from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_ENTRYPOINT = BACKEND_DIR / "main.py"


def _load_backend_app():
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    spec = importlib.util.spec_from_file_location(
        "nova_backend_main",
        BACKEND_ENTRYPOINT,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load backend app from {BACKEND_ENTRYPOINT}")

    backend_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend_module)
    return backend_module.app


app = _load_backend_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )
