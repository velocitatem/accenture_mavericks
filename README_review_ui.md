# Review Cockpit UI

A Streamlit interface for reviewing Escritura and Modelo 600 PDFs, running the existing OCR/LLM/validation pipelines, and producing an audit report.

## Run locally

```bash
pip install -r requirements.txt
streamlit run src/app.py
```

Sample docs for demo mode live at `/mnt/data/Escritura (1).pdf` and `/mnt/data/Autoliquidacion (1).pdf`.

Environment variables for OCR/LLM providers follow the existing backend expectations.
