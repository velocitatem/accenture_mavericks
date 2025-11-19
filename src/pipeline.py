from typing import Any, Callable, List
from decimal import Decimal
import logging
import sys
from tqdm import tqdm
from core.processing import process_pdf
from core.validation import validate_data, Escritura, Modelo600
from core.comparison import compare_escritura_with_tax_forms
from core.llm import extract_structured_data
from core.ocr import ocr_pdf #  EX: resultados = ocr_pdf(ruta_pdf_autoliquidacion, lang="spa",autoliquidacion=True,use_multiprocessing=True)  # spa = español
from core.cache import get_cache, cached_step
from functools import partial

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)
logger = logging.getLogger("pipeline")


class Pipeline: # simpler than an sklearn pipeline which is a bit too inflexible for our needs
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

    # Initialize cache
    cache = get_cache(
        ttl=86400,  # Cache for 24 hours
        enabled=True  # Set to False to disable caching
    )
    logger.info(f"Cache initialized: enabled={cache.enabled}")

    # For each pdf we get a list of strings for each page
    # We pass concat(pages) to the llm to extract structured data
    # we validate the structured data
    OCR_METHOD = "classic"  # "classic" or "ollama"
    OCR_MULTIPROCESSING = True
    OCR_USE_CLOUD = True
    OLLAMA_MODEL = "qwen3-vl:235b-cloud" if OCR_USE_CLOUD else "qwen3-vl:8b"

    # Build cached OCR function
    def build_ocr_function(autoliquidacion: bool):
        # OCR configuration is now handled via environment variables in src/core/ocr.py
        # We just need to pass the essential flags
        ocr_func = lambda path: ocr_pdf(
            path,
            lang="spa",
            autoliquidacion=autoliquidacion,
            use_multiprocessing=OCR_MULTIPROCESSING
        )
        # Wrap with cache decorator
        cache_prefix = f"ocr_{'autoliq' if autoliquidacion else 'escritura'}"
        return cached_step(cache_prefix, cache)(ocr_func)

    # Build cached LLM extraction function
    def build_llm_function(model):
        llm_func = lambda pages: extract_structured_data(pages, model=model)
        cache_prefix = f"llm_{model.__name__}"
        return llm_func
        return cached_step(cache_prefix, cache)(llm_func)

    # Build cached validation function
    @cached_step('validation', cache)
    def cached_validate(data):
        return validate_data(data)

    extraction_pipeline_escritura = Pipeline()
    extraction_pipeline_escritura.add(process_pdf)
    extraction_pipeline_escritura.add(build_ocr_function(autoliquidacion=False))
    extraction_pipeline_escritura.add(build_llm_function(Escritura))
    extraction_pipeline_escritura.add(cached_validate)

    extraction_pipeline_modelo600 = Pipeline()
    extraction_pipeline_modelo600.add(process_pdf)
    extraction_pipeline_modelo600.add(build_ocr_function(autoliquidacion=True))
    extraction_pipeline_modelo600.add(build_llm_function(Modelo600))
    extraction_pipeline_modelo600.add(cached_validate)

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

    with open("escritura_extracted.json", "w") as f:
        import json
        json.dump(escritura_dict, f, indent=2, ensure_ascii=False)
    with open("modelo600_extracted.json", "w") as f:
        import json
        json.dump(tax_forms_dict, f, indent=2, ensure_ascii=False)

    comparison_report = comparison_pipeline.run({
        'escrituras': [escritura_dict],
        'tax_forms': [tax_forms_dict],
    })

    logger.info(f"Comparison complete: {len(comparison_report)} reports")
    for r in comparison_report:
        logger.info(f"{r['property_id']}: {r['status']} ({len(r['issues'])} issues)")
        print(r['issues'])
