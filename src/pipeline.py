from typing import Any, Callable, List
from decimal import Decimal
import logging
import sys
from tqdm import tqdm
from core.processing import process_pdf
from core.validation import validate_data, Escritura, Modelo600
from core.comparison import compare_escritura_with_tax_forms
from core.llm import extract_structured_data
from core.ocr import extract_pdf_text #  EX: resultados = ocr_pdf(ruta_pdf_autoliquidacion, lang="spa",autoliquidacion=True,use_multiprocessing=True)  # spa = español
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


# ===== MAP-REDUCE FUNCTIONS FOR CHUNK-BASED PROCESSING =====

def _hash_image(image) -> str:
    """Generate SHA256 hash of image content for caching"""
    import hashlib
    import io
    # Convert image to bytes
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    image_bytes = buffer.getvalue()
    return hashlib.sha256(image_bytes).hexdigest()

def map_ocr_chunks(image_chunks):
    """MAP: Apply OCR to each image chunk independently using gemma"""
    from core.ocr import ocr_chunk, Provier

    logger.info(f"MAP: OCRing {len(image_chunks)} image chunks")
    ocr_results = []

    for i, img in enumerate(tqdm(image_chunks, desc="OCR chunks", unit="chunk")):
        chunk_num = i + 1
        img_hash = _hash_image(img)
        cache_key = f"ocr_chunk_{img_hash}"

        # Try cache
        cached_text = cache.get(cache_key, img_hash)
        if cached_text is not None:
            logger.debug(f"Cache hit for chunk {chunk_num}")
            text = cached_text
        else:
            # Perform OCR
            logger.debug(f"Cache miss for chunk {chunk_num}, running OCR")
            text = ocr_chunk(img, provider=Provier.GEMMA)
            # Cache result
            cache.set(cache_key, img_hash, text)

        # save tmp image
        img.save(f"/tmp/chunk_{chunk_num}.png")
        with open(f"/tmp/chunk_{chunk_num}.txt", "w") as f:
            f.write(text)
        print(f"{len(text)} characters extracted from chunk {chunk_num}: path: {'/tmp/chunk_' + str(chunk_num) + '.png'}")
        ocr_results.append({"chunk": chunk_num, "text": text})

    logger.info(f"MAP: OCR completed for {len(ocr_results)} chunks")
    return ocr_results


def map_llm_extraction(ocr_results, model):
    """MAP: Extract structured data from each chunk's OCR text"""
    from core.llm import extract_from_chunk

    logger.info(f"MAP: Extracting structured data from {len(ocr_results)} chunks")
    partial_extractions = []

    # JSON encoder for Decimal objects
    def decimal_encoder(obj):
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    for result in tqdm(ocr_results, desc="LLM extraction per chunk", unit="chunk"):
        try:
            structured = extract_from_chunk(result['text'], model=model)
            partial_extractions.append(structured)
            with open(f"/tmp/chunk_{result['chunk']}_extracted.json", "w") as f:
                import json
                json.dump(structured.model_dump(), f, indent=2, ensure_ascii=False, default=decimal_encoder)
        except Exception as e:
            logger.warning(f"LLM extraction failed for chunk {result['chunk']}: {e}")
            # Add empty model
            partial_extractions.append(model.model_construct())

    logger.info(f"MAP: Extracted {len(partial_extractions)} partial results")
    return partial_extractions


def reduce_merge_extractions(partial_extractions, model):
    """REDUCE: Merge all partial extractions into single complete document"""
    from core.llm import merge_chunk_extractions

    logger.info(f"REDUCE: Merging {len(partial_extractions)} partial extractions")
    merged = merge_chunk_extractions(partial_extractions, model)
    print(merged)
    logger.info("REDUCE: Merge complete")
    return merged



