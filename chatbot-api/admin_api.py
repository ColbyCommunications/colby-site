from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, timezone
from urllib.parse import urlencode
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from config_db import get_db_connection
from input_validation_pre_hook import get_standard_rejection_message
from okta_auth import (
    OktaConfigError,
    OKTA_SESSION_USER_KEY,
    OKTA_SESSION_STATE_KEY,
    OKTA_SESSION_CODE_VERIFIER_KEY,
    OKTA_SESSION_ID_TOKEN_KEY,
    get_okta_config,
)


# Use uvicorn.error logger so messages show up alongside the existing server logs
# on Platform.sh and local dev.
logger = logging.getLogger("uvicorn.error")

# Feature flag: when ADMIN_OKTA_ENABLED is not 'true', admin endpoints are left
# open (no Okta authentication enforced).
OKTA_ADMIN_ENABLED = os.getenv("ADMIN_OKTA_ENABLED", "false").lower() == "true"


# Paths that are exempt from Okta session checks so that the login and callback
# routes can bootstrap authentication. These are defined relative to the app's
# root (that is, they don't include any root_path such as /chatbot-api).
_ADMIN_AUTH_EXEMPT_PATHS = {
    "/admin/",
    "/admin/login",
    "/admin/authorization-code/callback",
    "/admin/logout",
    # HTML landing pages that render their own login preview when unauthenticated.
    "/admin/responses",
    "/admin/dashboard",
}


def _get_request_path(request: Request) -> str:
    """
    Return the request path relative to the application's root_path.

    On Platform.sh the public URL includes a `/chatbot-api` prefix, but our
    routers are mounted at `/admin`. We normalize by stripping any configured
    root_path (either from the ASGI scope or from the FastAPI app) so that
    paths look like `/admin/...` here.
    """
    # Full path as seen by the ASGI server (may include the public prefix).
    full_path = request.scope.get("path") or request.url.path

    # Prefer root_path from the request scope (set by the server), fall back
    # to the application's configured root_path if present.
    root_path = request.scope.get("root_path") or getattr(request.app, "root_path", "") or ""

    if root_path and full_path.startswith(root_path):
        # Strip the root_path prefix so we end up with router-relative paths
        # such as `/admin/login`.
        stripped = full_path[len(root_path) :] or "/"
        # Ensure leading slash for safety.
        if not stripped.startswith("/"):
            stripped = "/" + stripped
        logger.info(
            "Auth path normalization: full_path=%s root_path=%s normalized=%s",
            full_path,
            root_path,
            stripped,
        )
        return stripped

    logger.info(
        "Auth path normalization (no root_path): full_path=%s root_path=%s",
        full_path,
        root_path,
    )
    return full_path


def require_admin(request: Request) -> None:
    """
    Okta-backed auth for all /admin endpoints (when enabled).

    Behaviour:
    - If ADMIN_OKTA_ENABLED is not 'true', do nothing (admin routes are open).
    - If the request targets an exempt path (login, callback, logout), skip checks.
    - Otherwise, ensure Okta is configured and that a valid okta_user is present
      in the session. If not, redirect the client to /admin/login.
    """
    path = _get_request_path(request)

    if not OKTA_ADMIN_ENABLED:
        logger.info(
            "require_admin: Okta admin auth disabled via ADMIN_OKTA_ENABLED; allowing path=%s",
            path,
        )
        return

    # Accessing request.session requires SessionMiddleware. In some hosting
    # setups or early middleware hooks this may not yet be installed; in that
    # case, treat the session as empty instead of raising a RuntimeError so
    # we can still issue a redirect to the admin login page.
    try:
        session = request.session
    except RuntimeError:
        logger.warning(
            "require_admin: SessionMiddleware not installed; treating session as empty for path=%s",
            path,
        )
        session = {}

    session_user = session.get(OKTA_SESSION_USER_KEY)
    is_exempt = path in _ADMIN_AUTH_EXEMPT_PATHS or path.startswith("/admin/static/")
    logger.info(
        "require_admin: path=%s exempt=%s has_user=%s",
        path,
        is_exempt,
        bool(session_user),
    )
    if is_exempt:
        # Allow login/callback/logout and static assets without an existing session.
        return

    try:
        # Ensure Okta configuration is present; this will raise if required envs
        # are missing.
        get_okta_config()
    except OktaConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if session_user:
        # Already authenticated via Okta.
        logger.debug("require_admin: okta_user present in session, allowing request.")
        return

    # Not authenticated: redirect into the Okta login flow.
    login_url = request.url_for("admin_login")
    logger.info("require_admin: redirecting unauthenticated request on %s to %s", path, login_url)
    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail="Redirecting to admin login.",
        headers={"Location": str(login_url)},
    )
admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


class LlmModelDTO(BaseModel):
    """Model configuration entry exposed via the admin API."""

    id: Optional[int] = Field(default=None, description="Database ID (read-only)")
    model_id: str = Field(
        ...,
        description="Provider-specific model identifier, e.g. 'gpt-4.1-mini'",
    )
    provider: str = Field(default="openai")
    display_name: str
    is_active: bool = True
    is_default: bool = False


class AppMessageDTO(BaseModel):
    """Application-level message (e.g. standard rejection message)."""

    message_key: str
    content: str


class AppMessageUpdate(BaseModel):
    """Payload for creating/updating an app message."""

    content: str


class AgentInstructionDTO(BaseModel):
    """Single instruction row for an agent."""

    id: Optional[int] = Field(default=None, description="Database ID (read-only)")
    position: int
    content: str


class AgentDTO(BaseModel):
    """Logical agent plus its ordered instructions."""

    id: Optional[int] = Field(default=None, description="Database ID (read-only)")
    agent_key: str = Field(
        ...,
        description="Logical key used by the runtime (e.g. 'runtime_rag', 'validation_primary')",
    )
    name: str = Field(
        ...,
        description="Human-friendly display name for this agent (e.g. 'Colby RAG Assistant')",
    )
    description_template: Optional[str] = Field(
        default=None,
        description="Optional description template used when constructing prompts.",
    )
    model_id: str = Field(
        ...,
        description="Provider-specific model identifier used by this agent (e.g. 'gpt-4.1-mini').",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this agent is currently active.",
    )
    instructions: List[AgentInstructionDTO] = Field(
        default_factory=list,
        description="Ordered list of instructions for this agent.",
    )


class QueryLogPartDTO(BaseModel):
    """Single per-stage log entry for a user query."""

    id: int
    created_at: datetime
    stage: str
    model_id: Optional[str] = None
    agent_name: Optional[str] = None
    using_db_config: Optional[bool] = None
    blocked: Optional[bool] = None
    result: Dict[str, Any] = Field(default_factory=dict)


