from openai import OpenAI
from pydantic import BaseModel
import pydantic #https://github.com/openai/openai-python

# model phi3:3.8b

client = OpenAI(
    base_url="http://127.0.0.1:11434/v1", # using ollama
)



def extract_structured_data(text: str, model : pydantic.BaseModel) -> pydantic.BaseModel:
    """
    Use an LLM to extract structured data from text according to the provided Pydantic model.
    """
    prompt = f"""
    Extract the following structured data from the text below and format it as JSON matching this schema:

    {model.model_json_schema()}

    Text:
    \"\"\"
    {text}
    \"\"\"

    Provide only the JSON output.
    """

    response = client.chat.completions.create(
        model="phi3:3.8b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured data."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=1000,
    )

    json_output = response.choices[0].message.content

    # Parse the JSON output into the Pydantic model
    structured_data = model.model_validate_json(json_output)
    return structured_data

# Example usage:
class Person(BaseModel):
    name: str
    age: int
    email: str

text = """
Name: John Doe
Age: 30
Email: daskjlkj!@wlkjD.COM
"""

structured_data = extract_structured_data(text, Person)
print(structured_data)
