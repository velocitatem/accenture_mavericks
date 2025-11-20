import ollama
from PIL import Image
import io

MODEL = "gemma3:12b"




def do_ocr(image : Image.Image) -> str:
    # Enhanced prompt for intelligent extraction
    prompt = """Given the provided text, extract all textual content word-by-word character-by-character preserving the original information, return in a markdown format as much as possible."""
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