class QueryLogDTO(BaseModel):
    """High-level view of a user query and the assistant's response."""

    id: int
    created_at: datetime
    user_message: str
    final_answer: Optional[str] = None
    status: str
    blocked_by: Optional[str] = None
    error_message: Optional[str] = None
    parts: List[QueryLogPartDTO] = Field(
        default_factory=list,
        description="Per-stage model metadata for this query (validators, runtime, etc.).",
    )
    is_blacklist_example: Optional[bool] = Field(
        default=None,
        description="True if this query has been added as a blacklist training example.",
    )
    is_whitelist_example: Optional[bool] = Field(
        default=None,
        description="True if this query has been added as a whitelist training example.",
    )


class WeeklyMetricsDTO(BaseModel):
    """Aggregated chatbot metrics for the last 7 days (ET)."""

    start_date: date
    end_date: date
    total_queries: int
    answered: int
    blocked: int
    error: int
    blocked_by_query_validator: int
    blocked_by_blacklist_validator: int
    blocked_by_both: int
    passed_guardrails: int
    no_answer_after_pass: int


class TrainingExamplesDTO(BaseModel):
    """Global whitelist/blacklist training examples used by validator agents."""

    blacklist_queries: List[str] = Field(
        default_factory=list,
        description="Queries that should always be treated as BLACKLISTED_QUERY_EXAMPLE.",
    )
    whitelist_queries: List[str] = Field(
        default_factory=list,
        description="Queries that should always be treated as WHITELISTED_QUERY_EXAMPLE.",
    )


def _get_required_db_connection():
    """Return a live config DB connection or raise 503 if unavailable."""
    conn = get_db_connection()
    if conn is None:
        raise HTTPException(
            status_code=503,
            detail="Configuration database is not available",
        )
    return conn


def _row_to_model_dto(row: Dict[str, Any]) -> LlmModelDTO:
    return LlmModelDTO(
        id=row["id"],
        model_id=row["model_id"],
        provider=row["provider"],
        display_name=row["display_name"],
        is_active=bool(row["is_active"]),
        is_default=bool(row["is_default"]),
    )


def _row_to_agent_dto(
    row: Dict[str, Any],
    instructions: List[AgentInstructionDTO],
) -> AgentDTO:
    return AgentDTO(
        id=row["id"],
        agent_key=row["agent_key"],
        name=row["name"],
        description_template=row.get("description_template"),
        model_id=row["model_id"],
        is_active=bool(row["is_active"]),
        instructions=instructions,
    )


def _fetch_agent_instructions(cursor, agent_id: int) -> List[AgentInstructionDTO]:
    cursor.execute(
        """
        SELECT id, position, content
        FROM agent_instructions
        WHERE agent_id = %s
        ORDER BY position ASC, id ASC;
        """,
        (agent_id,),
    )
    rows = cursor.fetchall() or []
    return [
        AgentInstructionDTO(
            id=row["id"],
            position=row["position"],
            content=row["content"],
        )
        for row in rows
    ]


def _row_to_query_log_dto(
    row: Dict[str, Any],
    parts: Optional[List[QueryLogPartDTO]] = None,
) -> QueryLogDTO:
    return QueryLogDTO(
        id=row["id"],
        created_at=row["created_at"],
        user_message=row["user_message"],
        final_answer=row.get("final_answer"),
        status=row["status"],
        blocked_by=row.get("blocked_by"),
        error_message=row.get("error_message"),
        parts=parts or [],
        is_blacklist_example=(
            bool(row.get("is_blacklist_example"))
            if row.get("is_blacklist_example") is not None
            else None
        ),
        is_whitelist_example=(
            bool(row.get("is_whitelist_example"))
            if row.get("is_whitelist_example") is not None
            else None
        ),
    )


def _parse_date_param(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {value!r}. Expected YYYY-MM-DD.")


# ----- Okta-backed admin login/logout -----


def _generate_pkce_verifier_and_challenge() -> tuple[str, str]:
    """Generate a PKCE code_verifier and corresponding S256 code_challenge."""
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


@admin_router.get("/login", name="admin_login")
def admin_login(request: Request) -> RedirectResponse:
    """
    Entry point to start the Okta authorization code + PKCE flow.

    Redirects the browser to the Okta-hosted sign-in page.
    """
    if not OKTA_ADMIN_ENABLED:
        # If Okta admin auth is disabled, expose this as a 404 so callers know
        # the login endpoint is not active.
        raise HTTPException(status_code=404, detail="Admin Okta login is disabled.")

    try:
        config = get_okta_config()
    except OktaConfigError as exc:
        logger.error("admin_login: Okta configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = _generate_pkce_verifier_and_challenge()

    # Persist state and PKCE verifier in the server-side session.
    request.session[OKTA_SESSION_STATE_KEY] = state
    request.session[OKTA_SESSION_CODE_VERIFIER_KEY] = code_verifier

    query_params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "scope": config["scope"],
        "redirect_uri": config["redirect_uri"],
        "state": state,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }
    auth_url = f'{config["auth_uri"]}?{urlencode(query_params)}'
    logger.info(
        "admin_login: redirecting to Okta auth_uri=%s redirect_uri=%s state=%s",
        config["auth_uri"],
        config["redirect_uri"],
        state,
    )
    return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)


@admin_router.get("/authorization-code/callback", name="admin_callback")
def admin_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None) -> RedirectResponse:
    """
    Okta authorization code callback.

    Exchanges the authorization code for tokens, fetches userinfo, and stores
    a minimal Okta user profile in the session. Finally, redirects to /admin/.
    """
    if not OKTA_ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Admin Okta callback is disabled.")

    try:
        config = get_okta_config()
    except OktaConfigError as exc:
        logger.error("admin_callback: Okta configuration error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "admin_callback: received callback state=%s code_present=%s",
        state,
        bool(code),
    )

    if not state or state != request.session.get(OKTA_SESSION_STATE_KEY):
        logger.warning(
            "admin_callback: state mismatch. expected=%s got=%s",
            request.session.get(OKTA_SESSION_STATE_KEY),
            state,
        )
        raise HTTPException(status_code=400, detail="Invalid or missing state parameter.")

    if not code:
        logger.warning("admin_callback: missing authorization code.")
        raise HTTPException(status_code=400, detail="Authorization code was not returned.")

    code_verifier = request.session.get(OKTA_SESSION_CODE_VERIFIER_KEY)
    if not code_verifier:
        logger.warning("admin_callback: missing PKCE code_verifier in session.")
        raise HTTPException(status_code=400, detail="Missing PKCE code_verifier in session.")

    # Exchange code for tokens.
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        token_resp = httpx.post(
            config["token_uri"],
            data=data,
            headers=headers,
            auth=(config["client_id"], config["client_secret"]),
            timeout=10.0,
        )
        token_resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("admin_callback: token exchange failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange authorization code for tokens: {exc}",
        ) from exc

    exchange = token_resp.json()

    if exchange.get("token_type") != "Bearer":
        logger.error(
            "admin_callback: unsupported token_type from Okta: %s",
            exchange.get("token_type"),
        )
        raise HTTPException(
            status_code=403,
            detail="Unsupported token type from Okta. Expected 'Bearer'.",
        )

    access_token = exchange.get("access_token")
    id_token = exchange.get("id_token")
    if not access_token:
        logger.error("admin_callback: Okta token response missing access_token.")
        raise HTTPException(status_code=502, detail="Okta token response missing access_token.")

    # Fetch userinfo using the access token.
    try:
        userinfo_resp = httpx.get(
            config["userinfo_uri"],
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )
        userinfo_resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("admin_callback: userinfo request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to retrieve userinfo from Okta: {exc}",
        ) from exc

    userinfo = userinfo_resp.json()
    okta_user = {
        "sub": userinfo.get("sub"),
        "email": userinfo.get("email"),
        "name": userinfo.get("name") or userinfo.get("given_name") or userinfo.get("preferred_username"),
    }

    # Store user and (optionally) id_token in the session and clear transient values.
    request.session[OKTA_SESSION_USER_KEY] = okta_user
    if id_token:
        request.session[OKTA_SESSION_ID_TOKEN_KEY] = id_token

    request.session.pop(OKTA_SESSION_STATE_KEY, None)
    request.session.pop(OKTA_SESSION_CODE_VERIFIER_KEY, None)
    logger.info(
        "admin_callback: user authenticated sub=%s email=%s",
        okta_user.get("sub"),
        okta_user.get("email"),
    )

    # Redirect to the admin home, respecting root_path.
    redirect_url = request.url_for("admin_home")
    return RedirectResponse(str(redirect_url), status_code=status.HTTP_302_FOUND)


