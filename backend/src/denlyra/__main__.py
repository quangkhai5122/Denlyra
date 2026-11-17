"""Run only the synthetic localhost demo; never a public or production service."""
import uvicorn
from .config import Settings


def main():
    cfg = Settings.from_env()
    cfg.validate()
    uvicorn.run(create_app_string(), host=cfg.host, port=cfg.port, reload=False, access_log=False)


def create_app_string():
    return "denlyra.entrypoint:app"


if __name__ == "__main__":
    main()
