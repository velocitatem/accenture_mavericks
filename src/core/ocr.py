import platform
import os
import io
import logging
import tempfile
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import cpu_count
from typing import List, Dict, Any, Optional
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ocr")

# --- Configuration ---
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
CLOUD_MODEL = os.getenv("OCR_CLOUD_MODEL", "qwen3-vl:235b-cloud") 
LOCAL_MODEL = os.getenv("OCR_LOCAL_MODEL", "qwen3-vl:8b")
USE_CLOUD = os.getenv("OCR_USE_CLOUD", "true").lower() == "true"

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
USE_MISTRAL = os.getenv("OCR_USE_MISTRAL", "true").lower() == "true"

try:
    import ollama
    from ollama import Client
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logger.warning("Ollama python client not found. OCR will fall back to Classic.")

try:
    from mistralai import Mistral, DocumentURLChunk
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False
    logger.warning("Mistralai python client not found.")

_system = platform.system().lower()
if _system.startswith("win"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _get_page_image(pdf_path: str, page_number: int, dpi: int = 300) -> str:
    """Extracts page as image and saves to temp file. Returns path."""
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=dpi)
    
    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    pix.save(tmp_path)
    return tmp_path

def _ocr_mistral_full(pdf_path: str) -> List[Dict[str, Any]]:
    """Performs OCR on the entire PDF using Mistral API."""
    if not MISTRAL_AVAILABLE:
        raise ImportError("mistralai client not installed")
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not set")

    logger.info("Starting Mistral OCR...")
    client = Mistral(api_key=MISTRAL_API_KEY)
    file_path = Path(pdf_path)

    uploaded_file = client.files.upload(
        file={
            "file_name": file_path.stem,
            "content": file_path.read_bytes(),
        },
        purpose="ocr",
    )

    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)

    pdf_response = client.ocr.process(
        document=DocumentURLChunk(document_url=signed_url.url),
        model="mistral-ocr-latest",
        include_image_base64=True
    )
    
    results = []
    # Mistral response structure: has 'pages' list. Each page has 'markdown'.
    for i, page in enumerate(pdf_response.pages):
        text = page.markdown
        results.append({
            "page": i + 1,
            "text": text,
            "method": "MISTRAL"
        })
    
    logger.info(f"Mistral OCR completed for {len(results)} pages.")
    return results

def _ocr_ollama(image_path: str, model: str, is_cloud: bool, prompt: str) -> str:
    """Performs OCR using Ollama (Cloud or Local)."""
    if not OLLAMA_AVAILABLE:
        raise ImportError("Ollama client not installed")

    messages = [{
        "role": "user",
        "content": prompt,
        "images": [image_path]
    }]

    if is_cloud:
        if not OLLAMA_API_KEY:
            raise ValueError("OLLAMA_API_KEY not set for cloud inference")
        client = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {OLLAMA_API_KEY}"})
        response = client.chat(model=model, messages=messages)
    else:
        # Local
        response = ollama.chat(model=model, messages=messages)
    
    return response["message"]["content"]

def _ocr_classic(image_path: str, lang: str = "spa", autoliquidacion: bool = False) -> str:
    """Performs OCR using Tesseract."""
    img = Image.open(image_path)
    # Preprocessing
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)

    config = r"--psm 4" if autoliquidacion else r"--psm 6"
    return pytesseract.image_to_string(img, lang=lang, config=config)

def _process_page(args) -> Dict[str, Any]:
    pdf_path, page_idx, config = args
    page_number = page_idx + 1
    
    tmp_path = _get_page_image(pdf_path, page_idx)
    text = ""
    method_used = "NONE"

    try:
        # 1. Try Cloud
        if config.get("use_cloud") and OLLAMA_AVAILABLE:
            try:
                logger.debug(f"Page {page_number}: Trying Cloud OCR ({config['cloud_model']})")
                text = _ocr_ollama(tmp_path, config['cloud_model'], True, config['prompt'])
                method_used = "CLOUD"
            except Exception as e:
                logger.warning(f"Page {page_number}: Cloud OCR failed: {e}")

        # 2. Try Local
        if not text and OLLAMA_AVAILABLE:
            try:
                logger.debug(f"Page {page_number}: Trying Local OCR ({config['local_model']})")
                text = _ocr_ollama(tmp_path, config['local_model'], False, config['prompt'])
                method_used = "LOCAL"
            except Exception as e:
                logger.warning(f"Page {page_number}: Local OCR failed: {e}")

        # 3. Fallback to Classic
        if not text:
            try:
                logger.debug(f"Page {page_number}: Falling back to Classic OCR")
                text = _ocr_classic(tmp_path, config['lang'], config['autoliquidacion'])
                method_used = "CLASSIC"
            except Exception as e:
                logger.error(f"Page {page_number}: Classic OCR failed: {e}")
                text = f"[ERROR: OCR Failed for page {page_number}]"

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {"page": page_number, "text": text, "method": method_used}

def ocr_pdf(
    pdf_path: str,
    lang: str = "spa",
    autoliquidacion: bool = False,
    use_multiprocessing: bool = True,
    prompt: str = "Extract all text from this document, maintaining structure. Return tables in markdown.",
) -> List[Dict[str, Any]]:
    
    # 0. Try Mistral (Full PDF)
    if USE_MISTRAL and MISTRAL_AVAILABLE:
        try:
            return _ocr_mistral_full(pdf_path)
        except Exception as e:
            logger.warning(f"Mistral OCR failed: {e}. Falling back to page-by-page methods.")

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    config = {
        "use_cloud": USE_CLOUD,
        "cloud_model": CLOUD_MODEL,
        "local_model": LOCAL_MODEL,
        "lang": lang,
        "autoliquidacion": autoliquidacion,
        "prompt": prompt
    }

    args_list = [(pdf_path, i, config) for i in range(total_pages)]

    workers = min(cpu_count(), total_pages)
    if USE_CLOUD or OLLAMA_AVAILABLE:
        workers = min(2, workers) # Limit concurrency for LLM calls

    if use_multiprocessing and total_pages > 1:
        with ThreadPool(processes=workers) as pool:
            resultados = pool.map(_process_page, args_list)
    else:
        resultados = [_process_page(args) for args in args_list]

    resultados.sort(key=lambda x: x["page"])
    return resultados
