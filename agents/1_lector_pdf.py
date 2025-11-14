from pypdf import PdfReader
from typing import List, Dict


def extraer_texto_por_pagina(pdf_path: str) -> List[Dict[str, str]]:
    """
    Lee un PDF y devuelve una lista de diccionarios con:
    - 'pagina': número de página (empieza en 1)
    - 'texto': texto extraído de esa página
    """
    reader = PdfReader(pdf_path)
    resultado = []

    for num_pagina, page in enumerate(reader.pages, start=1):
        texto = page.extract_text() or ""  # por si alguna página viene como None
        resultado.append({
            "pagina": num_pagina,
            "texto": texto
        })

    return resultado


def leer_dos_pdfs(pdf1_path: str, pdf2_path: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Lee dos PDFs y devuelve un diccionario con la info separada:

    {
        "pdf1": [
            {"pagina": 1, "texto": "..."},
            {"pagina": 2, "texto": "..."},
            ...
        ],
        "pdf2": [
            {"pagina": 1, "texto": "..."},
            {"pagina": 2, "texto": "..."},
            ...
        ]
    }
    """
    pdf1_paginas = extraer_texto_por_pagina(pdf1_path)
    pdf2_paginas = extraer_texto_por_pagina(pdf2_path)

    return {
        "pdf1": pdf1_paginas,
        "pdf2": pdf2_paginas,
    }


if __name__ == "__main__":
    # Ejemplo de uso
    autoliquidacion_pdf = "../Pdfs_prueba/Autoliquidacion.pdf"
    escritura_pdf = "../Pdfs_prueba/Escritura.pdf"

    datos = leer_dos_pdfs(autoliquidacion_pdf, escritura_pdf)

    # Mostrar un ejemplo de salida
    print("=== PDF 1 ===")
    for pagina in datos["pdf1"]:
        print(f"\n--- Página {pagina['pagina']} ---")
        print(pagina["texto"][:500])  # solo los primeros 500 caracteres

    print("\n\n=== PDF 2 ===")
    for pagina in datos["pdf2"]:
        print(f"\n--- Página {pagina['pagina']} ---")
        print(pagina["texto"][:500])


