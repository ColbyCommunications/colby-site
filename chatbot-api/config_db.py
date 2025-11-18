from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import mysql.connector
from mysql.connector.connection import MySQLConnection
from mysql.connector.cursor import MySQLCursorDict


@dataclass
class AgentConfig:
    """Configuration for a single logical agent (runtime, validation, etc.)."""

    agent_key: str
    name: str
    description_template: Optional[str]
    model_id: str
    instructions: List[str]


def _parse_platform_relationships() -> Optional[dict]:
    """
    Parse Platform.sh / Upsun relationships to extract MySQL credentials.

    The `.platform.app.yaml` defines:
      relationships:
        configdb: "mysqldb:mysql"
    """
    rel_env = os.environ.get("PLATFORM_RELATIONSHIPS") or os.environ.get(
        "UPSUN_RELATIONSHIPS"
    )
    if not rel_env:
        return None

    try:
        decoded = base64.b64decode(rel_env).decode("utf-8")
        relationships = json.loads(decoded)
        return relationships.get("configdb", [None])[0]
    except Exception:
        return None


def _parse_config_db_url() -> Optional[dict]:
    """
    Parse CONFIG_DB_URL style connection strings, e.g.:
      mysql://user:pass@host:3306/dbname
    """
    url = os.environ.get("CONFIG_DB_URL")
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.scheme not in ("mysql", "mysql2"):
        return None

    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "",
        "password": parsed.password or "",
        "database": (parsed.path or "").lstrip("/") or "",
    }


def _get_db_connection_params() -> Optional[dict]:
    """
    Resolve DB connection parameters from either CONFIG_DB_URL or
    Platform.sh / Upsun relationships.
    """
    direct = _parse_config_db_url()
    if direct:
        return direct

    rel = _parse_platform_relationships()
    if not rel:
        return None

    return {
        "host": rel.get("host", "localhost"),
        "port": int(rel.get("port", 3306)),
        "user": rel.get("username", ""),
        "password": rel.get("password", ""),
        "database": rel.get("path", ""),
    }


def get_db_connection() -> Optional[MySQLConnection]:
    """
    Create a new MySQL connection to the configuration database.

    Returns None if connection details are not available; callers should
    gracefully fall back to in-code defaults in that case.
    """
    params = _get_db_connection_params()
    if not params:
        return None

    try:
        return mysql.connector.connect(
            host=params["host"],
            port=params["port"],
            user=params["user"],
            password=params["password"],
            database=params["database"],
            autocommit=True,
        )
    except Exception:
        return None


def init_config_schema() -> None:
    """
    Initialize the configuration schema if it does not yet exist.

    This is intentionally idempotent and safe to call multiple times.
    """
    conn = get_db_connection()
    if conn is None:
        return

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)

        # Core model catalogue: which LLM models are available to choose from.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_models (
                id INT AUTO_INCREMENT PRIMARY KEY,
                model_id VARCHAR(255) NOT NULL,
                provider VARCHAR(64) NOT NULL DEFAULT 'openai',
                display_name VARCHAR(255) NOT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                is_default TINYINT(1) NOT NULL DEFAULT 0,
                UNIQUE KEY uq_model_id (model_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Logical agents (runtime RAG, validators, etc.).
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_agents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                agent_key VARCHAR(64) NOT NULL,
                name VARCHAR(255) NOT NULL,
                description_template TEXT NULL,
                model_id VARCHAR(255) NOT NULL,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                UNIQUE KEY uq_agent_key (agent_key),
                KEY idx_agent_model (model_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Ordered instructions for each agent.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_instructions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                agent_id INT NOT NULL,
                position INT NOT NULL,
                content TEXT NOT NULL,
                UNIQUE KEY uq_agent_position (agent_id, position),
                CONSTRAINT fk_agent_instructions_agent
                    FOREIGN KEY (agent_id)
                    REFERENCES llm_agents(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Simple key/value messages (e.g., standard rejection message).
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_key VARCHAR(64) NOT NULL,
                content TEXT NOT NULL,
                UNIQUE KEY uq_message_key (message_key)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Query/response logs: one row per user request.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS query_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                user_message TEXT NOT NULL,
                final_answer MEDIUMTEXT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                blocked_by VARCHAR(64) NULL,
                error_message TEXT NULL,
                INDEX idx_query_created_at (created_at),
                INDEX idx_query_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Detailed per-stage metadata for each query (validators, runtime agent, etc.).
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS query_log_parts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                query_log_id INT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                stage VARCHAR(64) NOT NULL,
                model_id VARCHAR(255) NULL,
                agent_name VARCHAR(255) NULL,
                using_db_config TINYINT(1) NULL,
                blocked TINYINT(1) NULL,
                result_json MEDIUMTEXT NULL,
                INDEX idx_query_log_parts_query (query_log_id),
                CONSTRAINT fk_query_log_parts_query
                    FOREIGN KEY (query_log_id)
                    REFERENCES query_logs(id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

    finally:
        try:
            conn.close()
        except Exception:
            pass


def _fetchone(
    cursor: MySQLCursorDict, query: str, params: Iterable[object]
) -> Optional[dict]:
    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    return row if row else None


def _fetchall(
    cursor: MySQLCursorDict, query: str, params: Iterable[object]
) -> List[dict]:
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    return list(rows or [])


def load_agent_config(agent_key: str) -> Optional[AgentConfig]:
    """
    Load agent configuration (model + ordered instructions) for a given key.

    The `description_template` may contain optional placeholders:
      {current_date}               - human-readable EST date string
      {standard_rejection_message} - current standard rejection message
    which the caller can substitute at runtime.
    """
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)

        agent_row = _fetchone(
            cursor,
            """
            SELECT id, agent_key, name, description_template, model_id
            FROM llm_agents
            WHERE agent_key = %s AND is_active = 1
            LIMIT 1;
            """,
            [agent_key],
        )
        if not agent_row:
            return None

        instructions_rows = _fetchall(
            cursor,
            """
            SELECT content
            FROM agent_instructions
            WHERE agent_id = %s
            ORDER BY position ASC, id ASC;
            """,
            [agent_row["id"]],
        )

        instructions = [row["content"] for row in instructions_rows]

        return AgentConfig(
            agent_key=agent_row["agent_key"],
            name=agent_row["name"],
            description_template=agent_row.get("description_template"),
            model_id=agent_row["model_id"],
            instructions=instructions,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_app_message(message_key: str) -> Optional[str]:
    """
    Fetch a single application-level message (e.g. standard rejection message).
    """
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)
        row = _fetchone(
            cursor,
            """
            SELECT content
            FROM app_messages
            WHERE message_key = %s
            LIMIT 1;
            """,
            [message_key],
        )
        if not row:
            return None
        return row["content"]
    finally:
        try:
            conn.close()
        except Exception:
            pass


