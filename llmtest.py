from ollama import chat
import logging
import os
logger = logging.getLogger("llm")


def test_ollama_gemma3(timeout: int = 10) -> str:
    """
    Small smoke test to call the local Ollama model gemma3:1b.
    Returns the model's raw content string (or raises on error).
    """
    try:
        model_name = os.getenv("OLLAMA_MODEL", "gemma3:1b")
        logger.info("Running Ollama smoke test against model: %s", model_name)

        response = chat(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a minimal test agent."},
                {"role": "user", "content": "how are you doing?"}
            ],
            options={"temperature": 0.0},
        )

        # Normalize response extraction (dict or object)
        content = ""
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        else:
            content = getattr(getattr(response, "message", None), "content", "")

        logger.info("Ollama smoke test response: %s", content)
        print("Ollama smoke test response:", content)
        return content

    except Exception as exc:
        logger.error("Ollama smoke test failed: %s", exc)
        raise

if __name__ == "__main__":
    test_ollama_gemma3()
