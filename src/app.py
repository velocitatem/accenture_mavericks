import streamlit as st
import tempfile
from decimal import Decimal
from pipeline import Pipeline, get_cache, cached_step
from core.processing import process_pdf
from core.validation import validate_data, Escritura, Modelo600
from core.comparison import compare_escritura_with_tax_forms
from core.llm import extract_structured_data
from core.ocr import extract_pdf_text

# Initialize cache
cache = get_cache(ttl=86400, enabled=True)

# Build cached functions
def build_ocr_function(autoliquidacion: bool):
    ocr_func = lambda path: extract_pdf_text(path, is_escritura=not autoliquidacion)[0]
    cache_prefix = f"ocr_{'autoliq' if autoliquidacion else 'escritura'}"
    return cached_step(cache_prefix, cache)(ocr_func)

def build_llm_function(model):
    llm_func = lambda pages_or_text: extract_structured_data(pages_or_text, model=model)
    cache_prefix = f"llm_{model.__name__}"
    return cached_step(cache_prefix, cache)(llm_func)

cached_validate = cached_step('validation', cache)(validate_data)

# Build pipelines
extraction_pipeline_escritura = Pipeline()
extraction_pipeline_escritura.add(build_ocr_function(autoliquidacion=False))
extraction_pipeline_escritura.add(build_llm_function(Escritura))
extraction_pipeline_escritura.add(cached_validate)

extraction_pipeline_modelo600 = Pipeline()
extraction_pipeline_modelo600.add(build_ocr_function(autoliquidacion=True))
extraction_pipeline_modelo600.add(build_llm_function(Modelo600))
extraction_pipeline_modelo600.add(cached_validate)

comparison_pipeline = Pipeline()
comparison_pipeline.add(compare_escritura_with_tax_forms)

st.title("Document Validation Pipeline")
st.caption(f"Cache: {'Enabled' if cache.enabled else 'Disabled'} | TTL: {cache.ttl}s")

# File uploaders
escritura_file = st.file_uploader("Upload Escritura PDF", type="pdf")
modelo600_file = st.file_uploader("Upload Modelo 600 PDF", type="pdf")

if st.button("Run Pipeline") and escritura_file and modelo600_file:
    with st.spinner("Processing documents..."):
        # Save uploaded files to temp paths
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_escritura:
            tmp_escritura.write(escritura_file.read())
            escritura_path = tmp_escritura.name

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_modelo:
            tmp_modelo.write(modelo600_file.read())
            modelo_path = tmp_modelo.name

        # Run pipelines
        escritura_extract = extraction_pipeline_escritura.run(escritura_path)
        modelo_extract = extraction_pipeline_modelo600.run(modelo_path)

        # Convert to dicts
        escritura_dict = escritura_extract.model_dump() if hasattr(escritura_extract, 'model_dump') else escritura_extract
        modelo_dict = modelo_extract.model_dump() if hasattr(modelo_extract, 'model_dump') else modelo_extract

        # Run comparison
        comparison_report = comparison_pipeline.run({
            'escrituras': [escritura_dict],
            'tax_forms': [modelo_dict],
        })

        # Display results
        st.success("Processing complete!")

        st.subheader("Escritura Extraction")
        st.json(escritura_dict)

        st.subheader("Modelo 600 Extraction")
        st.json(modelo_dict)

        st.subheader("Comparison Report")
        for report in comparison_report:
            st.write(f"**Property ID**: {report['property_id']}")
            st.write(f"**Status**: {report['status']}")
            if report['issues']:
                st.warning(f"Found {len(report['issues'])} issues:")
                for issue in report['issues']:
                    st.write(f"- {issue}")
            else:
                st.success("No issues found")
