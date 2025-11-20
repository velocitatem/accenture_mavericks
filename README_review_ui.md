# Review Cockpit UI

A Streamlit interface for reviewing Escritura and Modelo 600 PDFs, running the existing OCR/LLM/validation pipelines, and producing an audit report.

## Run locally (no Docker required)
The repo ships a helper script that bootstraps a virtualenv, installs dependencies, and launches Streamlit. Redis is optional; caching disables itself if Redis is missing.

```bash
# from the repository root
./scripts/run_local.sh
```

Environment variables you can override:
- `PYTHON_BIN` (default: `python3`)
- `PORT` (default: `8501`)
- `ADDRESS` (default: `0.0.0.0`)
- `REDIS_HOST` / `REDIS_PORT` for a running Redis instance (optional)

If you prefer manual steps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run src/app.py --server.address=0.0.0.0 --server.port=8501
```

Sample docs for demo mode live at `/mnt/data/Escritura (1).pdf` and `/mnt/data/Autoliquidacion (1).pdf`.

Environment variables for OCR/LLM providers follow the existing backend expectations.
