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

### Using a local LLM with Ollama (no OpenAI key required)
1. Install Ollama from https://ollama.com/download or with the official script:
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
2. Start the Ollama service (it auto-starts after install on most platforms) and pull a model:
   ```bash
   ollama pull llama3   # or any model you prefer
   ```
3. Run the UI pointing at the local model:
   ```bash
   LLM_PROVIDER=ollama OLLAMA_MODEL=llama3 ./scripts/run_local.sh
   ```

If `LLM_PROVIDER` is unset, the app will automatically fall back to Ollama whenever `OPENAI_API_KEY` is missing.
