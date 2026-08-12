from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "外贸与投资决策系统"
    app_version: str = "0.3.0"
    data_dir: Path = Path(__file__).resolve().parents[2] / "data"
    database_url: str | None = None
    demo_mode: bool = True

    model_config = SettingsConfigDict(env_prefix="FTDS_", env_file=".env", extra="ignore")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'decision_system.db').as_posix()}"


settings = Settings()
