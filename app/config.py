
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_KEY: str = "dev-secret"
    ALLOWED_ORIGINS: str = "*"

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "adilai"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    # LLM provider selection: "perplexity" or "openai"
    LLM_PROVIDER: str = "perplexity"

    # Perplexity (chat) settings
    PERPLEXITY_API_KEY: str = ""
    PERPLEXITY_MODEL: str = "llama-3.1-sonar-small-128k-chat"
    LLM_PREFER_CHEAPEST: bool = True

    # OpenAI (legacy or for embeddings/chat if selected)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    EMBED_DIM: int = 1536

    # Ngrok token (used only by docker-compose service)
    NGROK_AUTHTOKEN: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