# Initialize cache
cache = get_cache(
    ttl=86400,  # Cache for 24 hours
    enabled=True# Set to False to disable caching
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
    ocr_func = lambda path: extract_pdf_text(
        path,
        is_escritura=not autoliquidacion
    )[0]
    # Wrap with cache decorator
    cache_prefix = f"ocr_{'autoliq' if autoliquidacion else 'escritura'}"
    return cached_step(cache_prefix, cache)(ocr_func)

# Build cached LLM extraction function
def build_llm_function(model):
    llm_func = lambda pages_or_text: extract_structured_data(pages_or_text, model=model)
    cache_prefix = f"llm_{model.__name__}"
    return cached_step(cache_prefix, cache)(llm_func)

# Build cached validation function
@cached_step('validation', cache)
def cached_validate(data):
    return validate_data(data)

# OLD: Traditional pipelines (kept for reference/fallback)
extraction_pipeline_escritura = Pipeline()
extraction_pipeline_escritura.add(build_ocr_function(autoliquidacion=False))
extraction_pipeline_escritura.add(build_llm_function(Escritura))
extraction_pipeline_escritura.add(cached_validate)

extraction_pipeline_modelo600 = Pipeline()
extraction_pipeline_modelo600.add(build_ocr_function(autoliquidacion=True))
extraction_pipeline_modelo600.add(build_llm_function(Modelo600))
extraction_pipeline_modelo600.add(cached_validate)

# # NEW: Map-Reduce chunk-based pipelines
# extraction_pipeline_escritura = Pipeline()
# extraction_pipeline_escritura.add(process_pdf)  # PDF → image chunks
# extraction_pipeline_escritura.add(map_ocr_chunks)  # MAP: chunks → OCR texts
# extraction_pipeline_escritura.add(partial(map_llm_extraction, model=Escritura))  # MAP: texts → partial JSONs
# extraction_pipeline_escritura.add(partial(reduce_merge_extractions, model=Escritura))  # REDUCE: merge JSONs
# extraction_pipeline_escritura.add(cached_validate)  # Validate final result

# extraction_pipeline_modelo600 = Pipeline()
# extraction_pipeline_modelo600.add(process_pdf)  # PDF → image chunks
# extraction_pipeline_modelo600.add(map_ocr_chunks)  # MAP: chunks → OCR texts
# extraction_pipeline_modelo600.add(partial(map_llm_extraction, model=Modelo600))  # MAP: texts → partial JSONs
# extraction_pipeline_modelo600.add(partial(reduce_merge_extractions, model=Modelo600))  # REDUCE: merge JSONs
# extraction_pipeline_modelo600.add(cached_validate)  # Validate final result

comparison_pipeline = Pipeline()
comparison_pipeline.add(compare_escritura_with_tax_forms)




if __name__ == "__main__":
    # TODO: Modifica para que lea los pdfs de una carpeta en tu sistema
    escritura_pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Escritura.pdf"
    modelo600_pdf_path = "/home/velocitatem/Documents/Projects/accenture_mavericks/Pdfs_prueba/Autoliquidacion.pdf"
    tax_forms_extract = extraction_pipeline_modelo600.run(modelo600_pdf_path)
    escritura_extract = extraction_pipeline_escritura.run(escritura_pdf_path)

    # Convert Pydantic models to dicts for comparison
    escritura_dict = escritura_extract.model_dump() if hasattr(escritura_extract, 'model_dump') else escritura_extract
    tax_forms_dict = tax_forms_extract.model_dump() if hasattr(tax_forms_extract, 'model_dump') else tax_forms_extract

    # Custom JSON encoder to handle Decimal objects
    def decimal_encoder(obj):
        if isinstance(obj, Decimal):
            return str(obj)  # Convert Decimal to string to preserve precision
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    with open("escritura_extracted.json", "w") as f:
        import json
        json.dump(escritura_dict, f, indent=2, ensure_ascii=False, default=decimal_encoder)
    with open("modelo600_extracted.json", "w") as f:
        import json
        json.dump(tax_forms_dict, f, indent=2, ensure_ascii=False, default=decimal_encoder)

    comparison_report = comparison_pipeline.run({
        'escrituras': [escritura_dict],
        'tax_forms': [tax_forms_dict],
    })

    logger.info(f"Comparison complete: {len(comparison_report)} reports")
    for r in comparison_report:
        logger.info(f"{r['property_id']}: {r['status']} ({len(r['issues'])} issues)")
        print(r['issues'])
