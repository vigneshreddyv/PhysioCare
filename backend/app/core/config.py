from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "PhysioCare Pro API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Backend API for PhysioCare Pro"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "physiocare_db"

    SECRET_KEY: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()