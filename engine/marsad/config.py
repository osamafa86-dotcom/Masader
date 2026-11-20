"""Runtime settings, read from environment variables prefixed with MARSAD_."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MARSAD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://marsad:marsad@localhost:5432/marsad"
    storage_dir: str = "./storage"

    # Site policy
    site_name: str = "مرصد"
    site_url: str = "http://localhost:3000"
    site_commercial: bool = False
    contact_email: str = "editor@example.org"

    # HTTP politeness
    user_agent: str = "MarsadBot/0.1 (+{site_url}; {contact_email})"
    per_host_delay_s: float = 5.0
    http_timeout_s: float = 30.0

    # AI
    llm_backend: str = "anthropic"  # "anthropic" | "fake"
    model_translate: str = "claude-opus-5-5"
    model_summarize: str = "claude-opus-5-5"
    model_classify: str = "claude-haiku-5-5"
    model_judge: str = "claude-sonnet-5-5"
    effort_translate: str = "medium"
    effort_classify: str = "low"
    qa_llm_judge: bool = False
    chunk_words: int = 1800
    daily_budget_usd: float = 15.0

    # Editorial policy
    review_min_importance: int = 3
    auto_publish: bool = False
    max_quote_words: int = 150

    # Worker
    worker_interval_s: int = 60
    worker_batch: int = 5

    def resolved_user_agent(self) -> str:
        return self.user_agent.format(site_url=self.site_url, contact_email=self.contact_email)


@lru_cache
def get_settings() -> Settings:
    return Settings()
