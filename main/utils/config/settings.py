from pathlib import Path
from typing import List
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    bot_token: SecretStr

    db_path_accountant: Path
    db_path_pharmacy: Path
    db_path_reports: Path

    admin_ids: List[int]

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

config = Settings()