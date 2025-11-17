from typing import Optional, Type
from ollama import chat
from pydantic import BaseModel
import pydantic
from .validation import Escritura, Modelo600

# model phi3:3.8b


def extract_structured_data(pages_or_text, model: Type[BaseModel] = Escritura) -> pydantic.BaseModel:
    """
    Use an LLM to extract structured data from text according to the provided Pydantic model.
    Accepts either a string or a list of page dictionaries from OCR.

    Args:
        pages_or_text: Either a string or list of page dicts from OCR
        model: The Pydantic model to use (Escritura or Modelo600)
    """
    json_schema = model.model_json_schema()

    # Handle both text string and list of page dicts
    if isinstance(pages_or_text, list):
        text = "\n\n".join(f"=== PÁGINA {p['page']} ===\n{p['text']}" for p in pages_or_text)
    else:
        text = pages_or_text

    prompt = f"""Extract structured data from this Spanish legal document (deed of sale).

FORMAT RULES:
1. Dates: DD-MM-YYYY format (e.g., "10-02-2025")
2. NIFs/DNIs: 8 digits + uppercase letter (e.g., "12345678Z"). DO NOT invent NIFs.
3. Amounts: Plain decimals, no currency symbols (e.g., "150000.50" NOT "$150K")
4. Catastral refs: 14-20 alphanumeric chars, NO dashes (e.g., "1234567VK1234S0001AB")
5. Addresses: Must include street type (C/, CALLE, AVENIDA, AV., PLAZA)
6. Coefficients: 0-100 (e.g., 50 NOT 1500)
7. Names: First name + at least one surname

EXTRACTION INSTRUCTIONS:

**notary**: Find "Ante mí, [NAME], Notario". Extract name only. NIF usually null. College from "Colegio de [city]"

**fecha_compra**: Find section "COMPRA-VENTA", look for "EN [city], a [day] de [month] de [year]". Convert to DD-MM-YYYY.

**sellers**: Find "COMO VENDEDORES:". For each DON/DOÑA: extract full_name, find "D.N.I. número" for nif (8 digits+letter), role="vendedor", coeficiente_adquisicion=null unless explicit.

**buyers**: Find "COMO COMPRADORES:". For each DON/DOÑA: extract full_name, find "D.N.I. número" for nif, role="comprador", coeficiente_adquisicion=null unless explicit.

**properties**: Generate id like "finca_001". type="urbana" or "rústica" from "finca urbana/rústica". address from "Finca sita en" (MUST include C/, CALLE, etc.). ref_catastral from "Referencia catastral" (alphanumeric only, no dashes). declared_value_escritura from "ESTIPULACIONES" (decimal). Extract province, tipo_bien if present.

**price_breakdown**: For each seller+property: property_id (use generated id), seller_nif, amount (decimal). Amounts MUST sum to declared_value_escritura.

**expenses_clause**: who_pays_taxes (who pays taxes), incremento_valor_terrenos_urbanos (who pays this specific tax).

VALIDATION:
- NIFs: 8 digits + letter
- Dates: valid DD-MM-YYYY
- Coefficients: ≤100
- Catastral refs: letters/numbers only, 14-20 chars
- DO NOT invent data

Document text:
{text}

Extract ONLY explicit data. Use null for missing fields. Return ONLY valid JSON, no comments."""

    response = chat(
        model='qwen3:14b',
        messages=[
            {'role': 'system', 'content': 'You are an expert at extracting structured data from Spanish legal documents. Follow instructions precisely and extract only data that appears explicitly in the text. Never invent or hallucinate data.'},
            {'role': 'user', 'content': prompt}
        ],
        format=json_schema,
    )
    print(response.message.content)

    # Use model_construct to bypass validation and accept data as-is
    import json
    data_dict = json.loads(response.message.content)
    structured_data = model.model_construct(**data_dict)
    return structured_data


# Example usage:
if __name__ == "__main__":

    import os
    text = """
------------------ COMPRA-VENTA ------------------

NÚMERO MIL TRESCIENTOS TREINTA Y UNO (1.331) EN MADRID, mi residencia, a diez de febrero de dos mil veinticinco. ----------------------

Ante mí, RICARDO GÓMEZ HERNÁNDEZ, Notario del Ilustre Colegio de Madrid, --------------------

------------- C O M P A R E C E N -------------

DE UNA PARTE, COMO VENDEDORES: ----------------

DOÑA LUCÍA MARTÍNEZ GARCÍA, mayor de edad, soltera, empleada, de vecindad civil madrileña, vecina de ALCOBENDAS (Madrid), con domicilio en la calle Falsa, número 4, con D.N.I. número 12345678B. ----------------

DON CARLOS LÓPEZ MARTÍNEZ, Profesor, y DOÑA ANA PÉREZ RODRÍGUEZ, Arquitecta, casados en régimen de gananciales, mayores de edad, de vecindad civil madrileña, vecinos de ALCOBENDAS (Madrid), con domicilio en la Avenida Imaginaria, número 67, escalera
    """


    class Person(BaseModel):
        name: str
        dni: Optional[str]

    class People(BaseModel):
        people: list[Person]
    structured_data = extract_structured_data(text)
    print(structured_data)
