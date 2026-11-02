import uvicorn
import os
from dotenv import load_dotenv


def main() -> None:
    if os.getenv("ENVIRONMENT") not in (None, "development"):
        raise SystemExit("Development launcher requires ENVIRONMENT=development")
    load_dotenv()
    if os.getenv("ENVIRONMENT") != "development":
        raise SystemExit("Development launcher requires ENVIRONMENT=development")
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
