from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any, Dict, Optional

from mysql.connector.cursor import MySQLCursorDict

from config_db import get_db_connection


logger = logging.getLogger(__name__)


_current_log_id: ContextVar[Optional[int]] = ContextVar(
    "current_query_log_id", default=None
)
_blocked_by_stage: ContextVar[Optional[str]] = ContextVar(
    "current_query_blocked_by", default=None
)


def _get_log_cursor() -> Optional[MySQLCursorDict]:
    """
    Helper to obtain a dictionary cursor for the config DB.

    Returns None if the DB is unavailable; callers should handle gracefully.
    """
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        return conn.cursor(dictionary=True)
    except Exception:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        return None


def get_current_log_id() -> Optional[int]:
    """Return the current query_log id (if any) for this request context."""
    return _current_log_id.get()


def mark_blocked_by(stage: str) -> None:
    """
    Record which stage (e.g. 'validation_primary', 'validation_blacklist')
    ultimately blocked this query.
    """
    if not stage:
        return
    _blocked_by_stage.set(stage)


def get_blocked_by() -> Optional[str]:
    """Return the stage that marked this query as blocked, if any."""
    return _blocked_by_stage.get()


def clear_request_log_context() -> None:
    """
    Clear per-request logging context.

    This is safe to call multiple times and is typically used in a finally block.
    """
    try:
        _current_log_id.set(None)
    except Exception:  # noqa: BLE001
        pass
    try:
        _blocked_by_stage.set(None)
    except Exception:  # noqa: BLE001
        pass


def start_request_log(user_message: str) -> None:
    """
    Insert a new row into query_logs for this request and remember its id.

    If the configuration DB is unavailable, this becomes a no-op.
    """
    conn = get_db_connection()
    if conn is None:
        logger.debug("Query logging disabled: config DB unavailable.")
        return

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)
        cursor.execute(
            """
            INSERT INTO query_logs (user_message, status)
            VALUES (%s, %s);
            """,
            (user_message, "pending"),
        )
        log_id = cursor.lastrowid
        _current_log_id.set(int(log_id))
        _blocked_by_stage.set(None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to start query log: %s", exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def add_log_part(
    *,
    stage: str,
    model_id: Optional[str],
    agent_name: Optional[str],
    using_db_config: Optional[bool],
    result: Dict[str, Any],
    blocked: Optional[bool] = None,
) -> None:
    """
    Append a per-stage metadata row under the current query log.

    This records which model ran (and how it reasoned) at each step:
    - validation_blacklist
    - validation_primary
    - runtime_rag
    """
    log_id = get_current_log_id()
    if not log_id:
        # Logging not active for this request.
        return

    conn = get_db_connection()
    if conn is None:
        return

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)
        json_payload = json.dumps(result, ensure_ascii=False, default=str)
        cursor.execute(
            """
            INSERT INTO query_log_parts (
                query_log_id,
                stage,
                model_id,
                agent_name,
                using_db_config,
                blocked,
                result_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                log_id,
                stage,
                model_id,
                agent_name,
                int(using_db_config) if using_db_config is not None else None,
                int(blocked) if blocked is not None else None,
                json_payload,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to append query_log_part for id %s: %s", log_id, exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


def finalize_request_log(
    *,
    status: str,
    final_answer: Optional[str],
    error_message: Optional[str] = None,
    blocked_by: Optional[str] = None,
) -> None:
    """
    Mark the current query log as completed with its final status.

    status:
      - 'answered' for normal successful answers
      - 'blocked' when a validator rejects the query
      - 'error' for unexpected runtime failures
    """
    log_id = get_current_log_id()
    if not log_id:
        clear_request_log_context()
        return

    conn = get_db_connection()
    if conn is None:
        clear_request_log_context()
        return

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)
        effective_blocked_by = blocked_by or get_blocked_by()
        cursor.execute(
            """
            UPDATE query_logs
            SET status = %s,
                final_answer = %s,
                blocked_by = %s,
                error_message = %s
            WHERE id = %s;
            """,
            (
                status,
                final_answer,
                effective_blocked_by,
                error_message,
                log_id,
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to finalize query_log %s: %s", log_id, exc)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
        # Always clear context so it does not leak across requests.
        clear_request_log_context()


