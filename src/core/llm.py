from typing import Optional
from ollama import chat
from pydantic import BaseModel
import pydantic
from .validation import Escritura

# model phi3:3.8b


def extract_structured_data(text: str) -> pydantic.BaseModel:
    """
    Use an LLM to extract structured data from text according to the provided Pydantic model.
    """
    model = Escritura
    json_schema = model.model_json_schema()

    prompt = f"""
Extract structured data matching this schema from the text:

Text:
{text}

Only return JSON output.
"""

    response = chat(
        model='phi3:3.8b',
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant that extracts structured data.'},
            {'role': 'user', 'content': prompt}
        ],
        format=json_schema,
    )
    print(response.message.content)

    structured_data = model.model_validate_json(response.message.content)
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
