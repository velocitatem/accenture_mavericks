import ollama
from PIL import Image
import io
# Load your image bytes (for example, from a file or other source)
with open("test2.png", "rb") as f:
    image_bytes = f.read()

MODEL = "gemma3:12b"


img = Image.open(io.BytesIO(image_bytes))


def do_ocr(image : Image.Image) -> str:
    # Enhanced prompt for intelligent extraction
    prompt = """Analyze the text in the provided image. Extract all readable information and text and try to match key-value pairs of any values, extract everything that you can see in the image and provide a consistent summary"""
    # Convert image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    image_bytes = img_byte_arr.getvalue()

    # Execute AI inference via Ollama
    response = ollama.chat(
        model='gemma3:12b',
        messages=[{
            'role': 'user',
            'content': prompt,
            'images': [image_bytes]
        }])

    return response['message']['content']


result = do_ocr(img)
