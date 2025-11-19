from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
from urllib.parse import urlencode
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from pydantic import BaseModel, Field

from config_db import get_db_connection
from okta_auth import (
    OktaConfigError,
    OKTA_SESSION_USER_KEY,
    OKTA_SESSION_STATE_KEY,
    OKTA_SESSION_CODE_VERIFIER_KEY,
    OKTA_SESSION_ID_TOKEN_KEY,
    get_okta_config,
)


# Paths that are exempt from Okta session checks so that the login and callback
# routes can bootstrap authentication. These are defined relative to the app's
# root (that is, they don't include any root_path such as /chatbot-api).
_ADMIN_AUTH_EXEMPT_PATHS = {
    "/admin/login",
    "/admin/authorization-code/callback",
    "/admin/logout",
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
        return stripped

    return full_path


def require_admin(request: Request) -> None:
    """
    Okta-backed auth for all /admin endpoints.

    - If the request targets an exempt path (login, callback, logout), skip checks.
    - Otherwise, ensure Okta is configured and that a valid okta_user is present
      in the session. If not, redirect the client to /admin/login.
    """
    path = _get_request_path(request)
    if path in _ADMIN_AUTH_EXEMPT_PATHS:
        # Allow login/callback/logout endpoints without an existing session.
        return

    try:
        # Ensure Okta configuration is present; this will raise if required envs
        # are missing.
        get_okta_config()
    except OktaConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if request.session.get(OKTA_SESSION_USER_KEY):
        # Already authenticated via Okta.
        return

    # Not authenticated: redirect into the Okta login flow.
    login_url = request.url_for("admin_login")
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
    try:
        config = get_okta_config()
    except OktaConfigError as exc:
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
    return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)


@admin_router.get("/authorization-code/callback", name="admin_callback")
def admin_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None) -> RedirectResponse:
    """
    Okta authorization code callback.

    Exchanges the authorization code for tokens, fetches userinfo, and stores
    a minimal Okta user profile in the session. Finally, redirects to /admin/.
    """
    try:
        config = get_okta_config()
    except OktaConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not state or state != request.session.get(OKTA_SESSION_STATE_KEY):
        raise HTTPException(status_code=400, detail="Invalid or missing state parameter.")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code was not returned.")

    code_verifier = request.session.get(OKTA_SESSION_CODE_VERIFIER_KEY)
    if not code_verifier:
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
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange authorization code for tokens: {exc}",
        ) from exc

    exchange = token_resp.json()

    if exchange.get("token_type") != "Bearer":
        raise HTTPException(
            status_code=403,
            detail="Unsupported token type from Okta. Expected 'Bearer'.",
        )

    access_token = exchange.get("access_token")
    id_token = exchange.get("id_token")
    if not access_token:
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

    # Redirect to the admin home, respecting root_path.
    redirect_url = request.url_for("admin_home")
    return RedirectResponse(str(redirect_url), status_code=status.HTTP_302_FOUND)


@admin_router.get("/logout", name="admin_logout")
def admin_logout(request: Request) -> RedirectResponse:
    """
    Clear the Okta-backed admin session and optionally invoke Okta global logout.
    """
    # Always clear local session state first.
    id_token = request.session.pop(OKTA_SESSION_ID_TOKEN_KEY, None)
    request.session.pop(OKTA_SESSION_USER_KEY, None)
    request.session.pop(OKTA_SESSION_STATE_KEY, None)
    request.session.pop(OKTA_SESSION_CODE_VERIFIER_KEY, None)

    try:
        config = get_okta_config()
    except OktaConfigError:
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


