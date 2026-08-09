from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-only-insecure-secret-change-me"
    database_url: str = "sqlite:///./app.db"
    anthropic_api_key: str = ""
    access_token_expire_minutes: int = 60 * 24

    # Comma-separated list of browser origins allowed to call this API.
    # Local dev works out of the box; set CORS_ORIGINS in the deployed
    # environment to your frontend's URL (e.g. https://planwise.vercel.app).
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
