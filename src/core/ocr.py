from platform import system
from multiprocessing.dummy import Pool as ThreadPool
from multiprocessing import Pool, cpu_count
import fitz # PyMuPDF
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance
import io
import platform

'''
Pytesseract necesita tener instalado Tesseract-OCR en el sistema operativo para que os funcione.
Usad esto en la terminal para instalarlo:
- Windows -> descargad desde este enlace https://github.com/UB-Mannheim/tesseract/wiki
    -Marcad spa (Spanish) en "additional language data" durante la instalación.

Si no eres Windows, usad estos comandos para descargar Tesseract-OCR:
- macOS -> en el terminal usad:
    brew install tesseract
    brew install tesseract-lang

- Linux (Debian/Ubuntu) -> sudo apt-get install tesseract-ocr
'''

system = platform.system().lower()
if system.startswith("win"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# -----------------------------
# Lector de PDFs con texto extraíble
# -----------------------------

def leer_pdf_texto(pdf_path):
    """
    Lee un PDF con texto extraíble (no escaneado) y devuelve una lista de
    diccionarios con el número de página y el texto de cada una.

    Arguments
    ----------
    pdf_path : str
        Ruta al archivo PDF.

    Returns
    -------
    list[dict]
        Lista de elementos con la forma:
        [
            {"page": 1, "text": "Texto de la página 1..."},
            {"page": 2, "text": "Texto de la página 2..."},
            ...
        ]
    """
    resultados = []

    # Abre el PDF
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            # Número de página humano (empieza en 1)
            page_number = i + 1

            # Extraer texto "normal"
            text = page.get_text("text")  # también vale page.get_text()

            resultados.append({
                "page": page_number,
                "text": text
            })

    return resultados


# -----------------------------
# OCR para PDFs escaneados
# -----------------------------
# Función para procesar una página del PDF

def _ocr_pagina_escritura_basico(args):
    pdf_path, page_number, lang, dpi, autoliquidacion = args

    # Cada proceso abre el PDF y carga su página
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=dpi)

    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageEnhance.Contrast(img).enhance(1.5)
    img = img.filter(ImageFilter.SHARPEN)


    ################################################
    if autoliquidacion==True:
        custom_oem_psm_config = r'--psm 4'

    else:
        custom_oem_psm_config = r'--psm 6'

    text = pytesseract.image_to_string(
        img,
        lang=lang,
        config=custom_oem_psm_config
    )

    return {
        "page": page_number + 1,
        "text": text
    }

# Función principal para OCR en PDF
def ocr_pdf(pdf_path: str, lang="spa", dpi: int = 300, use_multiprocessing: bool = True,autoliquidacion:bool=False):
    """
    OCR para Escritura.pdf

    Arguments
    ----------
    pdf_path: str
        ruta al archivo PDF.
    lang: str
        idioma para Tesseract (por defecto "spa" para español).
    dpi: int
        resolución para renderizar páginas (por defecto 300).
    use_multiprocessing: bool
        acelera procesando páginas en paralelo (por defecto True).
    autoliquidacion: bool
        si es True usa configuración específica para autoliquidaciones.
    
    Returns:
    ----------
    list[dict]
        Lista de diccionarios con 'page' y 'text' para cada página.
    """
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    args_list = [
        (pdf_path, i, lang, dpi,autoliquidacion)
        for i in range(total_pages)
    ]

    if use_multiprocessing:
        # Si quieres ir suave para no saturar CPU, puedes usar //2:
        # n_proc = max(1, cpu_count() // 2)
        workers = min(cpu_count(), total_pages)
        with ThreadPool(processes=workers) as pool:
            resultados = pool.map(_ocr_pagina_escritura_basico, args_list)

    else:
        # Modo secuencial
        resultados = []
        for args in args_list:
            resultados.append(_ocr_pagina_escritura_basico(args=args))

    # Orden por página por si acaso
    resultados.sort(key=lambda x: x["page"])
    return resultados



# -----------------------------
# Ejemplo de uso
# -----------------------------

if __name__ == "__main__":
    ruta_pdf_autoliquidacion = "Pdfs_prueba/Autoliquidacion.pdf"  # <<--- Cambia esto por tu PDF
    ruta_pdf_escritura = "Pdfs_prueba/Escritura.pdf"  # <<--- Cambia esto por tu PDF

    print("Procesando OCR...\n")

    resultados= leer_pdf_texto(ruta_pdf_escritura)
    for pagina in resultados:
        print(f"========== PÁGINA {pagina['page']} ==========")
        print(pagina["text"])
        print("\n")

    resultados = ocr_pdf(ruta_pdf_autoliquidacion, lang="spa",autoliquidacion=True,use_multiprocessing=True)  # spa = español
    for pagina in resultados:
        print(f"========== PÁGINA {pagina['page']} ==========")
        print(pagina["text"])
        print("\n")    