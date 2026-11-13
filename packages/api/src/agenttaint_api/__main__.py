"""Run: python -m agenttaint_api — binds 0.0.0.0:$PORT for Render compatibility."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("agenttaint_api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
