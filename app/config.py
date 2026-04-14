import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Nutrition & Recipe Analytics API"
    app_version: str = "1.0.0"
    debug: bool = False

    @property
    def resolved_database_url(self) -> str:
        if self.database_url != "":
            return self.database_url
        # Auto-detect: prefer full DB, fall back to demo DB
        base = os.path.dirname(os.path.dirname(__file__))
        full = os.path.join(base, "nutrition.db")
        demo = os.path.join(base, "nutrition_demo.db")
        return f"sqlite:///{full}" if os.path.exists(full) else f"sqlite:///{demo}"

    database_url: str = ""

    secret_key: str = "change-me-in-production-use-a-long-random-string"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    off_api_base: str = "https://world.openfoodfacts.org/api/v2"
    off_search_url: str = "https://world.openfoodfacts.org/cgi/search.pl"

    class Config:
        env_file = ".env"


settings = Settings()
