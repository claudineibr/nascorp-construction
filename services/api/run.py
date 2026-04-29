import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("CONSTRUCTION_API_HOST", "127.0.0.1")
    port = int(os.getenv("CONSTRUCTION_API_PORT", "8010"))
    reload_enabled = os.getenv("CONSTRUCTION_API_RELOAD", "true").lower() == "true"

    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload_enabled,
    )