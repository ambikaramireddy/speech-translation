from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    audiclabs_api_key: str = ""
    audiclabs_base_url: str = "https://api.audiclabs.com/v1"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    translator_backend: str = "gemini"
    max_upload_mb: int = 100
    cache_db: Path = Path("./data/cache.sqlite3")
    audio_dir: Path = Path("./data/audio")
    job_db: Path = Path("./data/jobs.sqlite3")
    lookup_cache_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings() -> Settings:
    return Settings()
