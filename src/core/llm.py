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

    # Define specific extraction rules based on the model type
    if model == Escritura:
        extraction_rules = """
**EXTRACTION RULES FOR ESCRITURA (DEED):**

1.  **NOTARY:**
    *   Locate the section titled "**DILIGENCIA DE DEPÓSITO DEL INSTRUMENTO**".
    *   Extract the notary's name (uppercase, bold) appearing after "**DOY FE. Signado; firmado:**".
    *   *Note:* NIF is usually not present for notary in deeds.

2.  **DOCUMENT NUMBER:**
    *   Locate the section titled "**COMPRA-VENTA**".
    *   Find the sentence with a number in words followed by Arabic numerals in parentheses (e.g., "mil ... (1000)").
    *   Extract ONLY the Arabic numerals inside the parentheses as the document number.

3.  **DATE OF SALE:**
    *   Locate the section titled "**COMPRA-VENTA**".
    *   Find the date expressed as "EN [City], a [Day] de [Month] de [Year]".
    *   Convert to format **DD-MM-YYYY**.

4.  **REGISTRY INFO:**
    *   Locate the section titled "**EXPONEN**".
    *   Find the paragraph containing "**INSCRIPCIÓN**".
    *   Extract: "Registro de la Propiedad número [num] de [locality], al tomo [vol], libro [book], folio [page], finca [prop_num]".
    *   If not registered, output "Not registered".

5.  **FORM TYPE (U/R):**
    *   In "**EXPONEN**", look for "**finca rústica**" -> Return "**600R**".
    *   In "**EXPONEN**", look for "**finca urbana**" -> Return "**600U**".

6.  **PROPERTY DETAILS:**
    *   **Cadastral Reference:** In "**EXPONEN**", look for "**Referencia catastral**" and extract the alphanumeric value immediately following.
    *   **Address:** In "**EXPONEN**", look for "**Finca sita en**" or "**situada en**". Extract full address.
    *   **Surface Area:** In "**EXPONEN**", look for "**superficie construida**" or "**que mide**". Extract numeric value only.
    *   **Type:** In "**EXPONEN**", extract the word describing the asset (e.g., "vivienda", "local", "garaje").
    *   **Purchase Year:** In "**EXPONEN**" -> "**TÍTULO**", look for "**formalizada en escritura autorizada por... el Notario de... [Date]**". Extract date as DD-MM-YYYY.

7.  **BUYERS (COMPRADORES):**
    *   Locate "**COMPARECEN**" -> "**COMO COMPRADORES**".
    *   Extract Name (after "**DON**"/"**DOÑA**") and NIF ("**D.N.I.**").

8.  **SELLERS (VENDEDORES):**
    *   Locate "**COMPARECEN**" -> "**COMO VENDEDORES**".
    *   Extract Name (after "**DON**"/"**DOÑA**") and NIF ("**D.N.I.**").
    *   *Note:* Ignore marital status or property regime for now unless specified in schema.

"""
    elif model == Modelo600:
        extraction_rules = """
**EXTRACTION RULES FOR MODELO 600 (SELF-ASSESSMENT):**

1.  **NOTARY:**
    *   **Name:** Locate block below "**SUJETO PASIVO**" and before "**MODALIDAD DE GRAVAMEN**". Extract name after NIF.
    *   **NIF:** In the same block, look for line starting with "**NOTARIO**". Extract alphanumeric value after dash/period.

2.  **DOCUMENT NUMBER:**
    *   Locate block below "**SUJETO PASIVO**". Look for line starting with "**DOCUMENTO**".
    *   Format is usually "PROVINCE/CODE - YEAR - PROTOCOL - NUMBER".
    *   Extract the **third element** (Protocol Number) as the document number.

3.  **DATE OF SALE (Devengo):**
    *   Locate "**DATOS DE LA OPERACIÓN**".
    *   Extract "**Fecha de devengo**" (right-aligned). Format: **DD-MM-YYYY**.

4.  **REGISTRY INFO:**
    *   Usually not present in Self-Assessment. Return null/empty if not found.

5.  **FORM TYPE (U/R):**
    *   Locate "**MODALIDAD DE GRAVAMEN TPO**".
    *   Find "**MODELO**" and extract code (e.g., "**600U**" or "**600R**").

6.  **PROPERTY DETAILS:**
    *   **Cadastral Reference:** Locate "**DATOS DEL INMUEBLE**" -> "**Referencia catastral**" (right-aligned in "**AUTOLIQUIDACIÓN**" col).
    *   **Address:** "**DATOS DEL INMUEBLE**" -> "**Dirección del inmueble**".
    *   **Surface Area:** "**DATOS TÉCNICOS**" -> "**Superficie construida**". Return numeric value only.
    *   **Type:** "**DATOS DEL INMUEBLE**" -> "**Tipo de bien**".

7.  **BUYERS (SUJETO PASIVO):**
    *   Locate "**SUJETO PASIVO**" (top right).
    *   Extract Name and NIF.

8.  **SELLERS (TRANSMITENTES):**
    *   Locate "**TRANSMITENTES**".
    *   Extract "**Apellidos y Nombre/Razón social**" and "**NIF**" (right-aligned in "**AUTOLIQUIDACIÓN**" col).

"""
    else:
        extraction_rules = "Extract the data according to the schema."

    system_prompt = f"""You are an expert at extracting structured data from Spanish legal documents (Deeds and Tax Forms).

{extraction_rules}

**GENERAL NEGATIVE CONSTRAINTS & FORMATTING:**
*   **NO HALLUCINATIONS:** Only extract what is explicitly in the text. If a field is missing, leave it null/empty.
*   **NO PLACEHOLDERS:** NEVER use placeholders like "<NAME>", "Unknown", "N/A", or "Jane Doe". If the name is not found, leave it null.
*   **EXTRACT EXACT TEXT:** When extracting names, copy the exact string found in the text (e.g., "HERRERA FERNÁNDEZ JAVIER").
*   **DATES:** Always use **DD-MM-YYYY**.
*   **NUMBERS:** Use dots for thousands and commas for decimals (Spanish format) OR standard US format, but be consistent.
*   **NAMES vs ROLES:**
    *   Do NOT use "MODELO 600U", "SUJETO PASIVO", or "TRANSMITENTE" as a person's name.
    *   "SUJETO PASIVO" is the **BUYER**.
    *   "TRANSMITENTE" is the **SELLER**.
*   **NOTARY:** Ensure the notary name is a person's name, not a code.
"""

    user_prompt = f"""
    EXTRACT DATA FROM THIS TEXT:
    {text}
    """
    try:
        response = chat(
            model='nemotron-mini:4b', # Use a capable model
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            format=json_schema,
            options={'temperature': 0.0} # Deterministic output
        )

        content = response.message.content
        data_dict = json.loads(content)

        return data_dict

        # Validate
        # return model.model_validate(data_dict) # Validation is done by caller or separate step if needed, but function signature says return BaseModel.
        # The original code returned data_dict at line 39 and unreachable code at 41.
        # I will return the validated model to match signature.
        return model.model_validate(data_dict)

    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise


if __name__ == "__main__":
    text = """Here's a breakdown of the information extracted from the image, presented as key-value pairs and a summary:\n\n**Key-Value Pairs (Extracted Text):**\n\n*   **SUJETO PASIVO:**\n    *   Nombre/Razón Social: HERRERA FERNÁNDEZ JAVIER\n    *   NIF: 12345678B\n*   **PRESENTADOR:** 777777E GÓMEZ RICARDO\n*   **DOCUMENTO:** 01-2025 -1234-001\n*   **NOTARIO:** 777777E GÓMEZ RICARDO\n*   **REGISTRO:** 32.345-2025 -001\n*   **AUTOLÍQUID.** 22345-2025 -I\n*   **BIENES INMUEBLES URBANOS**\n*   **MODELO 600U**\n*   **MODALIDAD DE GRAVAMEN TPO**\n*   **TRANSMITENTES**\n*   **APELLIDOS Y NOMBRE/RAZÓN SOCIAL:** MARTINEZ GARCIA LUCIA\n\n**Summary:**\n\nThe image appears to be a document related to real estate transfer in Spain, likely a declaration or form for tax purposes.\n\n*   **Subject (SUJETO PASIVO):** The subject or recipient of the document is HERRERA FERNÁNDEZ JAVIER with NIF 12345678B.\n*   **Presenter/Notary:** The document was presented by and notarized by GÓMEZ RICARDO (with identification number 777777E).\n*   **Reference Numbers:** A series of reference numbers are present: 01-2025 -1234-001,  32.345-2025-001, and AUTOLÍQUID. 22345-2025-I.\n*   **Type:**  A transaction type is shown (Bienes Inmuebles Urbanos, Modelo 600U,  Modalidad de gravamen TPO).\n*   **Transmitter:** MARTINEZ GARCIA LUCIA.\n\n**Important Notes:**\n\n*   This is based solely on the visible text in the image. The context and full meaning require understanding the overall document.\n*   Some elements might be incomplete or obscured."""


    print(extract_structured_data(text))
