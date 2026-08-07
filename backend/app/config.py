from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-only-insecure-secret-change-me"
    database_url: str = "sqlite:///./app.db"
    anthropic_api_key: str = ""
    access_token_expire_minutes: int = 60 * 24

    class Config:
        env_file = ".env"


settings = Settings()
