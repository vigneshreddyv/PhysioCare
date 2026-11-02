"""Production entry point; only an explicit process environment may configure it."""

import os

import uvicorn


def production_settings():
    if os.environ.get("ENVIRONMENT") != "production":
        raise SystemExit("Production launcher requires explicit ENVIRONMENT=production")

    from app.core.config import Settings

    configured = Settings(_env_file=None)
    configured.validate_runtime_startup()
    return configured


def main() -> None:
    configured = production_settings()
    uvicorn.run("app.main:app", host=configured.HOST, port=configured.PORT, reload=False)


if __name__ == "__main__":
    main()
