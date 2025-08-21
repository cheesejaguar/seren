from pydantic import BaseModel
from typing import Literal

class Settings(BaseModel):
    """
    Global settings for quickstarts and CLI defaults.
    """
    problem: str = "Build a Slack summarizer bot"
    budget_soft_cap_usd: float = 80.0
    budget_hard_cap_usd: float = 100.0
    budget_policy: Literal["CONSERVATIVE", "BALANCED", "AGGRESSIVE"] = "BALANCED"
    model_hint: str | None = None

def default_settings() -> "Settings":
    return Settings()
