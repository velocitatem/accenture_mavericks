import platform
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import cpu_count
import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
import io
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()


try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

_system = platform.system().lower()
if _system.startswith("win"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _ocr_pagina_ollama(args):
    """
    OCR a single PDF page using an Ollama vision model.
    """
    pdf_path, page_number, prompt, ollama_model = args

    print(f"[DEBUG] Processing page {page_number + 1}")

    if not OLLAMA_AVAILABLE:
        raise ImportError("Ollama Python client is not installed.")

    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=300)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name
        pix.save(tmp_path)

    print(f"[DEBUG] Page {page_number + 1} saved to {tmp_path}")

    try:
        is_cloud_model = ollama_model.endswith("-cloud")

        if is_cloud_model:
            from ollama import Client

            api_key = os.environ.get("OLLAMA_API_KEY")
            if not api_key:
                raise ValueError("Environment variable OLLAMA_API_KEY is not set.")

            client = Client(
                host="https://ollama.com",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            response = client.chat(
                model=ollama_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [tmp_path],
                    }
                ],
            )
        else:
            response = ollama.chat(
                model=ollama_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [tmp_path],
                    }
                ],
            )

        result = response["message"]["content"]
        print(f"[DEBUG] Page {page_number + 1} OCR complete, text length: {len(result)}")
        return {"page": page_number + 1, "text": result}

    except Exception as e:
        error_msg = str(e)
        return {"page": page_number + 1, "text": f"[Error: {error_msg}]"}
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def leer_pdf_texto(pdf_path):
    """
    Read a PDF with extractable (non-scanned) text and return a list of
    dictionaries with page number and text for each page.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.

    Returns
    -------
    list[dict]
        [
            {"page": 1, "text": "..."},
            {"page": 2, "text": "..."},
            ...
        ]
    """
    resultados = []

    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            page_number = i + 1
            text = page.get_text("text")
            resultados.append({"page": page_number, "text": text})

    return resultados


def _ocr_pagina_escritura_basico(args):
    pdf_path, page_number, lang, dpi, autoliquidacion = args

    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=dpi)

    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)

    if autoliquidacion:
        custom_oem_psm_config = r"--psm 4"
    else:
        custom_oem_psm_config = r"--psm 6"

    text = pytesseract.image_to_string(
        img,
        lang=lang,
        config=custom_oem_psm_config,
    )

    return {
        "page": page_number + 1,
        "text": text,
    }


def ocr_pdf(
    pdf_path: str,
    model: str = "CLASSIC",
    lang="spa",
    dpi: int = 300,
    use_multiprocessing: bool = True,
    autoliquidacion: bool = False,
    prompt: str = (
        "Extract all text from this document, maintaining the original structure "
        "and formatting. Return any tables in markdown format."
    ),
    ollama_model: str = "qwen3-vl:8b",
):
    """
    OCR for PDFs using different backends.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF file.
    model : str
        OCR engine:
        - "CLASSIC": Tesseract via Pytesseract.
        - "OLLAMA": Vision model via Ollama.
    lang : str
        Language for Tesseract (CLASSIC only), e.g. "spa", "eng", "spa+eng".
    dpi : int
        Page rendering resolution for rasterization.
    use_multiprocessing : bool
        Use multiprocessing for page-level parallelism (recommended only for CLASSIC).
    autoliquidacion : bool
        Special configuration for specific document layouts (CLASSIC only).
    prompt : str
        Prompt for the vision model (OLLAMA only).
    ollama_model : str
        Ollama model name (OLLAMA only).

    Returns
    -------
    list[dict]
        List of {"page": int, "text": str} entries.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    if model.upper() == "OLLAMA":
        if not OLLAMA_AVAILABLE:
            raise ImportError("Ollama Python client is not installed.")

        args_list = [
            (pdf_path, i, prompt, ollama_model)
            for i in range(total_pages)
        ]
        worker_func = _ocr_pagina_ollama

    else:  # CLASSIC
        args_list = [
            (pdf_path, i, lang, dpi, autoliquidacion)
            for i in range(total_pages)
        ]
        worker_func = _ocr_pagina_escritura_basico

    if use_multiprocessing and total_pages > 1:
        workers = min(cpu_count(), total_pages)
        with ThreadPool(processes=workers) as pool:
            resultados = pool.map(worker_func, args_list)
    else:
        resultados = [worker_func(args) for args in args_list]

    resultados.sort(key=lambda x: x["page"])
    return resultados


def combinar_paginas(resultados):
    """
    Combine the text of all pages into a single string with simple page markers.

    Parameters
    ----------
    resultados : list[dict]
        List of {"page": int, "text": str}.

    Returns
    -------
    str
        Combined text.
    """
    partes = []
    for pagina in resultados:
        partes.append(f"<page number={pagina['page']}>\n{pagina['text']}\n</page>\n")
    return "".join(partes)

if __name__ == "__main__":
    pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Autoliquidacion.pdf"  # Replace with your PDF path

    # OCR using CLASSIC model
    resultados_classic = ocr_pdf(
        pdf_path,
        model="OLLAMA",
        lang="spa",
        dpi=300,
        use_multiprocessing=False,
        # ollama_model="qwen3-vl:235b-cloud",
        autoliquidacion=True,
    )
    text = combinar_paginas(resultados_classic)
    print("=== OCR CLASSIC Result ===")
    print(text)