@admin_router.get("/query-logs", response_model=List[QueryLogDTO])
def list_query_logs(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: answered, blocked, or error.",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> List[QueryLogDTO]:
    """
    List query/response logs for a given date range, optionally filtered by text.

    Dates are inclusive and expected in YYYY-MM-DD format.
    """
    conn = _get_required_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        clauses = []
        params: List[Any] = []

        start = _parse_date_param(start_date)
        end = _parse_date_param(end_date)

        if start:
            clauses.append("q.created_at >= %s")
            params.append(datetime.combine(start, datetime.min.time()))
        if end:
            # inclusive end-date -> next day at midnight
            end_next = end + timedelta(days=1)
            clauses.append("q.created_at < %s")
            params.append(datetime.combine(end_next, datetime.min.time()))

        if q:
            like = f"%{q}%"
            clauses.append("(q.user_message LIKE %s OR q.final_answer LIKE %s)")
            params.extend([like, like])

        if status_filter:
            allowed_statuses = {"answered", "blocked", "error"}
            if status_filter not in allowed_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status filter {status_filter!r}. "
                    f"Expected one of {sorted(allowed_statuses)!r}.",
                )
            clauses.append("q.status = %s")
            params.append(status_filter)

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
                    FROM llm_agents a
                    JOIN agent_instructions ai ON ai.agent_id = a.id
                    WHERE a.agent_key = 'validation_blacklist'
                      AND ai.content = CONCAT('BLACKLISTED_QUERY_EXAMPLE: ', q.user_message)
                    LIMIT 1
                ) AS is_blacklist_example,
                EXISTS (
                    SELECT 1
                    FROM llm_agents a2
                    JOIN agent_instructions ai2 ON ai2.agent_id = a2.id
                    WHERE a2.agent_key = 'validation_blacklist'
                      AND ai2.content = CONCAT('WHITELISTED_QUERY_EXAMPLE: ', q.user_message)
                    LIMIT 1
                ) AS is_whitelist_example
            FROM query_logs AS q
            {where_sql}
            ORDER BY q.created_at DESC
            LIMIT %s OFFSET %s;
        """
        params.extend([limit, offset])

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
                    FROM llm_agents a
                    JOIN agent_instructions ai ON ai.agent_id = a.id
                    WHERE a.agent_key = 'validation_blacklist'
                      AND ai.content = CONCAT('BLACKLISTED_QUERY_EXAMPLE: ', q.user_message)
                    LIMIT 1
                ) AS is_blacklist_example,
                EXISTS (
                    SELECT 1
                    FROM llm_agents a2
                    JOIN agent_instructions ai2 ON ai2.agent_id = a2.id
                    WHERE a2.agent_key = 'validation_blacklist'
                      AND ai2.content = CONCAT('WHITELISTED_QUERY_EXAMPLE: ', q.user_message)
                    LIMIT 1
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
    blacklist example instruction for the 'validation_blacklist' agent.
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
            raise HTTPException(status_code=400, detail="Query log has no user_message to blacklist.")

        # Find the validation_blacklist agent.
        cursor.execute(
            """
            SELECT id
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            ("validation_blacklist",),
        )
        agent_row = cursor.fetchone()
        if not agent_row:
            raise HTTPException(
                status_code=404,
                detail="validation_blacklist agent not found. Configure it in the admin dashboard first.",
            )

        agent_id = agent_row["id"]

        # Avoid duplicate entries for the same query.
        instruction_content = f"BLACKLISTED_QUERY_EXAMPLE: {user_message}"
        cursor.execute(
            """
            SELECT id
            FROM agent_instructions
            WHERE agent_id = %s AND content = %s
            LIMIT 1;
            """,
            (agent_id, instruction_content),
        )
        existing = cursor.fetchone()
        if existing:
            return {
                "status": "ok",
                "message": "Query is already present in validation_blacklist instructions.",
            }

        # Determine next position.
        cursor.execute(
            """
            SELECT COALESCE(MAX(position), 0) AS max_pos
            FROM agent_instructions
            WHERE agent_id = %s;
            """,
            (agent_id,),
        )
        pos_row = cursor.fetchone() or {"max_pos": 0}
        next_position = int(pos_row.get("max_pos") or 0) + 1

        # Insert new blacklist instruction.
        cursor.execute(
            """
            INSERT INTO agent_instructions (
                agent_id,
                position,
                content
            )
            VALUES (%s, %s, %s);
            """,
            (agent_id, next_position, instruction_content),
        )

        return {
            "status": "ok",
            "message": "Query added to validation_blacklist instructions as BLACKLISTED_QUERY_EXAMPLE.",
            "agent_id": agent_id,
            "position": next_position,
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
    whitelist example instruction for the 'validation_blacklist' agent.
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
            raise HTTPException(status_code=400, detail="Query log has no user_message to whitelist.")

        # Find the validation_blacklist agent.
        cursor.execute(
            """
            SELECT id
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            ("validation_blacklist",),
        )
        agent_row = cursor.fetchone()
        if not agent_row:
            raise HTTPException(
                status_code=404,
                detail="validation_blacklist agent not found. Configure it in the admin dashboard first.",
            )

        agent_id = agent_row["id"]

        # Avoid duplicate entries for the same query.
        instruction_content = f"WHITELISTED_QUERY_EXAMPLE: {user_message}"
        cursor.execute(
            """
            SELECT id
            FROM agent_instructions
            WHERE agent_id = %s AND content = %s
            LIMIT 1;
            """,
            (agent_id, instruction_content),
        )
        existing = cursor.fetchone()
        if existing:
            return {
                "status": "ok",
                "message": "Query is already present in validation_blacklist whitelist instructions.",
            }

        # Determine next position.
        cursor.execute(
            """
            SELECT COALESCE(MAX(position), 0) AS max_pos
            FROM agent_instructions
            WHERE agent_id = %s;
            """,
            (agent_id,),
        )
        pos_row = cursor.fetchone() or {"max_pos": 0}
        next_position = int(pos_row.get("max_pos") or 0) + 1

        # Insert new whitelist instruction.
        cursor.execute(
            """
            INSERT INTO agent_instructions (
                agent_id,
                position,
                content
            )
            VALUES (%s, %s, %s);
            """,
            (agent_id, next_position, instruction_content),
        )

        return {
            "status": "ok",
            "message": "Query added to validation_blacklist instructions as WHITELISTED_QUERY_EXAMPLE.",
            "agent_id": agent_id,
            "position": next_position,
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/query-logs/{log_id}/blacklist", status_code=200)
def remove_query_from_blacklist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Remove a BLACKLISTED_QUERY_EXAMPLE instruction matching this log's user_message.
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
            SELECT id
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            ("validation_blacklist",),
        )
        agent_row = cursor.fetchone()
        if not agent_row:
            raise HTTPException(
                status_code=404,
                detail="validation_blacklist agent not found. Configure it in the admin dashboard first.",
            )

        agent_id = agent_row["id"]
        instruction_content = f"BLACKLISTED_QUERY_EXAMPLE: {user_message}"

        cursor.execute(
            """
            DELETE FROM agent_instructions
            WHERE agent_id = %s AND content = %s;
            """,
            (agent_id, instruction_content),
        )
        deleted = cursor.rowcount or 0

        if deleted == 0:
            return {
                "status": "ok",
                "message": "Query was not present in blacklist instructions.",
            }

        return {
            "status": "ok",
            "message": "Query removed from BLACKLISTED_QUERY_EXAMPLE instructions.",
        }
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@admin_router.delete("/query-logs/{log_id}/whitelist", status_code=200)
def remove_query_from_whitelist_from_log(log_id: int) -> Dict[str, Any]:
    """
    Remove a WHITELISTED_QUERY_EXAMPLE instruction matching this log's user_message.
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
            SELECT id
            FROM llm_agents
            WHERE agent_key = %s
            LIMIT 1;
            """,
            ("validation_blacklist",),
        )
        agent_row = cursor.fetchone()
        if not agent_row:
            raise HTTPException(
                status_code=404,
                detail="validation_blacklist agent not found. Configure it in the admin dashboard first.",
            )

        agent_id = agent_row["id"]
        instruction_content = f"WHITELISTED_QUERY_EXAMPLE: {user_message}"

        cursor.execute(
            """
            DELETE FROM agent_instructions
            WHERE agent_id = %s AND content = %s;
            """,
            (agent_id, instruction_content),
        )
        deleted = cursor.rowcount or 0

        if deleted == 0:
            return {
                "status": "ok",
                "message": "Query was not present in whitelist instructions.",
            }

        return {
            "status": "ok",
            "message": "Query removed from WHITELISTED_QUERY_EXAMPLE instructions.",
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


@admin_router.get("/", response_class=HTMLResponse)
def admin_home() -> HTMLResponse:
    """Serve the admin landing page with navigation cards."""
    home_path = ADMIN_UI_DIR / "home.html"
    try:
        html = home_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin home HTML not found.")
    return HTMLResponse(content=html)


@admin_router.get("/responses", response_class=HTMLResponse)
def admin_responses() -> HTMLResponse:
    """Serve the responses/logs dashboard HTML page."""
    responses_path = ADMIN_UI_DIR / "responses.html"
    try:
        html = responses_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin responses HTML not found.")
    return HTMLResponse(content=html)


@admin_router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard() -> HTMLResponse:
    """Serve the static admin dashboard HTML page."""
    index_path = ADMIN_UI_DIR / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin dashboard HTML not found.")
    return HTMLResponse(content=html)


