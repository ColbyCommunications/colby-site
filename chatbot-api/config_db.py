from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional
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

        # Central store of admin-provided whitelist/blacklist training examples.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS query_examples (
                id INT AUTO_INCREMENT PRIMARY KEY,
                kind VARCHAR(32) NOT NULL,
                query_text TEXT NOT NULL,
                source_log_id INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_query_examples_log
                    FOREIGN KEY (source_log_id)
                    REFERENCES query_logs(id)
                    ON DELETE SET NULL,
                UNIQUE KEY uq_query_examples_kind_text (kind, query_text(255)),
                KEY idx_query_examples_kind (kind)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        )

        # Idempotent backfill: migrate any legacy BLACKLISTED/WHITELISTED examples
        # stored as agent_instructions for validator agents into query_examples.
        cursor.execute(
            """
            INSERT IGNORE INTO query_examples (kind, query_text)
            SELECT
                'blacklist' AS kind,
                TRIM(SUBSTRING_INDEX(ai.content, 'BLACKLISTED_QUERY_EXAMPLE: ', -1)) AS query_text
            FROM llm_agents AS a
            JOIN agent_instructions AS ai
                ON ai.agent_id = a.id
            WHERE a.agent_key IN ('validation_blacklist', 'validation_primary')
              AND ai.content LIKE 'BLACKLISTED_QUERY_EXAMPLE:%'
              AND TRIM(SUBSTRING_INDEX(ai.content, 'BLACKLISTED_QUERY_EXAMPLE: ', -1)) <> '';
            """
        )

        cursor.execute(
            """
            INSERT IGNORE INTO query_examples (kind, query_text)
            SELECT
                'whitelist' AS kind,
                TRIM(SUBSTRING_INDEX(ai.content, 'WHITELISTED_QUERY_EXAMPLE: ', -1)) AS query_text
            FROM llm_agents AS a
            JOIN agent_instructions AS ai
                ON ai.agent_id = a.id
            WHERE a.agent_key IN ('validation_blacklist', 'validation_primary')
              AND ai.content LIKE 'WHITELISTED_QUERY_EXAMPLE:%'
              AND TRIM(SUBSTRING_INDEX(ai.content, 'WHITELISTED_QUERY_EXAMPLE: ', -1)) <> '';
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

        # Filter out legacy training-example rows; the canonical source for
        # whitelist/blacklist examples is the query_examples table.
        instructions: List[str] = []
        for row in instructions_rows:
            content = (row.get("content") or "").strip()
            if content.startswith("BLACKLISTED_QUERY_EXAMPLE:") or content.startswith(
                "WHITELISTED_QUERY_EXAMPLE:"
            ):
                continue
            instructions.append(content)

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


def get_query_examples(kind: str) -> List[str]:
    """
    Return distinct query_text values for the given kind ('blacklist' or 'whitelist').

    If the configuration database or query_examples table is unavailable, this
    returns an empty list so callers can fail soft.
    """
    conn = get_db_connection()
    if conn is None:
        return []

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT DISTINCT query_text
            FROM query_examples
            WHERE kind = %s
            ORDER BY query_text ASC;
            """,
            (kind,),
        )
        rows = cursor.fetchall() or []
        return [row["query_text"] for row in rows if row.get("query_text")]
    except Exception:
        # If the table is missing or another error occurs, treat as no examples.
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


# --- Platform.sh metadata for OpenAI requests ---


def _parse_platform_routes() -> Optional[Dict[str, Any]]:
    """Parse PLATFORM_ROUTES (base64-encoded JSON) environment variable."""
    routes_env = os.environ.get("PLATFORM_ROUTES")
    if not routes_env:
        return None
    try:
        return json.loads(base64.b64decode(routes_env).decode("utf-8"))
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_openai_metadata() -> Dict[str, str]:
    """Build metadata dict for OpenAI requests from Platform.sh environment."""
    metadata: Dict[str, str] = {}

    routes = _parse_platform_routes()
    if routes:
        for url, route in routes.items():
            if isinstance(route, dict) and route.get("primary"):
                metadata["primary_url"] = url[:512]
                if route.get("production_url"):
                    metadata["production_url"] = route["production_url"][:512]
                break

    env = os.environ.get("PLATFORM_ENVIRONMENT") or os.environ.get("UPSUN_ENVIRONMENT")
    if env:
        metadata["environment"] = env[:512]
    project = os.environ.get("PLATFORM_PROJECT") or os.environ.get("UPSUN_PROJECT")
    if project:
        metadata["project"] = project[:512]
    branch = os.environ.get("PLATFORM_BRANCH") or os.environ.get("UPSUN_BRANCH")
    if branch:
        metadata["branch"] = branch[:512]
    app = os.environ.get("PLATFORM_APPLICATION_NAME") or os.environ.get("UPSUN_APPLICATION_NAME")
    if app:
        metadata["app_name"] = app[:512]

    return metadata


def get_openai_metadata_or_none() -> Optional[Dict[str, str]]:
    """Get metadata dict, or None if not running on Platform.sh."""
    metadata = get_openai_metadata()
    return metadata if metadata else None

