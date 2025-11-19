from typing import Any, Callable, List
from decimal import Decimal
import logging
import sys
from tqdm import tqdm
from core.validation import validate_data, Escritura, Modelo600
from core.comparison import compare_escritura_with_tax_forms
from core.llm import extract_structured_data
from core.ocr import ocr_pdf #  EX: resultados = ocr_pdf(ruta_pdf_autoliquidacion, lang="spa",autoliquidacion=True,use_multiprocessing=True)  # spa = español
from functools import partial

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("pipeline")


text = """
------------------ COMPRA-VENTA ------------------

NÚMERO MIL TRESCIENTOS TREINTA Y UNO (1.331) EN MADRID, mi residencia, a diez de febrero de dos mil veinticinco. ----------------------

Ante mí, RICARDO GÓMEZ HERNÁNDEZ, Notario del Ilustre Colegio de Madrid, --------------------

------------- C O M P A R E C E N -------------

DE UNA PARTE, COMO VENDEDORES: ----------------

DOÑA LUCÍA MARTÍNEZ GARCÍA, mayor de edad, soltera, empleada, de vecindad civil madrileña, vecina de ALCOBENDAS (Madrid), con domicilio en la calle Falsa, número 4, con D.N.I. número 12345678B. ----------------

DON CARLOS LÓPEZ MARTÍNEZ, Profesor, y DOÑA ANA PÉREZ RODRÍGUEZ, Arquitecta, casados en régimen de gananciales, mayores de edad, de vecindad civil madrileña, vecinos de ALCOBENDAS (Madrid), con domicilio en la Avenida Imaginaria, número 67, escalera
    """



class Pipeline:
    """Simple AI processing pipeline."""

    def __init__(self):
        self.steps: List[Callable] = []

    def add(self, func: Callable):
        self.steps.append(func)
        return self

    def run(self, data: Any) -> Any:
        logger.info(f"Starting pipeline with {len(self.steps)} steps")
        for step in tqdm(self.steps, desc="Pipeline", unit="step"):
            step_name = step.__name__ if hasattr(step, '__name__') else str(step)
            logger.debug(f"Executing step: {step_name}")
            try:
                data = step(data)
                logger.debug(f"Step {step_name} completed")
            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                raise
        logger.info("Pipeline completed")
        return data



def ocr_wrapper_for_extraction(pdf_path: str) -> str:
    pages = ocr_pdf(pdf_path, lang="spa", autoliquidacion=False, use_multiprocessing=True)
    concatenated_text = "\n".join(page['text'] for page in pages)
    return concatenated_text


if __name__ == "__main__":

    # For each pdf we get a list of strings for each page
    # We pass concat(pages) to the llm to extract structured data
    # we validate the structured data
    OCR_METHOD = "classic"  # "classic" or "ollama"
    OCR_MULTIPROCESSING = True
    OCR_USE_CLOUD = True
    OLLAMA_MODEL = "qwen3-vl:235b-cloud" if OCR_USE_CLOUD else "qwen3-vl:8b"

    # Build OCR function based on method
    def build_ocr_function(autoliquidacion: bool):
        # OCR configuration is now handled via environment variables in src/core/ocr.py
        # We just need to pass the essential flags
        return lambda path: ocr_pdf(
            path,
            lang="spa",
            autoliquidacion=autoliquidacion,
            use_multiprocessing=OCR_MULTIPROCESSING
        )

    extraction_pipeline_escritura = Pipeline()
    extraction_pipeline_escritura.add(build_ocr_function(autoliquidacion=False))
    extraction_pipeline_escritura.add(lambda pages: extract_structured_data(pages, model=Escritura))
    extraction_pipeline_escritura.add(validate_data)

    extraction_pipeline_modelo600 = Pipeline()
    extraction_pipeline_modelo600.add(build_ocr_function(autoliquidacion=True))
    extraction_pipeline_modelo600.add(lambda pages: extract_structured_data(pages, model=Modelo600))
    extraction_pipeline_modelo600.add(validate_data)

    comparison_pipeline = Pipeline()
    comparison_pipeline.add(compare_escritura_with_tax_forms)


    # TODO: Modifica para que lea los pdfs de una carpeta en tu sistema
    escritura_pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Escritura.pdf"
    modelo600_pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Autoliquidacion.pdf"


    escritura_extract = extraction_pipeline_escritura.run(escritura_pdf_path)
    tax_forms_extract = extraction_pipeline_modelo600.run(modelo600_pdf_path)

    # Convert Pydantic models to dicts for comparison
    escritura_dict = escritura_extract.model_dump() if hasattr(escritura_extract, 'model_dump') else escritura_extract
    tax_forms_dict = tax_forms_extract.model_dump() if hasattr(tax_forms_extract, 'model_dump') else tax_forms_extract

    comparison_report = comparison_pipeline.run({
        'escrituras': [escritura_dict],
        'tax_forms': [tax_forms_dict],
    })

    logger.info(f"Comparison complete: {len(comparison_report)} reports")
    for r in comparison_report:
        logger.info(f"{r['property_id']}: {r['status']} ({len(r['issues'])} issues)")
        print(r['issues'])
