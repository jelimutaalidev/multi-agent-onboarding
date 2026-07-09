"""
CLI entry point untuk menjalankan FastAPI server.

Contoh:
    python api.py
    python api.py --host 0.0.0.0 --port 8080
"""

import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("HUGGINGFACEHUB_API_TOKEN", "")  # Will load from .env

if __name__ == "__main__":
    import uvicorn

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    print(f"[API] Starting server at http://{host}:{port}")
    print("[API] Docs at http://{host}:{port}/docs")
    uvicorn.run("src.api:app", host=host, port=port, reload=True)
