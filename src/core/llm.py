from typing import Type, Union, List, Dict
from ollama import chat
from pydantic import BaseModel
import json
import logging
from .validation import Escritura, Modelo600

logger = logging.getLogger("llm")

def extract_structured_data(pages_or_text: Union[str, List[Dict]], model: Type[BaseModel] = Escritura) -> BaseModel:
    """
    Use an LLM to extract structured data from text according to the provided Pydantic model.
    """
    json_schema = model.model_json_schema()

    if isinstance(pages_or_text, list):
        text = "\n\n".join(f"=== PÁGINA {p['page']} ===\n{p['text']}" for p in pages_or_text)
    else:
        text = pages_or_text

    system_prompt = "You are an expert at extracting structured data from Spanish legal documents. Follow instructions precisely and extract only data that appears explicitly in the text. Never invent or hallucinate data."

    if model == Modelo600:
        user_prompt = f"""Extract structured data from this Spanish tax form (Modelo 600 - Autoliquidación).
        INSTRUCTIONS:
        1. **notary**:
           - Name: Look for "DILIGENCIA DE DEPÓSITO DEL INSTRUMENTO" or top block under "SUJETO PASIVO". Format: "Nombre Apellido1 Apellido2".
           - NIF: Look for "NOTARIO" under "SUJETO PASIVO".
        2. **document_number**:
           - Look for "DOCUMENTO" under "SUJETO PASIVO". Format: XXXX (3rd element of the code).
        3. **date_of_sale**:
           - Look for "Fecha de devengo" in "DATOS DE LA OPERACIÓN". Format: DD-MM-AAAA.
        4. **document_info**: List of pages/models found (e.g. 600U, 600R).
           - Model: Look for "MODELO" near "MODALIDAD DE GRAVAMEN TPO".
        5. **sellers**:
           - Name: "TRANSMITENTES" -> "Apellidos y Nombre/Razón social".
           - NIF: "TRANSMITENTES" -> "NIF".
        6. **buyers**:
           - Name: "SUJETO PASIVO" -> Name and surnames.
           - NIF: "SUJETO PASIVO" -> Number aligned to right.
        7. **properties**:
           - 'id': generate like 'finca_001'.
           - 'property_type': '600U' or '600R'.
           - 'declared_value': "DATOS DEL INMUEBLE" -> "Base imponible" or "Valor declarado".
           - 'ref_catastral': "DATOS DEL INMUEBLE" -> "Referencia catastral".
           - 'address': "DATOS DEL INMUEBLE" -> "Dirección del inmueble".
           - 'surface_area': "DATOS TÉCNICOS" -> "Superficie construida".
           - 'type': "DATOS DEL INMUEBLE" -> "Tipo de bien".
        8. **sale_breakdown**:
           - "DATOS LIQUIDATORIOS" -> "Coeficiente de adquisición" (%).
        9. **expenses_clause**: Who pays taxes.

        DOCUMENT TEXT:
        {text}

        Return ONLY valid JSON matching the schema.
        """
    else: # Escritura
        user_prompt = f"""Extract structured data from this Spanish Deed of Sale (Escritura).
        INSTRUCTIONS:
        1. **notary**:
           - Name: "DILIGENCIA DE DEPÓSITO DEL INSTRUMENTO" -> after "DOY FE. Signado; firmado:".
        2. **document_number**:
           - "COMPRA-VENTA" -> Number in parenthesis (Arabic notation).
        3. **date_of_sale**:
           - "COMPRA-VENTA" ->  Format: DD-MM-AAAA.
        4. **sellers**:
           - Name: "COMPARECEN" -> "COMO VENDEDORES" -> after "DON"/"DOÑA".
           - NIF: "COMPARECEN" -> "COMO VENDEDORES" -> "D.N.I." or "DD.NN.II.".
           - Marital Status: "COMPARECEN" -> "casado/a" -> "en régimen de".
        5. **buyers**:
           - Name: "COMPARECEN" -> "COMO COMPRADORES" -> after "DON"/"DOÑA".
           - NIF: "COMPARECEN" -> "COMO COMPRADORES" -> "D.N.I." or "DD.NN.II.".
        6. **properties**:
           - 'id': generate like 'finca_001'.
           - 'type': "EXPONEN" -> "vivienda", "local", "garaje", etc.
           - 'address': "EXPONEN" -> "Finca sita en" / "situada en".
           - 'ref_catastral': "EXPONEN" -> "Referencia catastral".
           - 'surface_area': "EXPONEN" -> "superficie construida" / "que mide".
           - 'registry_info': "EXPONEN" -> "INSCRIPCIÓN" -> "Registro... Tomo... Libro... Folio... Finca...".
           - 'purchase_year': "EXPONEN" -> "TÍTULO" -> "formalizada en escritura...". Date format DD-MM-YYYY.
        7. **sale_breakdown**:
           - "ESTIPULACIONES" -> Calculate based on "pleno dominio", "mitad indivisa", etc.
        8. **expenses_clause**: Who pays taxes/plusvalia.

        DOCUMENT TEXT:
        {text}

        Return ONLY valid JSON matching the schema.
        """

    try:
        response = chat(
            model='nemotron-mini:4b', # Use a capable model
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            format=json_schema,
        )

        content = response.message.content
        data_dict = json.loads(content)

        # Validate
        return model.model_validate(data_dict)

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise
