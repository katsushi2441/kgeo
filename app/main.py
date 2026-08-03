from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, audit_service, config, db, monitor_service, report
from .models import (
    AuditDetail,
    AuditSummary,
    PromptCreate,
    PromptRun,
    PromptSummary,
    SiteCreate,
    SiteSummary,
    UsageStatus,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Kurage GEO API",
    description="日本語GEO技術監査とAI検索可視性モニタリング",
    version=__version__,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
logger = logging.getLogger("kgeo")
audit_locks: dict[str, asyncio.Lock] = {}
monitor_locks: dict[str, asyncio.Lock] = {}


def _valid_username(value: str) -> bool:
    return bool(value) and len(value) <= 200 and not any(ord(char) < 32 for char in value)


def is_admin(username: str) -> bool:
    return monitor_service.normalize_owner(username) in config.ADMIN_USERS


def authenticated_owner(
    x_kgeo_token: str = Header(default=""),
    x_kgeo_user: str = Header(default=""),
    x_kgeo_act_as: str = Header(default=""),
) -> str:
    """操作対象のオーナー。管理者だけ X-KGeo-Act-As で代理操作できる。

    利用者が詰まったときに運営が直接手当てするためのもの。管理者以外が
    ヘッダを付けても無視せず403にする(黙って自分のデータを操作すると、
    代理できたと誤解したまま作業が進む)。
    """
    if not config.INTERNAL_TOKEN:
        return config.DEV_USER
    if not x_kgeo_token or not hmac.compare_digest(x_kgeo_token, config.INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid internal token")
    owner = x_kgeo_user.strip()
    if not _valid_username(owner):
        raise HTTPException(status_code=401, detail="Authenticated user is required")
    act_as = x_kgeo_act_as.strip()
    if not act_as or act_as == owner:
        return owner
    if not is_admin(owner):
        raise HTTPException(status_code=403, detail="代理操作は管理者のみ利用できます")
    if not _valid_username(act_as):
        raise HTTPException(status_code=400, detail="代理操作の対象ユーザーが不正です")
    logger.info("admin %s acting as %s", owner, act_as)
    return act_as


def usage_status(owner: str) -> UsageStatus:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    plan = db.get_plan(owner)
    admin = is_admin(owner)
    unlimited = admin or plan != "free"
    monitor_used = db.monthly_usage(owner, "monitor", month)
    next_run_is_free = unlimited or monitor_used < config.FREE_MONITOR_RUNS_PER_MONTH
    return UsageStatus(
        plan="admin" if admin else plan,
        month=month,
        audits_used=db.monthly_usage(owner, "audit", month),
        # Audit charging is enforced by the public X-authenticated PHP gateway.
        # The FastAPI token is trusted internal traffic and must not apply a
        # second monthly limit after a paid diagnosis has been authorized.
        audits_limit=None,
        monitor_runs_used=monitor_used,
        monitor_runs_limit=None if unlimited else config.FREE_MONITOR_RUNS_PER_MONTH,
        # 次の1回が無料枠に収まるかで、どちらのLLMの設定を見るかが変わる
        llm_configured=monitor_service.configured(owner, paid=not next_run_is_free),
    )


def enforce_limit(owner: str, kind: str) -> None:
    if kind == "audit":
        return
    status = usage_status(owner)
    used = status.audits_used if kind == "audit" else status.monitor_runs_used
    limit = status.audits_limit if kind == "audit" else status.monitor_runs_limit
    if limit is not None and used >= limit:
        raise HTTPException(status_code=429, detail=f"FREE_{kind.upper()}_LIMIT_REACHED")


def within_free_quota(owner: str, kind: str) -> bool:
    """この実行が無料枠に収まるか。収まるならローカルGemma、超えたらDeepSeek。

    管理者は limit=None(無制限)なので常に無料扱い＝Gemma。
    """
    status = usage_status(owner)
    if kind != "monitor":
        return True                      # 監査の課金はPHPゲートウェイ側で判定する
    limit = status.monitor_runs_limit
    return limit is None or status.monitor_runs_used < limit


def require_site(owner: str, site_id: str) -> dict:
    site = db.get_site(owner, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@app.get("/", response_class=FileResponse)
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/health")
def health(owner: str = Depends(authenticated_owner)) -> dict:
    return {
        "ok": True,
        "service": "kgeo",
        "version": __version__,
        "authenticated": bool(owner),
        "llm_configured": monitor_service.configured(owner),
    }


@app.get("/api/admin/users")
def admin_users(
    x_kgeo_token: str = Header(default=""),
    x_kgeo_user: str = Header(default=""),
) -> dict:
    """代理操作の対象にできる利用者の一覧。管理者専用・読み取りのみ。"""
    if config.INTERNAL_TOKEN:
        if not x_kgeo_token or not hmac.compare_digest(x_kgeo_token, config.INTERNAL_TOKEN):
            raise HTTPException(status_code=401, detail="Invalid internal token")
        if not is_admin(x_kgeo_user.strip()):
            raise HTTPException(status_code=403, detail="管理者のみ利用できます")
    return {"users": db.list_owners()}


@app.get("/api/usage", response_model=UsageStatus)
def get_usage(owner: str = Depends(authenticated_owner)) -> UsageStatus:
    return usage_status(owner)


@app.get("/api/sites", response_model=list[SiteSummary])
def sites(owner: str = Depends(authenticated_owner)) -> list[SiteSummary]:
    return [SiteSummary.model_validate(row) for row in db.list_sites(owner)]


@app.post("/api/sites", response_model=SiteSummary)
def new_site(payload: SiteCreate, owner: str = Depends(authenticated_owner)) -> SiteSummary:
    if len(db.list_sites(owner)) >= config.MAX_SITES_PER_USER:
        raise HTTPException(status_code=429, detail="SITE_LIMIT_REACHED")
    try:
        audit_service.validate_target(str(payload.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe URL: {exc}") from exc
    return SiteSummary.model_validate(db.create_site(owner, payload))


@app.get("/api/sites/{site_id}", response_model=SiteSummary)
def site(site_id: str, owner: str = Depends(authenticated_owner)) -> SiteSummary:
    return SiteSummary.model_validate(require_site(owner, site_id))


@app.get("/api/sites/{site_id}/audits", response_model=list[AuditSummary])
def audits(site_id: str, owner: str = Depends(authenticated_owner)) -> list[AuditSummary]:
    require_site(owner, site_id)
    return [AuditSummary.model_validate(row) for row in db.list_audits(owner, site_id)]


@app.post("/api/sites/{site_id}/audits", response_model=AuditDetail)
async def new_audit(site_id: str, owner: str = Depends(authenticated_owner)) -> AuditDetail:
    target = require_site(owner, site_id)
    lock = audit_locks.setdefault(owner, asyncio.Lock())
    async with lock:
        enforce_limit(owner, "audit")
        try:
            result = await asyncio.to_thread(audit_service.run_audit, target["url"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsafe URL: {exc}") from exc
        recommendations = audit_service.japanese_recommendations(result)
        return AuditDetail.model_validate(db.save_audit(owner, site_id, result, recommendations))


@app.get("/api/audits/{audit_id}", response_model=AuditDetail)
def audit(audit_id: str, owner: str = Depends(authenticated_owner)) -> AuditDetail:
    row = db.get_audit(owner, audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    return AuditDetail.model_validate(row)


def _report_row(audit_id: str, owner: str) -> dict:
    row = db.get_audit(owner, audit_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit not found")
    return row


@app.get("/api/audits/{audit_id}/report.md")
def audit_report_markdown(
    audit_id: str, lang: str = "ja", owner: str = Depends(authenticated_owner)
) -> Response:
    """監査結果をMarkdownでダウンロードする。"""
    row = _report_row(audit_id, owner)
    text = report.build_markdown(row, lang)
    stem = report.filename_stem(row)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.md"'},
    )


@app.get("/api/audits/{audit_id}/report.pdf")
def audit_report_pdf(
    audit_id: str, lang: str = "ja", owner: str = Depends(authenticated_owner)
) -> Response:
    """監査結果をPDFでダウンロードする。"""
    row = _report_row(audit_id, owner)
    pdf = report.build_pdf(row, lang)
    stem = report.filename_stem(row)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{stem}.pdf"'},
    )


@app.get("/api/sites/{site_id}/prompts", response_model=list[PromptSummary])
def prompts(site_id: str, owner: str = Depends(authenticated_owner)) -> list[PromptSummary]:
    require_site(owner, site_id)
    return [PromptSummary.model_validate(row) for row in db.list_prompts(owner, site_id)]


@app.post("/api/sites/{site_id}/prompts", response_model=PromptSummary)
def new_prompt(
    site_id: str, payload: PromptCreate, owner: str = Depends(authenticated_owner)
) -> PromptSummary:
    require_site(owner, site_id)
    return PromptSummary.model_validate(db.create_prompt(owner, site_id, payload.prompt))


@app.get("/api/prompts/{prompt_id}/runs", response_model=list[PromptRun])
def prompt_runs(prompt_id: str, owner: str = Depends(authenticated_owner)) -> list[PromptRun]:
    if not db.get_prompt(owner, prompt_id):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return [PromptRun.model_validate(row) for row in db.list_prompt_runs(owner, prompt_id)]


@app.post("/api/prompts/{prompt_id}/runs", response_model=PromptRun)
async def new_prompt_run(prompt_id: str, owner: str = Depends(authenticated_owner)) -> PromptRun:
    prompt = db.get_prompt(owner, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    site_row = require_site(owner, prompt["site_id"])
    lock = monitor_locks.setdefault(owner, asyncio.Lock())
    async with lock:
        enforce_limit(owner, "monitor")
        # 無料枠の実行は自社GPUのGemma、課金された実行はDeepSeek。
        free = within_free_quota(owner, "monitor")
        try:
            result = await monitor_service.run_prompt(
                prompt["prompt"],
                site_row["brand_name"],
                site_row["url"],
                owner,
                [site_row["name"]],
                paid=not free,
            )
        except (RuntimeError, httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return PromptRun.model_validate(db.save_prompt_run(owner, prompt_id, result))
