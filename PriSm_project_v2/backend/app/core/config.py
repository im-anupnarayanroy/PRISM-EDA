from pydantic import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "PriSm Analytics"
    DATA_PATH: str = "backend/data"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
