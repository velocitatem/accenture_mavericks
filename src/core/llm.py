from typing import Type, Union, List, Dict, Any
from enum import Enum
from ollama import chat
from pydantic import BaseModel
import json
import logging
from .validation import Escritura, Modelo600

logger = logging.getLogger("llm")

class ExtractionProvider(Enum):
    OPENAI = "OPENAI"
    OLLAMA = "OLLAMA"

def extract_structured_data(pages_or_text: Union[str, List[Dict]], model: Type[BaseModel] = Escritura, provider: ExtractionProvider = ExtractionProvider.OPENAI) -> BaseModel:
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

Your goal is to accurately extract the objects of who are the sellers and who are the buyers. Do not extract more than one nif per field.  "buyer_nif": "11223344E / 55667788F",THIS IS WRONG, just one string with no slashes or commas.
If there are two sellers, they should each have their own entry in the sales breakdown, only one nif per buyer or seller nif field. Some fractions or proportions may be verbally expressed, make sure to think about that and take into account when extracting the sales breakdown. The final sales breakdown should highlight all the different parties which are seeling or buying (individuals) and what the proerty is (identified by the catastral reference) and how much of each individuals stake is in the transaction.

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

        In this text we have N pages of transfers between buyers and sellers. Each page first defines the subject, the buyer (sujeto pasivo) or the sellers and under each seller we identify the proportion of the property they sell. This shouls be highlighted in the sales breakdown of the whole document, first identify the sujetos pasivos across all the pages, then identify the transmitentes and their proportions. Finally match the buyers to the sellers based on the proportions and what property they are transacting over. If there are two sellers, they should each have their own entry in the sales breakdown, only one nif per buyer or seller nif field.

Return values of amounts just as numbers not separated by anythingor whole integers very simply. NO: 160,000.00 YES: 160000
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
    timeout = 60

    for attempt in range(1, max_retries + 1):
        try:
            if provider == ExtractionProvider.OPENAI:
                from openai import OpenAI
                client = OpenAI()
                response = client.responses.parse(
                    model="gpt-5-mini",
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    text_format=model
                )
                return response.output_parsed
            elif provider == ExtractionProvider.OLLAMA:
                response = chat(
                    model='nemotron-mini:4b',
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    format=json_schema,
                    options={'temperature': 0.0, 'timeout': timeout}
                )
                content = response.message.content
                data_dict = json.loads(content)
                return model.model_validate(data_dict)
            else:
                raise ValueError(f"Unknown provider: {provider}")

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"LLM extraction attempt {attempt}/{max_retries} failed: {e}, retrying...")
            else:
                logger.error(f"LLM extraction failed after {max_retries} attempts: {e}")
                raise


def extract_from_chunk(chunk_text: str, model: Type[BaseModel], provider: ExtractionProvider = ExtractionProvider.OPENAI) -> BaseModel:
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
Another chunk may contain the information you're looking for.

{extraction_rules}

**CRITICAL NEGATIVE CONSTRAINTS:**
*   **NO HALLUCINATIONS:** ONLY extract what is EXPLICITLY visible in the text below. If a field is missing from this chunk, return null (not empty string "").
*   **NO PLACEHOLDERS:** NEVER use placeholders like "<NAME>", "Unknown", "N/A", "Jane Doe", or similar. Return null instead.
*   **NO EMPTY OBJECTS:** Do NOT return empty objects like {{"name": "", "nif": null}}. If you don't see a person's name in this chunk, return null for that entire person entry.
*   **NO ROLE NAMES AS PERSON NAMES:** Do NOT extract role labels as names:
    *   WRONG: "MODELO 600U", "SUJETO PASIVO", "TRANSMITENTE", "VENDEDOR", "COMPRADOR", "EL NOTARIO"
    *   RIGHT: Actual person names like "Ricardo Gómez Hernández"
*   **EXTRACT EXACT TEXT:** When extracting names, copy the exact string found in the text (e.g., "HERRERA FERNÁNDEZ JAVIER").
*   **DATES:** Always use **DD-MM-YYYY** format. If you don't see a date, return null.
*   **NUMBERS:** Preserve exact numeric format from source.
*   **EMPTY CHUNKS:** If this chunk contains no relevant information for extraction, it's OK to return an object with all null/empty fields.

