from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, HttpUrl, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    brand_name: str = Field(min_length=1, max_length=120)
    competitors: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("name", "brand_name")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("competitors")
    @classmethod
    def clean_competitors(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class SiteSummary(BaseModel):
    id: str
    name: str
    url: str
    brand_name: str
    competitors: list[str]
    latest_score: int | None = None
    latest_band: str | None = None
    created_at: str
    updated_at: str


class AuditSummary(BaseModel):
    id: str
    site_id: str
    score: int
    band: str
    http_status: int
    error: str | None = None
    score_breakdown: dict[str, int]
    recommendations_ja: list[str]
    created_at: str


class AuditDetail(AuditSummary):
    result: dict


class PromptCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value: str) -> str:
        return value.strip()


class PromptSummary(BaseModel):
    id: str
    site_id: str
    prompt: str
    active: bool
    created_at: str


class PromptRun(BaseModel):
    id: str
    prompt_id: str
    provider: str
    model: str
    brand_mentioned: bool
    domain_cited: bool
    citation_rank: int | None = None
    cited_urls: list[str]
    response_text: str
    evaluation_mode: str = "legacy-unverified"
    analysis: dict = Field(default_factory=dict)
    error: str | None = None
    created_at: str


class UsageStatus(BaseModel):
    plan: str
    month: str
    audits_used: int
    audits_limit: int | None
    monitor_runs_used: int
    monitor_runs_limit: int | None
    llm_configured: bool