@admin_router.get("/logout", name="admin_logout")
def admin_logout(request: Request) -> RedirectResponse:
    """
    Clear the Okta-backed admin session and optionally invoke Okta global logout.

    When ADMIN_OKTA_ENABLED is not 'true', this simply redirects back to the
    admin home page without calling Okta.
    """
    logger.info("admin_logout: clearing local admin session.")

    # Always clear local session state first.
    id_token = request.session.pop(OKTA_SESSION_ID_TOKEN_KEY, None)
    request.session.pop(OKTA_SESSION_USER_KEY, None)
    request.session.pop(OKTA_SESSION_STATE_KEY, None)
    request.session.pop(OKTA_SESSION_CODE_VERIFIER_KEY, None)

    # If Okta admin auth is disabled, just go back to the admin home page.
    if not OKTA_ADMIN_ENABLED:
        redirect_url = request.url_for("admin_home")
        return RedirectResponse(str(redirect_url), status_code=status.HTTP_302_FOUND)

    try:
        config = get_okta_config()
    except OktaConfigError as exc:
        logger.warning("admin_logout: Okta configuration error, using local redirect only: %s", exc)
        # If Okta isn't fully configured, just go back to the admin home page.
        redirect_url = request.url_for("admin_home")
        return RedirectResponse(str(redirect_url), status_code=status.HTTP_302_FOUND)

    logout_uri = config["logout_uri"]
    post_logout_redirect_uri = config.get("post_logout_redirect_uri") or str(
        request.url_for("admin_home")
    )

    params: Dict[str, str] = {"post_logout_redirect_uri": post_logout_redirect_uri}
    if id_token:
        params["id_token_hint"] = id_token

    logout_url = f"{logout_uri}?{urlencode(params)}"
    logger.info(
        "admin_logout: redirecting to Okta logout_uri=%s post_logout_redirect_uri=%s has_id_token=%s",
        logout_uri,
        post_logout_redirect_uri,
        bool(id_token),
    )
    return RedirectResponse(logout_url, status_code=status.HTTP_302_FOUND)


# ----- Admin endpoints: LLM models -----


@admin_router.get("/models", response_model=List[LlmModelDTO])
def list_models() -> List[LlmModelDTO]:
    """List all configured LLM models."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, model_id, provider, display_name, is_active, is_default
            FROM llm_models
            ORDER BY display_name ASC, model_id ASC;
            """
        )
        rows = cursor.fetchall() or []
        return [_row_to_model_dto(row) for row in rows]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.post("/models", response_model=LlmModelDTO, status_code=201)
