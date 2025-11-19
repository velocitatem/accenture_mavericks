from typing import Type, Union, List, Dict, Any
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
    max_retries = 2
    timeout = 60  # 1 minute timeout

    for attempt in range(1, max_retries + 1):
        try:
            response = chat(
                model='nemotron-mini:4b', # Use a capable model
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                format=json_schema,
                options={
                    'temperature': 0.0,  # Deterministic output
                    'timeout': timeout
                }
            )

            content = response.message.content
            data_dict = json.loads(content)

            # Validate and return
            return model.model_validate(data_dict)

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"LLM extraction attempt {attempt}/{max_retries} failed: {e}, retrying...")
            else:
                logger.error(f"LLM extraction failed after {max_retries} attempts: {e}")
                raise


def extract_from_chunk(chunk_text: str, model: Type[BaseModel]) -> BaseModel:
    """
    Extract partial/incomplete data from a single chunk.
    Uses relaxed validation to allow missing fields.
    """
    json_schema = model.model_json_schema()

    # Make all fields optional for chunk-based extraction
    for field_name, field_info in json_schema.get("properties", {}).items():
        if "required" in json_schema:
            # Remove from required list
            if field_name in json_schema["required"]:
                json_schema["required"].remove(field_name)

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

You are extracting data from a PARTIAL section of a document.
This is only one chunk of a larger document, so you may not see all information.

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
- Leave fields null/empty if not present in this chunk
"""

    user_prompt = f"""
    EXTRACT DATA FROM THIS CHUNK:
    {chunk_text}
    """

    max_retries = 2
    timeout = 60  # 1 minute timeout

    from openai import OpenAI
    for attempt in range(1, max_retries + 1):
        try:
            client = OpenAI()

            response = client.responses.parse(
                model="gpt-4o-2024-08-06",
                input=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": user_prompt
                    },
                ],
                text_format=model
            )
            return response.output_parsed
            # response = chat(
            #     model='nemotron-mini:4b',
            #     messages=[
            #         {'role': 'system', 'content': system_prompt},
            #         {'role': 'user', 'content': user_prompt}
            #     ],
            #     format=json_schema,
            #     options={
            #         'temperature': 0.0,
            #         'timeout': timeout
            #     }
            # )

            # content = response.message.content
            # data_dict = json.loads(content)

            # Don't validate strictly, just return the dict as model
            # Use construct to bypass validation
            #return model.model_construct(**data_dict)

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Chunk extraction attempt {attempt}/{max_retries} failed: {e}, retrying...")
            else:
                logger.error(f"Chunk extraction failed after {max_retries} attempts: {e}")
                # Return empty model as fallback
                return model.model_construct()


def merge_chunk_extractions(chunk_results: List[BaseModel], model: Type[BaseModel]) -> BaseModel:
    """
    Merge multiple partial extractions using voting strategy.
    - For each field, count occurrences of each value
    - Use majority vote winner
    - If no majority, use the last non-null value
    """
    from collections import Counter

    logger.info(f"Merging {len(chunk_results)} chunk extractions")

    merged_dict = {}

    # Get all field names from the model
    field_names = model.model_json_schema().get("properties", {}).keys()

    for field_name in field_names:
        values = []

        # Collect all non-null values for this field across chunks
        for chunk_result in chunk_results:
            chunk_dict = chunk_result.model_dump() if hasattr(chunk_result, 'model_dump') else chunk_result

            value = chunk_dict.get(field_name)

            # Skip null/empty values
            if value is None:
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            if isinstance(value, list) and len(value) == 0:
                continue

            # For lists, we'll extend rather than vote
            if isinstance(value, list):
                values.extend(value)
            else:
                values.append(value)

        # Apply voting/merge strategy
        if not values:
            merged_dict[field_name] = None
        elif isinstance(values[0], list) or all(isinstance(v, (dict, list)) for v in values):
            # For lists/dicts, concatenate unique items
            merged_dict[field_name] = values
        else:
            # Voting: count occurrences
            counter = Counter(values)
            most_common = counter.most_common()

            if len(most_common) == 1:
                # Only one value
                merged_dict[field_name] = most_common[0][0]
            elif most_common[0][1] > most_common[1][1]:
                # Clear majority
                merged_dict[field_name] = most_common[0][0]
                logger.debug(f"Field '{field_name}': majority vote = {most_common[0][0]} ({most_common[0][1]} votes)")
            else:
                # No majority, use last value
                merged_dict[field_name] = values[-1]
                logger.debug(f"Field '{field_name}': no majority, using last value = {values[-1]}")

    # Validate and return
    try:
        return model.model_validate(merged_dict)
    except Exception as e:
        logger.warning(f"Validation failed during merge: {e}. Returning constructed model.")
        return model.model_construct(**merged_dict)

if __name__ == "__main__":
    text = """

**Extracted Information (Key-Value Pairs)**

*   **Owners:** García y Don Carlos López Martínez
*   **Ownership Type:** Dueños en pleno dominio (Owners in full ownership)
*   **Property Type:** Finca urbana (Urban estate/property)
*   **Location:**
    *   Calle/Street: C/ (Avenida/Street)
    *   Place/Town: ALCOBENDAS
    *   Building: Batalla de Belchite nº 6, 4° B (Building Battle of Belchite number 6, floor 4, letter B)

**Summary**

The document describes an urban property belonging to García and Don Carlos López Martínez, who are the full owners. The property is located on Calle/Street C/ Batalla de Belchite number 6, floor 4, letter B, in the town of ALCOBENDAS.
    """

    r = extract_from_chunk(text, Escritura)
    print(r)
