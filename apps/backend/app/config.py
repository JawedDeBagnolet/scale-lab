from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    api_secret: str
    fernet_key: str = ""  # Fernet key for creds encryption — generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