def create_model(model: LlmModelDTO) -> LlmModelDTO:
    """Create a new LLM model entry."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Enforce uniqueness on model_id at the application level for clearer errors.
        cursor.execute(
            "SELECT id FROM llm_models WHERE model_id = %s LIMIT 1;",
            (model.model_id,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="A model with this model_id already exists.",
            )

        cursor.execute(
            """
            INSERT INTO llm_models (
                model_id, provider, display_name,
                is_active, is_default
            )
            VALUES (%s, %s, %s, %s, %s);
            """,
            (
                model.model_id,
                model.provider,
                model.display_name,
                int(model.is_active),
                int(model.is_default),
            ),
        )
        new_id = cursor.lastrowid

        cursor.execute(
            """
            SELECT id, model_id, provider, display_name, is_active, is_default
            FROM llm_models
            WHERE id = %s;
            """,
            (new_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Failed to load created model.")
        return _row_to_model_dto(row)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.put("/models/{model_id}", response_model=LlmModelDTO)
def update_model(model_id: str, model: LlmModelDTO) -> LlmModelDTO:
    """
    Replace an existing LLM model entry identified by its current model_id.

    The payload's model_id is allowed to differ from the path parameter and will
    be treated as the new model_id.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id
            FROM llm_models
            WHERE model_id = %s
            LIMIT 1;
            """,
            (model_id,),
        )
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Model not found.")

        cursor.execute(
            """
            UPDATE llm_models
            SET model_id = %s,
                provider = %s,
                display_name = %s,
                is_active = %s,
                is_default = %s
            WHERE id = %s;
            """,
            (
                model.model_id,
                model.provider,
                model.display_name,
                int(model.is_active),
                int(model.is_default),
                existing["id"],
            ),
        )

        cursor.execute(
            """
            SELECT id, model_id, provider, display_name, is_active, is_default
            FROM llm_models
            WHERE id = %s;
            """,
            (existing["id"],),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Failed to load updated model.")
        return _row_to_model_dto(row)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/models/{model_id}", status_code=204)
def delete_model(model_id: str) -> None:
    """Delete a model by its model_id."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "DELETE FROM llm_models WHERE model_id = %s;",
            (model_id,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Model not found.")
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


# ----- Admin endpoints: agents + instructions -----


@admin_router.get("/agents", response_model=List[AgentDTO])
def list_agents() -> List[AgentDTO]:
    """List all active logical agents and their instructions."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, agent_key, name, description_template,
                   model_id, is_active
            FROM llm_agents
            WHERE is_active = 1
            ORDER BY agent_key ASC;
            """
        )
        rows = cursor.fetchall() or []

        agents: List[AgentDTO] = []
        for row in rows:
            instructions = _fetch_agent_instructions(cursor, row["id"])
            agents.append(_row_to_agent_dto(row, instructions))
        return agents
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/agents/{agent_key}", response_model=AgentDTO)
def get_agent(agent_key: str) -> AgentDTO:
    """Fetch a single agent configuration by its logical key."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, agent_key, name, description_template,
                   model_id, is_active
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            (agent_key,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found.")

        instructions = _fetch_agent_instructions(cursor, row["id"])
        return _row_to_agent_dto(row, instructions)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.post("/agents", response_model=AgentDTO, status_code=201)
def create_agent(agent: AgentDTO) -> AgentDTO:
    """Create a new logical agent and its instructions."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM llm_agents WHERE agent_key = %s LIMIT 1;",
            (agent.agent_key,),
        )
        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="An agent with this agent_key already exists.",
            )

        cursor.execute(
            """
            INSERT INTO llm_agents (
                agent_key, name, description_template,
                model_id, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                agent.agent_key,
                agent.name,
                agent.description_template,
                agent.model_id,
                int(agent.is_active),
            ),
        )
        agent_id = cursor.lastrowid

        created_instructions: List[AgentInstructionDTO] = []
        for inst in agent.instructions:
            cursor.execute(
                """
                INSERT INTO agent_instructions (
                    agent_id, position, content
                )
                VALUES (%s, %s, %s);
                """,
                (
                    agent_id,
                    inst.position,
                    inst.content,
                ),
            )
            created_instructions.append(
                AgentInstructionDTO(
                    id=cursor.lastrowid,
                    position=inst.position,
                    content=inst.content,
                )
            )

        return AgentDTO(
            id=agent_id,
            agent_key=agent.agent_key,
            name=agent.name,
            description_template=agent.description_template,
            model_id=agent.model_id,
            is_active=agent.is_active,
            instructions=created_instructions,
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.put("/agents/{agent_key}", response_model=AgentDTO)
def update_agent(agent_key: str, agent: AgentDTO) -> AgentDTO:
    """
    Replace an existing agent (identified by current agent_key) and its instructions.

    The payload's agent_key is allowed to differ from the path parameter and will
    be treated as the new agent_key.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            (agent_key,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found.")

        agent_id = row["id"]

        cursor.execute(
            """
            UPDATE llm_agents
            SET agent_key = %s,
                name = %s,
                description_template = %s,
                model_id = %s,
                is_active = %s
            WHERE id = %s;
            """,
            (
                agent.agent_key,
                agent.name,
                agent.description_template,
                agent.model_id,
                int(agent.is_active),
                agent_id,
            ),
        )

        # Replace instructions wholesale for simplicity.
        cursor.execute(
            "DELETE FROM agent_instructions WHERE agent_id = %s;",
            (agent_id,),
        )

        created_instructions: List[AgentInstructionDTO] = []
        for inst in agent.instructions:
            cursor.execute(
                """
                INSERT INTO agent_instructions (
                    agent_id, position, content
                )
                VALUES (%s, %s, %s);
                """,
                (
                    agent_id,
                    inst.position,
                    inst.content,
                ),
            )
            created_instructions.append(
                AgentInstructionDTO(
                    id=cursor.lastrowid,
                    position=inst.position,
                    content=inst.content,
                )
            )

        return AgentDTO(
            id=agent_id,
            agent_key=agent.agent_key,
            name=agent.name,
            description_template=agent.description_template,
            model_id=agent.model_id,
            is_active=agent.is_active,
            instructions=created_instructions,
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/agents/{agent_key}", status_code=204)
def delete_agent(agent_key: str) -> None:
    """Delete an agent (and its instructions) by agent_key."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            DELETE FROM llm_agents
            WHERE agent_key = %s;
            """,
            (agent_key,),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Agent not found.")
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


# ----- Admin endpoints: app messages -----


@admin_router.get("/messages", response_model=List[AppMessageDTO])
def list_messages() -> List[AppMessageDTO]:
    """List all application-level messages."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT message_key, content
            FROM app_messages
            ORDER BY message_key ASC;
            """
        )
        rows = cursor.fetchall() or []
        return [
            AppMessageDTO(
                message_key=row["message_key"],
                content=row["content"],
            )
            for row in rows
        ]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/messages/{message_key}", response_model=AppMessageDTO)
def get_message(message_key: str) -> AppMessageDTO:
    """Fetch a single message by its key."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT message_key, content
            FROM app_messages
            WHERE message_key = %s
            LIMIT 1;
            """,
            (message_key,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Message not found.")
        return AppMessageDTO(
            message_key=row["message_key"],
            content=row["content"],
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.put("/messages/{message_key}", response_model=AppMessageDTO)
def upsert_message(message_key: str, payload: AppMessageUpdate) -> AppMessageDTO:
    """
    Create or update an application-level message.

    Uses INSERT ... ON DUPLICATE KEY UPDATE semantics under the hood.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO app_messages (message_key, content)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                content = VALUES(content);
            """,
            (message_key, payload.content),
        )

        cursor.execute(
            """
            SELECT message_key, content
            FROM app_messages
            WHERE message_key = %s
            LIMIT 1;
            """,
            (message_key,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=500,
                detail="Failed to load stored message.",
            )
        return AppMessageDTO(
            message_key=row["message_key"],
            content=row["content"],
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


# ----- Admin endpoints: query logs -----


@admin_router.get("/metrics/weekly", response_model=WeeklyMetricsDTO)
def get_weekly_metrics(
    start_date: Optional[str] = Query(
        default=None,
        description="Start date (YYYY-MM-DD, ET). Defaults to 7 days ago if omitted with end_date.",
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="End date (YYYY-MM-DD, ET). Defaults to today if omitted with start_date.",
    ),
) -> WeeklyMetricsDTO:
    """
    Return aggregated chatbot metrics for the last 7 calendar days (ET).

    This powers the summary cards on the admin home dashboard.
    """
    est_tz = ZoneInfo("America/New_York")
    today_et = datetime.now(est_tz).date()

    # Interpret incoming dates as ET calendar days; fall back to last 7 days.
    start = _parse_date_param(start_date)
    end = _parse_date_param(end_date)

    if not start and not end:
        # Default window: last 7 ET calendar days.
        end = today_et
        start = end - timedelta(days=6)
    elif start and not end:
        # Single-day window.
        end = start
    elif end and not start:
        start = end

    assert start is not None and end is not None

    # Convert the ET date range into UTC timestamps for querying MySQL.
    start_local = datetime.combine(start, datetime.min.time(), tzinfo=est_tz)
    end_next_local = datetime.combine(
        end + timedelta(days=1),
        datetime.min.time(),
        tzinfo=est_tz,
    )
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_next_local.astimezone(timezone.utc).replace(tzinfo=None)

    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Core counts by status.
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_queries,
                SUM(CASE WHEN status = 'answered' THEN 1 ELSE 0 END) AS answered,
                SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked,
                SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS error
            FROM query_logs
            WHERE created_at >= %s AND created_at < %s;
            """,
            (start_utc, end_utc),
        )
        row = cursor.fetchone() or {}
        total_queries = int(row.get("total_queries") or 0)
        answered = int(row.get("answered") or 0)
        blocked = int(row.get("blocked") or 0)
        error = int(row.get("error") or 0)

        # Guardrail behaviour by validator (Query Validator / Blacklist Validator).
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN has_primary_blocked = 1 THEN 1 ELSE 0 END) AS blocked_by_query_validator,
                SUM(CASE WHEN has_blacklist_blocked = 1 THEN 1 ELSE 0 END) AS blocked_by_blacklist_validator,
                SUM(
                    CASE
                        WHEN has_primary_blocked = 1 AND has_blacklist_blocked = 1
                        THEN 1 ELSE 0
                    END
                ) AS blocked_by_both,
                SUM(
                    CASE
                        WHEN has_primary_blocked = 0 AND has_blacklist_blocked = 0
                        THEN 1 ELSE 0
                    END
                ) AS passed_guardrails
            FROM (
                SELECT
                    q.id AS query_id,
                    MAX(
                        CASE
                            WHEN p.stage = 'validation_primary' AND p.blocked = 1
                            THEN 1 ELSE 0
                        END
                    ) AS has_primary_blocked,
                    MAX(
                        CASE
                            WHEN p.stage = 'validation_blacklist' AND p.blocked = 1
                            THEN 1 ELSE 0
                        END
                    ) AS has_blacklist_blocked
                FROM query_logs AS q
                LEFT JOIN query_log_parts AS p
                    ON p.query_log_id = q.id
                WHERE q.created_at >= %s AND q.created_at < %s
                GROUP BY q.id
            ) AS per_query;
            """,
            (start_utc, end_utc),
        )
        guard = cursor.fetchone() or {}
        blocked_by_query_validator = int(
            guard.get("blocked_by_query_validator") or 0
        )
        blocked_by_blacklist_validator = int(
            guard.get("blocked_by_blacklist_validator") or 0
        )
        blocked_by_both = int(guard.get("blocked_by_both") or 0)
        passed_guardrails = int(guard.get("passed_guardrails") or 0)

        # Queries that passed both validators but were answered with the
        # standard rejection message by the main runtime agent.
        rejection_message = get_standard_rejection_message()
        cursor.execute(
            """
            SELECT COUNT(*) AS no_answer_after_pass
            FROM (
                SELECT
                    q.id AS query_id,
                    MAX(
                        CASE
                            WHEN p.stage = 'validation_primary' AND p.blocked = 1
                            THEN 1 ELSE 0
                        END
                    ) AS has_primary_blocked,
                    MAX(
                        CASE
                            WHEN p.stage = 'validation_blacklist' AND p.blocked = 1
                            THEN 1 ELSE 0
                        END
                    ) AS has_blacklist_blocked
                FROM query_logs AS q
                LEFT JOIN query_log_parts AS p
                    ON p.query_log_id = q.id
                WHERE q.created_at >= %s AND q.created_at < %s
                GROUP BY q.id
            ) AS s
            JOIN query_logs AS q
                ON q.id = s.query_id
            WHERE s.has_primary_blocked = 0
              AND s.has_blacklist_blocked = 0
              AND q.status = 'answered'
              AND q.final_answer = %s;
            """,
            (start_utc, end_utc, rejection_message),
        )
        row = cursor.fetchone() or {}
        no_answer_after_pass = int(row.get("no_answer_after_pass") or 0)

        return WeeklyMetricsDTO(
            start_date=start,
            end_date=end,
            total_queries=total_queries,
            answered=answered,
            blocked=blocked,
            error=error,
            blocked_by_query_validator=blocked_by_query_validator,
            blocked_by_blacklist_validator=blocked_by_blacklist_validator,
            blocked_by_both=blocked_by_both,
            passed_guardrails=passed_guardrails,
            no_answer_after_pass=no_answer_after_pass,
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/training-examples", response_model=TrainingExamplesDTO)
def get_training_examples() -> TrainingExamplesDTO:
    """
    Fetch all global blacklist and whitelist training examples from query_examples.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT kind, query_text
            FROM query_examples
            WHERE kind IN ('blacklist', 'whitelist')
            ORDER BY kind ASC, query_text ASC;
            """
        )
        rows = cursor.fetchall() or []

        blacklist: List[str] = []
        whitelist: List[str] = []
        for row in rows:
            text = (row.get("query_text") or "").strip()
            if not text:
                continue
            if row.get("kind") == "blacklist":
                blacklist.append(text)
            elif row.get("kind") == "whitelist":
                whitelist.append(text)

        return TrainingExamplesDTO(
            blacklist_queries=blacklist,
            whitelist_queries=whitelist,
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.put("/training-examples", response_model=TrainingExamplesDTO)
def put_training_examples(payload: TrainingExamplesDTO) -> TrainingExamplesDTO:
    """
    Replace the current blacklist/whitelist examples with the provided lists.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Normalize and de-duplicate incoming queries.
        blacklist = sorted(
            {q.strip() for q in payload.blacklist_queries if (q or "").strip()}
        )
        whitelist = sorted(
            {q.strip() for q in payload.whitelist_queries if (q or "").strip()}
        )

        # Clear existing examples for these kinds.
        cursor.execute("DELETE FROM query_examples WHERE kind IN ('blacklist', 'whitelist');")

        # Re-insert blacklist examples.
        for text in blacklist:
            cursor.execute(
                """
                INSERT INTO query_examples (kind, query_text)
                VALUES ('blacklist', %s);
                """,
                (text,),
            )

        # Re-insert whitelist examples.
        for text in whitelist:
            cursor.execute(
                """
                INSERT INTO query_examples (kind, query_text)
                VALUES ('whitelist', %s);
                """,
                (text,),
            )

        return TrainingExamplesDTO(
            blacklist_queries=blacklist,
            whitelist_queries=whitelist,
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/query-logs", response_model=List[QueryLogDTO])
def list_query_logs(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(
        default=None,
        description=(
            "Filter by status or label. Supported values: "
            "answered, blocked, error, blacklisted, whitelisted, "
            "blocked_by_blacklist_validator, blocked_by_query_validator, "
            "standard_rejection_answered."
        ),
    ),
    limit: Optional[int] = Query(default=None, ge=1, le=50000),
    offset: int = Query(default=0, ge=0),
) -> List[QueryLogDTO]:
    """
    List query/response logs for a given date range, optionally filtered by text.

    Dates are inclusive and expected in YYYY-MM-DD format, interpreted in
    America/New_York (ET) and converted to UTC for comparison.
    """
    # Treat all date filters as Eastern Time (ET) so that "Today" and
    # "Last 7 days" in the dashboard align with what users see. We assume
    # the underlying MySQL `created_at` timestamps are stored in UTC.
    est_tz = ZoneInfo("America/New_York")
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        clauses: List[str] = []
        params: List[Any] = []

        start = _parse_date_param(start_date)
        end = _parse_date_param(end_date)

        if start:
            # Interpret the start date as midnight in ET, then convert to UTC
            # for comparison against UTC-stored MySQL timestamps.
            start_local = datetime.combine(start, datetime.min.time(), tzinfo=est_tz)
            start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
            clauses.append("q.created_at >= %s")
            params.append(start_utc)
        if end:
            # Inclusive end-date: compute the *next* midnight in ET and convert
            # to UTC, then use a strict `<` comparison.
            end_next = end + timedelta(days=1)
            end_local = datetime.combine(end_next, datetime.min.time(), tzinfo=est_tz)
            end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
            clauses.append("q.created_at < %s")
            params.append(end_utc)

        if q:
            like = f"%{q}%"
            clauses.append("(q.user_message LIKE %s OR q.final_answer LIKE %s)")
            params.extend([like, like])

        if status_filter:
            # Traditional status-based filters
            status_values = {"answered", "blocked", "error"}
            # Training example label filters
            label_values = {"blacklisted", "whitelisted"}
            # More granular blocked-status filters and standard rejection answers
            blocked_detail_values = {
                "blocked_by_blacklist_validator",
                "blocked_by_query_validator",
                "standard_rejection_answered",
            }

            if status_filter in status_values:
                clauses.append("q.status = %s")
                params.append(status_filter)
            elif status_filter == "blacklisted":
                # Queries that have been explicitly added as blacklist examples.
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM query_examples e
                        WHERE e.kind = 'blacklist'
                          AND e.query_text = q.user_message
                    )
                    """
                )
            elif status_filter == "whitelisted":
                # Queries that have been explicitly added as whitelist examples.
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM query_examples e
                        WHERE e.kind = 'whitelist'
                          AND e.query_text = q.user_message
                    )
                    """
                )
            elif status_filter == "blocked_by_blacklist_validator":
                # Queries that were explicitly blocked by the blacklist validator.
                clauses.append("(q.status = %s AND q.blocked_by = %s)")
                params.extend(["blocked", "validation_blacklist"])
            elif status_filter == "blocked_by_query_validator":
                # Queries that were explicitly blocked by the primary query validator.
                clauses.append("(q.status = %s AND q.blocked_by = %s)")
                params.extend(["blocked", "validation_primary"])
            elif status_filter == "standard_rejection_answered":
                # Queries that were technically "answered" but where the runtime
                # agent returned the standard rejection message (e.g. insufficient context).
                rejection_message = get_standard_rejection_message()
                clauses.append("(q.status = %s AND q.final_answer = %s)")
                params.extend(["answered", rejection_message])
            else:
                allowed = sorted(list(status_values | label_values | blocked_detail_values))
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid status filter {status_filter!r}. "
                        f"Expected one of {allowed!r}."
                    ),
                )

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        # Build limit/offset clause - if limit is None, return all results
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT %s OFFSET %s"
            params.extend([limit, offset])
        elif offset > 0:
            # MySQL requires a large number for LIMIT when only OFFSET is provided
            limit_sql = "LIMIT 18446744073709551615 OFFSET %s"
            params.append(offset)

        query = f"""
            SELECT
                q.id,
                q.created_at,
                q.user_message,
                q.final_answer,
                q.status,
                q.blocked_by,
                q.error_message,
                EXISTS (
                    SELECT 1
                    FROM query_examples e
                    WHERE e.kind = 'blacklist'
                      AND e.query_text = q.user_message
                ) AS is_blacklist_example,
                EXISTS (
                    SELECT 1
                    FROM query_examples e2
                    WHERE e2.kind = 'whitelist'
                      AND e2.query_text = q.user_message
                ) AS is_whitelist_example
            FROM query_logs AS q
            {where_sql}
            ORDER BY q.created_at DESC
            {limit_sql};
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []

        return [
            _row_to_query_log_dto(row, parts=[])
            for row in rows
        ]
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/query-logs/export/csv")
def export_query_logs_csv(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None),
) -> StreamingResponse:
    """
    Export query logs as CSV with the same filters as list_query_logs.

    Returns a downloadable CSV file with all matching query logs including
    detailed validator reasoning and per-stage metadata.
    """
    est_tz = ZoneInfo("America/New_York")
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        clauses: List[str] = []
        params: List[Any] = []

        start = _parse_date_param(start_date)
        end = _parse_date_param(end_date)

        if start:
            start_local = datetime.combine(start, datetime.min.time(), tzinfo=est_tz)
            start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
            clauses.append("q.created_at >= %s")
            params.append(start_utc)
        if end:
            end_next = end + timedelta(days=1)
            end_local = datetime.combine(end_next, datetime.min.time(), tzinfo=est_tz)
            end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
            clauses.append("q.created_at < %s")
            params.append(end_utc)

        if q:
            like = f"%{q}%"
            clauses.append("(q.user_message LIKE %s OR q.final_answer LIKE %s)")
            params.extend([like, like])

        if status_filter:
            status_values = {"answered", "blocked", "error"}
            label_values = {"blacklisted", "whitelisted"}
            blocked_detail_values = {
                "blocked_by_blacklist_validator",
                "blocked_by_query_validator",
                "standard_rejection_answered",
            }

            if status_filter in status_values:
                clauses.append("q.status = %s")
                params.append(status_filter)
            elif status_filter == "blacklisted":
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM query_examples e
                        WHERE e.kind = 'blacklist'
                          AND e.query_text = q.user_message
                    )
                    """
                )
            elif status_filter == "whitelisted":
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM query_examples e
                        WHERE e.kind = 'whitelist'
                          AND e.query_text = q.user_message
                    )
                    """
                )
            elif status_filter == "blocked_by_blacklist_validator":
                clauses.append("(q.status = %s AND q.blocked_by = %s)")
                params.extend(["blocked", "validation_blacklist"])
            elif status_filter == "blocked_by_query_validator":
                clauses.append("(q.status = %s AND q.blocked_by = %s)")
                params.extend(["blocked", "validation_primary"])
            elif status_filter == "standard_rejection_answered":
                rejection_message = get_standard_rejection_message()
                clauses.append("(q.status = %s AND q.final_answer = %s)")
                params.extend(["answered", rejection_message])

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        query = f"""
            SELECT
                q.id,
                q.created_at,
                q.user_message,
                q.final_answer,
                q.status,
                q.blocked_by,
                q.error_message,
                EXISTS (
                    SELECT 1
                    FROM query_examples e
                    WHERE e.kind = 'blacklist'
                      AND e.query_text = q.user_message
                ) AS is_blacklist_example,
                EXISTS (
                    SELECT 1
                    FROM query_examples e2
                    WHERE e2.kind = 'whitelist'
                      AND e2.query_text = q.user_message
                ) AS is_whitelist_example
            FROM query_logs AS q
            {where_sql}
            ORDER BY q.created_at DESC;
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall() or []

        # Fetch all query log parts for the retrieved logs
        log_ids = [row["id"] for row in rows]
        parts_by_log_id: Dict[int, List[Dict[str, Any]]] = {log_id: [] for log_id in log_ids}

        if log_ids:
            # Build placeholders for IN clause
            placeholders = ",".join(["%s"] * len(log_ids))
            cursor.execute(
                f"""
                SELECT
                    query_log_id,
                    stage,
                    model_id,
                    agent_name,
                    using_db_config,
                    blocked,
                    result_json,
                    created_at
                FROM query_log_parts
                WHERE query_log_id IN ({placeholders})
                ORDER BY query_log_id, created_at ASC, id ASC;
                """,
                tuple(log_ids),
            )
            parts_rows = cursor.fetchall() or []
            for part in parts_rows:
                log_id = part["query_log_id"]
                if log_id in parts_by_log_id:
                    parts_by_log_id[log_id].append(part)

        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header with verbose columns
        writer.writerow([
            "ID",
            "Created At (ET)",
            "Status",
            "Blocked By",
            "Is Blacklist Example",
            "Is Whitelist Example",
            "Error Message",
            "User Message",
            "Final Answer",
            # Validation Primary (Query Validator) columns
            "Query Validator - Model",
            "Query Validator - Agent",
            "Query Validator - Blocked",
            "Query Validator - Is Legitimate",
            "Query Validator - Reasoning",
            # Validation Blacklist columns
            "Blacklist Validator - Model",
            "Blacklist Validator - Agent",
            "Blacklist Validator - Blocked",
            "Blacklist Validator - Is Legitimate",
            "Blacklist Validator - Reasoning",
            # Runtime columns
            "Runtime - Model",
            "Runtime - Agent",
            "Runtime - Using DB Config",
        ])

        # Write data rows
        for row in rows:
            created_at = row.get("created_at")
            if created_at:
                # Convert to ET for display
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                created_at_et = created_at.astimezone(est_tz)
                created_str = created_at_et.strftime("%Y-%m-%d %H:%M:%S ET")
            else:
                created_str = ""

            # Extract per-stage info
            parts = parts_by_log_id.get(row["id"], [])

            # Find validation_primary stage
            primary_validator = {}
            blacklist_validator = {}
            runtime_info = {}

            for part in parts:
                stage = part.get("stage", "")
                result_json = part.get("result_json") or "{}"
                try:
                    result = json.loads(result_json)
                except Exception:
                    result = {}

                if stage == "validation_primary":
                    primary_validator = {
                        "model": part.get("model_id", ""),
                        "agent": part.get("agent_name", ""),
                        "blocked": "Yes" if part.get("blocked") else "No",
                        "is_legitimate": str(result.get("is_legitimate_colby_query", "")) if "is_legitimate_colby_query" in result else "",
                        "reasoning": result.get("reasoning") or result.get("reason") or "",
                    }
                elif stage == "validation_blacklist":
                    blacklist_validator = {
                        "model": part.get("model_id", ""),
                        "agent": part.get("agent_name", ""),
                        "blocked": "Yes" if part.get("blocked") else "No",
                        "is_legitimate": str(result.get("is_legitimate_colby_query", "")) if "is_legitimate_colby_query" in result else "",
                        "reasoning": result.get("reasoning") or result.get("reason") or "",
                    }
                elif stage == "runtime_rag" or stage == "runtime":
                    runtime_info = {
                        "model": part.get("model_id", ""),
                        "agent": part.get("agent_name", ""),
                        "using_db_config": "Yes" if part.get("using_db_config") else "No",
                    }

            writer.writerow([
                row.get("id", ""),
                created_str,
                row.get("status", ""),
                row.get("blocked_by", ""),
                "Yes" if row.get("is_blacklist_example") else "No",
                "Yes" if row.get("is_whitelist_example") else "No",
                row.get("error_message", "") or "",
                row.get("user_message", "") or "",
                row.get("final_answer", "") or "",
                # Query Validator
                primary_validator.get("model", ""),
                primary_validator.get("agent", ""),
                primary_validator.get("blocked", ""),
                primary_validator.get("is_legitimate", ""),
                primary_validator.get("reasoning", ""),
                # Blacklist Validator
                blacklist_validator.get("model", ""),
                blacklist_validator.get("agent", ""),
                blacklist_validator.get("blocked", ""),
                blacklist_validator.get("is_legitimate", ""),
                blacklist_validator.get("reasoning", ""),
                # Runtime
                runtime_info.get("model", ""),
                runtime_info.get("agent", ""),
                runtime_info.get("using_db_config", ""),
            ])

        # Generate filename with current date
        now_et = datetime.now(est_tz)
        filename = f"chatbot_logs_{now_et.strftime('%Y%m%d_%H%M%S')}.csv"

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.get("/query-logs/{log_id}", response_model=QueryLogDTO)
def get_query_log(log_id: int) -> QueryLogDTO:
    """Fetch a single query log and all of its per-stage metadata."""
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                q.id,
                q.created_at,
                q.user_message,
                q.final_answer,
                q.status,
                q.blocked_by,
                q.error_message,
                EXISTS (
                    SELECT 1
                    FROM query_examples e
                    WHERE e.kind = 'blacklist'
                      AND e.query_text = q.user_message
                ) AS is_blacklist_example,
                EXISTS (
                    SELECT 1
                    FROM query_examples e2
                    WHERE e2.kind = 'whitelist'
                      AND e2.query_text = q.user_message
                ) AS is_whitelist_example
            FROM query_logs AS q
            WHERE q.id = %s
            LIMIT 1;
            """,
            (log_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Query log not found.")

        cursor.execute(
            """
            SELECT
                id,
                created_at,
                stage,
                model_id,
                agent_name,
                using_db_config,
                blocked,
                result_json
            FROM query_log_parts
            WHERE query_log_id = %s
            ORDER BY created_at ASC, id ASC;
            """,
            (log_id,),
        )
        part_rows = cursor.fetchall() or []

        parts: List[QueryLogPartDTO] = []
        for pr in part_rows:
            try:
                parsed_result = json.loads(pr.get("result_json") or "{}")
            except Exception:
                parsed_result = {"raw": pr.get("result_json")}

            parts.append(
                QueryLogPartDTO(
                    id=pr["id"],
                    created_at=pr["created_at"],
                    stage=pr["stage"],
                    model_id=pr.get("model_id"),
                    agent_name=pr.get("agent_name"),
                    using_db_config=bool(pr["using_db_config"]) if pr.get("using_db_config") is not None else None,
                    blocked=bool(pr["blocked"]) if pr.get("blocked") is not None else None,
                    result=parsed_result,
                )
            )

        return _row_to_query_log_dto(row, parts=parts)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.post("/query-logs/{log_id}/blacklist", status_code=200)
def add_query_to_blacklist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Shortcut: take the user_message from a query log and append it as a new
    blacklist example instruction for the 'validation_blacklist' agent and,
    when present, the general 'validation_primary' validator as well.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Load the query text.
        cursor.execute(
            """
            SELECT user_message
            FROM query_logs
            WHERE id = %s
            LIMIT 1;
            """,
            (log_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Query log not found.")

        user_message = (row.get("user_message") or "").strip()
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="Query log has no user_message to blacklist.",
            )

        cursor.execute(
            """
            INSERT IGNORE INTO query_examples (kind, query_text, source_log_id)
            VALUES ('blacklist', %s, %s);
            """,
            (user_message, log_id),
        )

        return {
            "status": "ok",
            "message": "Query added to blacklist examples.",
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass

# New: whitelist helper mirrors blacklist but uses WHITELISTED_QUERY_EXAMPLE prefix.
@admin_router.post("/query-logs/{log_id}/whitelist", status_code=200)
def add_query_to_whitelist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Shortcut: take the user_message from a query log and append it as a new
    whitelist example instruction for both the 'validation_blacklist' and
    'validation_primary' agents.

    This ensures that when a query is explicitly whitelisted from the admin
    UI, **both** validators see it as a whitelist example so that the general
    query validator does not subsequently block it.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Load the query text.
        cursor.execute(
            """
            SELECT user_message
            FROM query_logs
            WHERE id = %s
            LIMIT 1;
            """,
            (log_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Query log not found.")

        user_message = (row.get("user_message") or "").strip()
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="Query log has no user_message to whitelist.",
            )

        cursor.execute(
            """
            INSERT IGNORE INTO query_examples (kind, query_text, source_log_id)
            VALUES ('whitelist', %s, %s);
            """,
            (user_message, log_id),
        )

        return {
            "status": "ok",
            "message": "Query added to whitelist examples.",
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/query-logs/{log_id}/blacklist", status_code=200)
def remove_query_from_blacklist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Remove BLACKLISTED_QUERY_EXAMPLE instructions matching this log's user_message
    from both the 'validation_blacklist' and 'validation_primary' agents (if present).
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT user_message
            FROM query_logs
            WHERE id = %s
            LIMIT 1;
            """,
            (log_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Query log not found.")

        user_message = (row.get("user_message") or "").strip()
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="Query log has no user_message to un-blacklist.",
            )

        cursor.execute(
            """
            DELETE FROM query_examples
            WHERE kind = 'blacklist' AND query_text = %s;
            """,
            (user_message,),
        )

        if cursor.rowcount == 0:
            return {
                "status": "ok",
                "message": "Query was not present in blacklist examples.",
            }

        return {
            "status": "ok",
            "message": "Query removed from blacklist examples.",
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/query-logs/{log_id}/whitelist", status_code=200)
def remove_query_from_whitelist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Remove WHITELISTED_QUERY_EXAMPLE instructions matching this log's user_message
    from both the 'validation_blacklist' and 'validation_primary' agents (if present).
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT user_message
            FROM query_logs
            WHERE id = %s
            LIMIT 1;
            """,
            (log_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Query log not found.")

        user_message = (row.get("user_message") or "").strip()
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="Query log has no user_message to un-whitelist.",
            )

        cursor.execute(
            """
            DELETE FROM query_examples
            WHERE kind = 'whitelist' AND query_text = %s;
            """,
            (user_message,),
        )

        if cursor.rowcount == 0:
            return {
                "status": "ok",
                "message": "Query was not present in whitelist examples.",
            }

        return {
            "status": "ok",
            "message": "Query removed from whitelist examples.",
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


# ----- Admin dashboard HTML -----

ADMIN_UI_DIR = Path(__file__).parent / "admin_ui"


@admin_router.get("/static/dashboard.css")
def admin_dashboard_css() -> FileResponse:
    """Serve the dashboard CSS."""
    css_path = ADMIN_UI_DIR / "dashboard.css"
    if not css_path.exists():
        raise HTTPException(status_code=500, detail="Admin dashboard CSS not found.")
    return FileResponse(css_path, media_type="text/css")


@admin_router.get("/static/dashboard.js")
def admin_dashboard_js() -> FileResponse:
    """Serve the dashboard JavaScript."""
    js_path = ADMIN_UI_DIR / "dashboard.js"
    if not js_path.exists():
        raise HTTPException(status_code=500, detail="Admin dashboard JS not found.")
    return FileResponse(js_path, media_type="application/javascript")


@admin_router.get("/static/responses.js")
def admin_responses_js() -> FileResponse:
    """Serve the responses/logs dashboard JavaScript."""
    js_path = ADMIN_UI_DIR / "responses.js"
    if not js_path.exists():
        raise HTTPException(status_code=500, detail="Admin responses JS not found.")
    return FileResponse(js_path, media_type="application/javascript")


@admin_router.get("/static/home.js")
def admin_home_js() -> FileResponse:
    """Serve the admin home dashboard JavaScript."""
    js_path = ADMIN_UI_DIR / "home.js"
    if not js_path.exists():
        raise HTTPException(status_code=500, detail="Admin home JS not found.")
    return FileResponse(js_path, media_type="application/javascript")


def _get_session_user(request: Request) -> Optional[dict]:
    """Safely retrieve the Okta-backed admin user from the session, if present."""
    try:
        return request.session.get(OKTA_SESSION_USER_KEY)
    except Exception:  # pragma: no cover - defensive fallback
        return None


def _render_login_html() -> HTMLResponse:
    """Render the shared admin login preview HTML."""
    login_path = ADMIN_UI_DIR / "login.html"
    try:
        html = login_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin login HTML not found.")
    return HTMLResponse(content=html)


@admin_router.get("/", response_class=HTMLResponse)
def admin_home(request: Request) -> HTMLResponse:
    """
    Serve the admin landing page.

    Behaviour:
    - When ADMIN_OKTA_ENABLED is not 'true', always render the full admin home
      dashboard (no Okta auth required).
    - Otherwise, if an Okta-backed admin session is present (okta_user in
      session), render the full admin home dashboard.
    - If Okta is enabled and not authenticated, show the shared login preview
      page.
    """
    session_user = _get_session_user(request)

    # When Okta admin auth is disabled, treat the admin home as open access.
    if not OKTA_ADMIN_ENABLED or session_user:
        home_path = ADMIN_UI_DIR / "home.html"
        try:
            html = home_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="Admin home HTML not found.")
        return HTMLResponse(content=html)

    # Okta is enabled and there is no authenticated session: render the shared
    # login preview.
    return _render_login_html()


@admin_router.get("/responses", response_class=HTMLResponse)
def admin_responses(request: Request) -> HTMLResponse:
    """
    Serve the responses/logs dashboard HTML page.

    When ADMIN_OKTA_ENABLED is true and there is no authenticated session,
    render the same login preview as the admin home instead of returning a
    JSON redirect that Platform.sh pretty-prints.
    """
    session_user = _get_session_user(request)
    if OKTA_ADMIN_ENABLED and not session_user:
        return _render_login_html()

    responses_path = ADMIN_UI_DIR / "responses.html"
    try:
        html = responses_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin responses HTML not found.")
    return HTMLResponse(content=html)


@admin_router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request) -> HTMLResponse:
    """
    Serve the static admin dashboard HTML page.

    When ADMIN_OKTA_ENABLED is true and there is no authenticated session,
    render the shared login preview instead of a JSON redirect response.
    """
    session_user = _get_session_user(request)
    if OKTA_ADMIN_ENABLED and not session_user:
        return _render_login_html()

    index_path = ADMIN_UI_DIR / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin dashboard HTML not found.")
    return HTMLResponse(content=html)


