from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field

from config_db import get_db_connection


ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def require_admin(x_admin_api_key: Optional[str] = Header(default=None)) -> None:
    """
    Simple header-based auth for admin/dashboard endpoints.

    If ADMIN_API_KEY is set, all admin endpoints require an X-Admin-Api-Key header
    matching that value. If ADMIN_API_KEY is not set, the admin endpoints are open
    (intended for local development only).
    """
    if not ADMIN_API_KEY:
        # No admin key configured => do not enforce auth (development mode).
        return

    if x_admin_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


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
    name: str
    description_template: Optional[str] = None
    model_id: str
    is_active: bool = True
    instructions: List[AgentInstructionDTO] = Field(
        default_factory=list,
        description="Ordered list of instructions for this agent",
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


@admin_router.get("/dashboard", response_class=HTMLResponse)
def admin_dashboard() -> HTMLResponse:
    """Serve the static admin dashboard HTML page."""
    index_path = ADMIN_UI_DIR / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Admin dashboard HTML not found.")
    return HTMLResponse(content=html)