**ROLE CLARIFICATIONS:**
*   "SUJETO PASIVO" label means this section contains **BUYER** information
*   "TRANSMITENTE" label means this section contains **SELLER** information
*   Extract the actual person's name that appears AFTER these labels, not the labels themselves
"""

    user_prompt = f"""
    EXTRACT DATA FROM THIS CHUNK:
    {chunk_text}
    """

    max_retries = 2
    timeout = 60

    for attempt in range(1, max_retries + 1):
        try:
            if provider == ExtractionProvider.OPENAI:
                from openai import OpenAI
                client = OpenAI()
                response = client.responses.parse(
                    model="gpt-4o-2024-08-06",
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    text_format=model
                )
                return response.output_parsed
            elif provider == ExtractionProvider.OLLAMA:
                response = chat(
                    model='nemotron-mini:4b',
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    format=json_schema,
                    options={'temperature': 0.0, 'timeout': timeout}
                )
                content = response.message.content
                data_dict = json.loads(content)
                return model.model_construct(**data_dict)
            else:
                raise ValueError(f"Unknown provider: {provider}")

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Chunk extraction attempt {attempt}/{max_retries} failed: {e}, retrying...")
            else:
                logger.error(f"Chunk extraction failed after {max_retries} attempts: {e}")
                return model.model_construct()


def normalize_name(name: str) -> str:
    """
    Normalize a person's name for comparison.
    - Remove titles (Don, Doña, Sr., Sra.)
    - Convert to lowercase
    - Remove accents
    - Strip extra whitespace
    """
    import unicodedata

    if not name:
        return ""

    # Remove titles
    titles = ['don ', 'doña ', 'sr. ', 'sra. ', 'señor ', 'señora ', 'd. ', 'dª ']
    name_lower = name.lower().strip()
    for title in titles:
        if name_lower.startswith(title):
            name_lower = name_lower[len(title):]

    # Remove accents
    name_normalized = unicodedata.normalize('NFD', name_lower)
    name_normalized = ''.join(char for char in name_normalized if unicodedata.category(char) != 'Mn')

    # Clean up whitespace
    name_normalized = ' '.join(name_normalized.split())

    return name_normalized


def deduplicate_persons(persons: List[Dict]) -> List[Dict]:
    """
    Deduplicate person entries by merging information from different chunks.
    Strategy: Group by normalized name, then merge all fields (prefer non-null values)
    """
    if not persons:
        return []

    # Filter out placeholder/invalid entries first
    placeholder_keywords = ['placeholder', 'unknown', 'n/a', 'jane doe', 'john doe', 'ejemplo', 'example']

    # Group by normalized name
    groups = {}
    for person in persons:
        if not isinstance(person, dict):
            continue

        name = person.get('full_name', '')
        if not name or name.strip() == '':
            continue

        # Skip placeholders
        name_lower = name.lower()
        if any(keyword in name_lower for keyword in placeholder_keywords):
            logger.debug(f"Skipping placeholder person: {name}")
            continue

        normalized = normalize_name(name)
        if not normalized:
            continue

        if normalized not in groups:
            groups[normalized] = []
        groups[normalized].append(person)

    # Merge each group
    deduplicated = []
    for normalized_name, group in groups.items():
        # Start with the first entry
        merged = group[0].copy()

        # Merge fields from all entries in the group
        for person in group[1:]:
            for key, value in person.items():
                # Skip if value is null/empty
                if value is None or value == '':
                    continue

                # If current merged value is null/empty, use this value
                current = merged.get(key)
                if current is None or current == '':
                    merged[key] = value
                # Special handling for NIFs: consolidate different NIF fields
                elif key in ['nif', 'seller_nif', 'buyer_nif']:
                    # If we have a NIF in one field and null in another, populate it
                    if merged.get('nif') is None and value:
                        merged['nif'] = value
                    if key == 'seller_nif' and merged.get('seller_nif') is None and value:
                        merged['seller_nif'] = value
                    if key == 'buyer_nif' and merged.get('buyer_nif') is None and value:
                        merged['buyer_nif'] = value
                # For full_name, prefer the version with proper capitalization
                elif key == 'full_name' and value:
                    # Prefer mixed case over all caps
                    if current.isupper() and not value.isupper():
                        merged[key] = value

        # Ensure consistent full_name (prefer mixed case)
        if 'full_name' in merged:
            candidates = [p.get('full_name', '') for p in group if p.get('full_name')]
            # Pick the one with best capitalization (mixed case preferred)
            mixed_case = [c for c in candidates if c and not c.isupper() and not c.islower()]
            if mixed_case:
                merged['full_name'] = mixed_case[0]
            elif candidates:
                merged['full_name'] = candidates[0]

        deduplicated.append(merged)

    logger.debug(f"Deduplicated {len(persons)} persons into {len(deduplicated)} unique entries")
    return deduplicated


def deduplicate_properties(properties: List[Dict]) -> List[Dict]:
    """
    Deduplicate property entries by merging information from different chunks.
    Strategy: Group by cadastral reference (if available) or address, then merge fields
    """
    if not properties:
        return []

    # Filter out placeholder/invalid entries
    placeholder_keywords = ['placeholder', 'unknown', 'n/a', 'ejemplo', 'example', 'calle falsa']

    # Group by cadastral reference or address
    groups = {}
    unkeyed = []  # Properties without ref_catastral or address

    for prop in properties:
        if not isinstance(prop, dict):
            continue

        # Check for placeholders in any field
        is_placeholder = False
        for key, value in prop.items():
            if isinstance(value, str):
                value_lower = value.lower()
                if any(keyword in value_lower for keyword in placeholder_keywords):
                    logger.debug(f"Skipping placeholder property: {key}={value}")
                    is_placeholder = True
                    break

        if is_placeholder:
            continue

        # Try to find a key: ref_catastral > address
        ref_cat = prop.get('ref_catastral', '').strip()
        address = prop.get('address', '').strip() if prop.get('address') else ''

        key = None
        if ref_cat and ref_cat != '':
            key = ('ref', ref_cat)
        elif address and address != '':
            key = ('addr', address.lower())

        if key:
            if key not in groups:
                groups[key] = []
            groups[key].append(prop)
        else:
            # No clear key - check if it has ANY non-null fields
            if any(v for k, v in prop.items() if k != 'id' and v not in [None, '', []]):
                unkeyed.append(prop)

    # Merge each group
    deduplicated = []
    for key, group in groups.items():
        # Start with the first entry
        merged = group[0].copy()

        # Merge fields from all entries in the group
        for prop in group[1:]:
            for field_name, value in prop.items():
                # Skip if value is null/empty
                if value is None or value == '':
                    continue

                # If current merged value is null/empty, use this value
                current = merged.get(field_name)
                if current is None or current == '':
                    merged[field_name] = value
                # For numeric fields, prefer non-zero values
                elif field_name in ['declared_value', 'surface_area']:
                    try:
                        current_num = float(str(current).replace(',', '.')) if current else 0
                        value_num = float(str(value).replace(',', '.')) if value else 0
                        if value_num > current_num:
                            merged[field_name] = value
                    except (ValueError, TypeError):
                        pass

        deduplicated.append(merged)

    # Add unkeyed properties (but try to avoid completely empty ones)
    for prop in unkeyed:
        # Only add if it has substantial data
        non_null_fields = sum(1 for k, v in prop.items() if k != 'id' and v not in [None, '', []])
        if non_null_fields >= 2:  # At least 2 fields populated
            deduplicated.append(prop)

    logger.debug(f"Deduplicated {len(properties)} properties into {len(deduplicated)} unique entries")
    return deduplicated


def merge_chunk_extractions(chunk_results: List[BaseModel], model: Type[BaseModel]) -> BaseModel:
    """
    Merge multiple partial extractions using voting strategy.
    - For single-value fields: Use majority vote
    - For list fields: Collect all items and deduplicate
    """
    from collections import Counter
    from typing import get_origin

    logger.info(f"Merging {len(chunk_results)} chunk extractions")

    merged_dict = {}

    # Get all field names and their types from the model
    model_fields = model.model_fields

    for field_name in model_fields.keys():
        field_info = model_fields[field_name]
        field_type = field_info.annotation
        is_list_field = get_origin(field_type) is list

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
            if isinstance(value, dict) and not any(value.values()):
                # Empty dict (all values are None/empty)
                continue

            values.append(value)

        # Apply merge strategy based on field type
        if not values:
            merged_dict[field_name] = None if not is_list_field else []
        elif is_list_field:
            # List field: collect all items from all chunks
            all_items = []
            for value in values:
                if isinstance(value, list):
                    all_items.extend(value)
                else:
                    all_items.append(value)
            merged_dict[field_name] = all_items
        else:
            # Single value field: use voting strategy
            # For complex objects (dicts), convert to JSON string for comparison
            if all(isinstance(v, dict) for v in values):
                # Convert dicts to JSON strings for counting
                import json
                json_values = [json.dumps(v, sort_keys=True) for v in values]
                counter = Counter(json_values)
                most_common_json = counter.most_common(1)[0][0]
                merged_dict[field_name] = json.loads(most_common_json)
            else:
                # Simple values: direct voting
                counter = Counter(str(v) if not isinstance(v, (int, float, bool)) else v for v in values)
                most_common = counter.most_common()

                if len(most_common) == 1:
                    merged_dict[field_name] = values[0]
                elif most_common[0][1] > most_common[1][1]:
                    # Clear majority - find original value
                    winner_str = most_common[0][0]
                    merged_dict[field_name] = next(v for v in values if str(v) == winner_str)
                    logger.debug(f"Field '{field_name}': majority vote = {winner_str} ({most_common[0][1]} votes)")
                else:
                    # No majority, use last non-null value
                    merged_dict[field_name] = values[-1]
                    logger.debug(f"Field '{field_name}': no majority, using last value = {values[-1]}")

    # Post-process: deduplicate and clean up lists
    if 'sellers' in merged_dict and merged_dict['sellers']:
        merged_dict['sellers'] = deduplicate_persons(merged_dict['sellers'])
    if 'buyers' in merged_dict and merged_dict['buyers']:
        merged_dict['buyers'] = deduplicate_persons(merged_dict['buyers'])
    if 'properties' in merged_dict and merged_dict['properties']:
        merged_dict['properties'] = deduplicate_properties(merged_dict['properties'])

    # Validate and return
    try:
        return model.model_validate(merged_dict)
    except Exception as e:
        logger.warning(f"Validation failed during merge: {e}. Returning constructed model.")
        return model.model_construct(**merged_dict)

if __name__ == "__main__":
    C = ["SUJETO PASIVO\nHERRERA\nFERNÁNDEZ\nJAVIER\n11223344E\n\nPRESENTADOR.- 77777777F GOMEZ HERNANDEZ RICARDO\nAUTOLIQUID. 22345-2025-I\nDOCUMENTO .- 01-2025- 1234-001 TIPO .- NOTARIAL\nNOTARIO .- 77777777F GOMEZ HERNANDEZ RICARDO\nREGISTRO .- 32.345-2025-001\n\nMODALIDAD DE GRAVAMEN TPO MODELO 600U\nBIENES INMUEBLES URBANOS\n\nTRANSMITENTES\nNIF\nApellidos y Nombre/Razón social\nAUTOLIQUIDACION\n12345678B\nMARTINEZ GARCIA LUCIA", "# TRANSMITENTES\n\n## NIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\n\n## NIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\n\n## DATOS DE LA OPERACIÓN\nConcepto de la operación\nFecha de devengo\n\n## DATOS DEL INMUEBLE\nTipo de bien\nReferencia catastral\n\nDirección del inmueble\n\n## DATOS TÉCNICOS\nDestinada a vivienda habitual\nNo +25% otra viv. mismo municipio\nSuperficie construida\n\n## DATOS LIQUIDATORIOS\nValor declarado bien inmueble\nCoeficiente de Adquisición\nBASE IMPONIBLE\n\n---\n\n# AUTOLIQUIDACION\n\n12345678B\nMARTINEZ GARCIA LUCIA\n50,00%\n\n87654321C\nLOPEZ MARTINEZ CARLOS\n50,00%\n\n001-Compraventa bienes inmuebles\n10-02-2025\n\nVivienda\n123456780000010001BN\n\nMADRID ALCOBENDAS CALLE BATALLA DE BELCHITE 6 4 B\n\nSi\n115,75m2\n\n320.000,00\n100,00%\n160.000,00", "DATOS LIQUIDATORIOS\nValor declarado bien inmueble 320.000,00\nCoeficiente de Adquisición 100,00\\%\nBASE IMPONIBLE 160.000,00\nREDUCCIÓN\nBASE LIQUIDABLE 160.000,00\nTIPO 2,50\nCUOTA 4.000,00\nBONIFICACIÓN\nA INGRESAR 4.000,00\nINGRESADO A CUENTA\nRECARGO\nINTERESES DE DEMORA\nDEUDA TRIBUTARIA\n$4.000,00$\n(Norma, art, apdo)", "SUJETO PASIVO\nHERRERA\nFERNÁNDEZ\nJAVIER\n11223344E\n\nPRESENTADOR. - 77777777F GOMEZ HERNANDEZ RICARDO\nAUTOLIQUID. 22345-2025-I\nDOCUMENTO .- 01-2025- 1234-001 TIPO .- NOTARIAL\nNOTARIO .- 77777777F GOMEZ HERNANDEZ RICARDO\nREGISTRO .- 32345-2025-001\n\nMODALIDAD DE GRAVAMEN TPO MODELO 600R\nBIENES INMUEBLES RUSTICOS\n\nTRANSMITENTES\nNIF\nApellidos y Nombre/Razón social\n\nAUTOLIQUIDACION\n44332211D\nPEREZ RODRIGUEZ ANA", "# ATTUANA \n\nTRANSMITENTES\nNIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\nNIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\n\n## DATOS DE LA OPERACIÓN\n\nConcepto de la operación\nFecha de devengo\nDATOS DEL INMUEBLE\nReferencia catastral\nValor declarado individual (100\\%)\nExención\n\n## DATOS LIQUIDATORIOS\n\nBASE IMPONIBLE SUJETA\nREDUCCIÓN\nBASE LIQUIDABLE\nTIPO\nCUOTA\nBONIFICACIÓN\nA INGRESAR\nINGRESADO A CUENTA\nRECARGO\nINTERESES DE DEMORA\n\n## AUTOLIQUIDACION\n\n44332211D\nPEREZ RODRIGUEZ ANA\n$25,00 \\%$\n87654321 C\nLOPEZ MARTINEZ CARLOS\n$25,00 \\%$\n\n001-Compraventa bienes inmuebles\n$10-02-2025$\n\n876543210000010001JX\n250,00\nNo\n\n250,00\n250,00\n7,00\n17,50\n17,50", "CUOTA ..... 17,50\nBONIFICACIÓN\nA INGRESAR ..... 17,50\nINGRESADO A CUENTA\nRECARGO\nINTERESES DE DEMORA\nDEUDA TRIBUTARIA ..... 17,50\nBASE IMPONIBLE EXENTA\n(Norma, art, apdo)", "SUJETO PASIVO\nGÓMEZ\nPIZARRO\nLAURA\n55667788F\n\nPRESENTADOR. - 77777777F GOMEZ HERNANDEZ RICARDO\nAUTOLIQUID. 22345-2025-I\nDOCUMENTO .- 01-2025- 1234-001 TIPO .- NOTARIAL\nNOTARIO .- 77777777F GOMEZ HERNANDEZ RICARDO\nREGISTRO .- 32345-2025-001\n\nMODALIDAD DE GRAVAMEN TPO MODELO 600R\nBIENES INMUEBLES RUSTICOS\n\nTRANSMITENTES\nNIF\nApellidos y Nombre/Razón social\nAUTOLIQUIDACION\n44332211D\nPEREZ RODRIGUEZ ANA", "# ATTUANA \n\nTRANSMITENTES\nNIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\nNIF\nApellidos y Nombre/Razón social\nCoeficiente de transmisión\n\n## DATOS DE LA OPERACIÓN\n\nConcepto de la operación\nFecha de devengo\nDATOS DEL INMUEBLE\nReferencia catastral\nValor declarado individual (100\\%)\nExención\n\n## DATOS LIQUIDATORIOS\n\nBASE IMPONIBLE SUJETA\nREDUCCIÓN\nBASE LIQUIDABLE\nTIPO\nCUOTA\nBONIFICACIÓN\nA INGRESAR\nINGRESADO A CUENTA\nRECARGO\nINTERESES DE DEMORA\n\n## AUTOLIQUIDACION\n\nPEREZ RODRIGUEZ ANA\n$25,00 \\%$\n87654321 C\nLOPEZ MARTINEZ CARLOS\n$25,00 \\%$\n\n001-Compraventa bienes inmuebles\n$10-02-2025$\n\n876543210000010001JX\n250,00\nNo\n\n250,00\n250,00\n7,00\n17,50\n17,50", "CUOTA ..... 17,50\nBONIFICACIÓN\nA INGRESAR ..... 17,50\nINGRESADO A CUENTA\nRECARGO\nINTERESES DE DEMORA\nDEUDA TRIBUTARIA ..... 17,50\nBASE IMPONIBLE EXENTA\n(Norma, art, apdo)"]
    text = "\n".join(C)

    r = extract_from_chunk(text, Modelo600)
    print(r)

    # print as json
