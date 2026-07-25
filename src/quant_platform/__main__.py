"""Entry point — python -m quant_platform"""

import uvicorn
from .config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "quant_platform.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.run_mode.value == "local",
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
