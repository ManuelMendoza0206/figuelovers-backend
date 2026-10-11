from pydantic import ConfigDict as SettingsConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Graph Editor API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Orígenes permitidos para Frontend (React)
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # Pydantic v2: `class Config` esta deprecado. `model_config` debe ir
    # a nivel de la clase, no anidado dentro de `class Config` (eso era
    # inerte y el warning PydanticDeprecatedSince20 seguia apareciendo).
    model_config = SettingsConfigDict(case_sensitive=True, extra="ignore")


settings = Settings()