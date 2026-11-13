"""Run: python -m agenttaint_api.

Defaults to loopback (127.0.0.1) for local-first safety.
Set HOST=0.0.0.0 for Render / container deploy port binding.
"""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("agenttaint_api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
