from __future__ import annotations

import html
import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import List, Optional
from zoneinfo import ZoneInfo

from mysql.connector.cursor import MySQLCursorDict

from config_db import get_db_connection


@dataclass
class QueryExample:
    """Single example query text with an occurrence count for the day."""

    user_message: str
    count: int


@dataclass
class DailyMetrics:
    """Aggregated chatbot activity metrics for a single calendar day (ET)."""

    target_date: date
    total_queries: int
    answered: int
    blocked: int
    error: int
    blocked_by_agent_1: int
    blocked_by_agent_2: int
    blocked_by_both: int
    passed_guardrails: int
    no_answer_after_pass: int
    top_answered_queries: List[QueryExample]
    top_blocked_queries: List[QueryExample]


def _day_utc_range_for_et(target_date: date) -> tuple[datetime, datetime]:
    """
    Return [start_utc, end_utc) for the given ET calendar date.

    This mirrors the behaviour used in admin_api.list_query_logs so that
    "Today" in the email matches what the dashboard shows.
    """
    est_tz = ZoneInfo("America/New_York")

    start_local = datetime.combine(target_date, datetime.min.time(), tzinfo=est_tz)
    end_local = datetime.combine(
        target_date + timedelta(days=1),
        datetime.min.time(),
        tzinfo=est_tz,
    )

    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def fetch_daily_metrics(target_date: Optional[date] = None) -> DailyMetrics:
    """
    Compute daily chatbot metrics from query_logs + query_log_parts.

    Metrics include:
    - total queries, answered, blocked, error
    - queries blocked by Agent 1 (validation_primary) / Agent 2 (validation_blacklist)
    - queries blocked by both validators
    - queries that passed both validators (guardrails) overall
    - queries that passed both validators but produced no final answer
    - up to 10 most frequent answered queries
    - up to 10 most frequent rejected (blocked) queries
    """
    if target_date is None:
        target_date = date.today()

    start_utc, end_utc = _day_utc_range_for_et(target_date)

    conn = get_db_connection()
    if conn is None:
        raise RuntimeError("Configuration database is not available.")

    try:
        cursor: MySQLCursorDict = conn.cursor(dictionary=True)

        # --- Core counts by status ---
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

        # --- Guardrail behaviour by validator (Agent 1 / Agent 2) ---
        cursor.execute(
            """
            SELECT
                SUM(CASE WHEN has_primary_blocked = 1 THEN 1 ELSE 0 END) AS blocked_by_agent_1,
                SUM(CASE WHEN has_blacklist_blocked = 1 THEN 1 ELSE 0 END) AS blocked_by_agent_2,
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
        blocked_by_agent_1 = int(guard.get("blocked_by_agent_1") or 0)
        blocked_by_agent_2 = int(guard.get("blocked_by_agent_2") or 0)
        blocked_by_both = int(guard.get("blocked_by_both") or 0)
        passed_guardrails = int(guard.get("passed_guardrails") or 0)

        # --- Passed guardrails but main agent had no answer ---
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
              AND (q.final_answer IS NULL OR TRIM(q.final_answer) = '')
              AND q.status != 'blocked';
            """,
            (start_utc, end_utc),
        )
        row = cursor.fetchone() or {}
        no_answer_after_pass = int(row.get("no_answer_after_pass") or 0)

        # --- Top answered queries (by frequency, then recency) ---
        cursor.execute(
            """
            SELECT user_message, COUNT(*) AS cnt, MAX(created_at) AS last_seen
            FROM query_logs
            WHERE created_at >= %s AND created_at < %s
              AND status = 'answered'
            GROUP BY user_message
            ORDER BY cnt DESC, last_seen DESC
            LIMIT 10;
            """,
            (start_utc, end_utc),
        )
        answered_rows = cursor.fetchall() or []
        top_answered_queries: List[QueryExample] = [
            QueryExample(
                user_message=row["user_message"],
                count=int(row["cnt"] or 0),
            )
            for row in answered_rows
        ]

        # --- Top rejected / blocked queries (by frequency, then recency) ---
        cursor.execute(
            """
            SELECT user_message, COUNT(*) AS cnt, MAX(created_at) AS last_seen
            FROM query_logs
            WHERE created_at >= %s AND created_at < %s
              AND status = 'blocked'
            GROUP BY user_message
            ORDER BY cnt DESC, last_seen DESC
            LIMIT 10;
            """,
            (start_utc, end_utc),
        )
        blocked_rows = cursor.fetchall() or []
        top_blocked_queries: List[QueryExample] = [
            QueryExample(
                user_message=row["user_message"],
                count=int(row["cnt"] or 0),
            )
            for row in blocked_rows
        ]

        return DailyMetrics(
            target_date=target_date,
            total_queries=total_queries,
            answered=answered,
            blocked=blocked,
            error=error,
            blocked_by_agent_1=blocked_by_agent_1,
            blocked_by_agent_2=blocked_by_agent_2,
            blocked_by_both=blocked_by_both,
            passed_guardrails=passed_guardrails,
            no_answer_after_pass=no_answer_after_pass,
            top_answered_queries=top_answered_queries,
            top_blocked_queries=top_blocked_queries,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _format_percent(numerator: int, denominator: int) -> str:
    """Return a pretty percentage string like '0', '12.5', or '100'."""
    if denominator <= 0:
        return "0"
    pct = (numerator / denominator) * 100.0
    # Keep one decimal place, but strip trailing .0 for clean display.
    txt = f"{pct:.1f}"
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt


def _render_query_list_html(examples: List[QueryExample], empty_text: str) -> str:
    """Render an ordered list of query examples (or a muted empty-state text)."""
    if not examples:
        return (
            '<div style="font-size:12px; color:#9ca3af;">'
            f"{html.escape(empty_text)}"
            "</div>"
        )

    parts: List[str] = []
    parts.append(
        '<ol style="margin:0; padding-left:18px; font-size:12px; color:#0f172a;">'
    )
    for ex in examples:
        text = (ex.user_message or "").strip()
        if len(text) > 260:
            text = text[:257] + "…"
        safe_text = html.escape(text)
        suffix = ""
        if ex.count > 1:
            suffix = (
                ' <span style="color:#6b7280;">'
                f"({ex.count}×)"
                "</span>"
            )
        parts.append(
            f'<li style="margin-bottom:4px;">{safe_text}{suffix}</li>'
        )
    parts.append("</ol>")

    return "\n".join(parts)


_BASE_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Colby Chatbot – Daily Analytics</title>
  </head>
  <body style="margin:0; padding:0; background-color:#f4f6fb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#f4f6fb; padding:24px 0;">
      <tr>
        <td align="center">
          <table width="640" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 6px 18px rgba(15, 23, 42, 0.08);">
            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg, #003f7d, #0f6fcf); padding:24px 32px; color:#ffffff;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                  <tr>
                    <td align="left">
                      <div style="font-size:13px; letter-spacing:0.15em; text-transform:uppercase; opacity:0.8;">
                        Colby Chatbot
                      </div>
                      <div style="font-size:22px; font-weight:600; margin-top:6px;">
                        Daily Analytics Summary
                      </div>
                      <div style="font-size:13px; margin-top:6px; opacity:0.9;">
                        {analytics_date}
                      </div>
                    </td>
                    <td align="right" style="vertical-align:top;">
                      <a href="https://www.chatbot-hbxlydq-ouiqvb5juucvu.us-4.platformsh.site/chatbot-api/admin/" target="_blank" rel="noopener noreferrer" style="text-decoration:none; color:inherit;">
                        <span style="display:inline-block; padding:6px 12px; border-radius:999px; background:rgba(15, 23, 42, 0.18); font-size:11px; font-weight:500;">
                          Go to Dashboard &rarr;
                        </span>
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Key metrics (3 columns) -->
            <tr>
              <td style="padding:4px 24px 4px 24px;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                  <tr>
                    <!-- Total queries -->
                    <td width="33.33%" style="padding:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; background-color:#f8fafc; border:1px solid #e2e8f0;">
                        <tr>
                          <td style="padding:12px 14px;">
                            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#94a3b8; font-weight:600;">
                              Total queries
                            </div>
                            <div style="font-size:24px; font-weight:600; color:#0f172a; margin-top:4px;">
                              {total_queries}
                            </div>
                            <div style="font-size:11px; color:#64748b; margin-top:4px;">
                              Across all agents yesterday
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>

                    <!-- Answered -->
                    <td width="33.33%" style="padding:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; background-color:#ecfdf3; border:1px solid #bbf7d0;">
                        <tr>
                          <td style="padding:12px 14px;">
                            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#16a34a; font-weight:600;">
                              Answered
                            </div>
                            <div style="font-size:24px; font-weight:600; color:#14532d; margin-top:4px;">
                              {queries_answered}
                            </div>
                            <div style="font-size:11px; color:#166534; margin-top:4px;">
                              {answered_rate}% of all queries
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>

                    <!-- Blocked -->
                    <td width="33.33%" style="padding:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; background-color:#fef2f2; border:1px solid #fecaca;">
                        <tr>
                          <td style="padding:12px 14px;">
                            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:#b91c1c; font-weight:600;">
                              Blocked
                            </div>
                            <div style="font-size:24px; font-weight:600; color:#7f1d1d; margin-top:4px;">
                              {queries_blocked}
                            </div>
                            <div style="font-size:11px; color:#b91c1c; margin-top:4px;">
                              {blocked_rate}% flagged as unsafe or out of scope
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Guardrail breakdown -->
            <tr>
              <td style="padding:4px 24px 16px 24px;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                  <tr>
                    <td width="50%" style="padding:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; background-color:#f8fafc; border:1px solid #e2e8f0;">
                        <tr>
                          <td style="padding:12px 14px;">
                            <div style="font-size:12px; font-weight:600; color:#0f172a; margin-bottom:6px;">
                              Guardrail performance
                            </div>
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="font-size:12px; color:#475569;">
                              <tr>
                                <td style="padding:4px 0;">Blocked by Colby Query Validator</td>
                                <td align="right" style="padding:4px 0; font-weight:600;">
                                  {blocked_by_agent_1}
                                </td>
                              </tr>
                              <tr>
                                <td style="padding:4px 0;">Blocked by Colby Blacklist Validator</td>
                                <td align="right" style="padding:4px 0; font-weight:600;">
                                  {blocked_by_agent_2}
                                </td>
                              </tr>
                              <tr>
                                <td style="padding:4px 0;">Blocked by both</td>
                                <td align="right" style="padding:4px 0; font-weight:600;">
                                  {blocked_by_both}
                                </td>
                              </tr>
                              <tr>
                                <td style="padding:4px 0;">Passed guardrails</td>
                                <td align="right" style="padding:4px 0; font-weight:600; color:#15803d;">
                                  {passed_guardrails}
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                      </table>
                    </td>

                    <td width="50%" style="padding:8px;">
                      <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; background-color:#fefce8; border:1px solid #facc15;">
                        <tr>
                          <td style="padding:12px 14px;">
                            <div style="font-size:12px; font-weight:600; color:#713f12; margin-bottom:6px;">
                              No‑answer cases
                            </div>
                            <div style="font-size:12px; color:#854d0e; line-height:1.5;">
                              {no_answer_after_pass} queries passed both guardrail agents
                              but the main answer agent had no confident response.
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Top answered / rejected queries -->
            <tr>
              <td style="padding:8px 32px 4px 32px;">
                <div style="font-size:13px; font-weight:600; color:#0f172a; margin-bottom:6px;">
                  Top answered queries
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:0 24px 12px 24px;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; border:1px solid #e2e8f0; background-color:#ffffff;">
                  <tr>
                    <td style="padding:10px 14px;">
                      {top_answered_html}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="padding:8px 32px 4px 32px;">
                <div style="font-size:13px; font-weight:600; color:#0f172a; margin-bottom:6px;">
                  Top rejected queries
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:0 24px 12px 24px;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border-radius:10px; border:1px solid #e2e8f0; background-color:#ffffff;">
                  <tr>
                    <td style="padding:10px 14px;">
                      {top_blocked_html}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="padding:16px 32px 24px 32px; border-top:1px solid #e5e7eb;">
                <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                  <tr>
                    <td align="left" style="font-size:11px; color:#9ca3af;">
                      Sent from the Colby Chatbot Dashboard.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def render_daily_email_html(metrics: DailyMetrics) -> str:
    """Render a styled HTML email for the given day's metrics."""
    total = metrics.total_queries
    answered_rate = _format_percent(metrics.answered, total)
    blocked_rate = _format_percent(metrics.blocked, total)

    est_tz = ZoneInfo("America/New_York")
    # Human-friendly analytics day label in ET (single date, not a range).
    analytics_date = metrics.target_date.strftime("%B %d, %Y")

    top_answered_html = _render_query_list_html(
        metrics.top_answered_queries,
        empty_text="No answered queries were recorded for this day.",
    )
    top_blocked_html = _render_query_list_html(
        metrics.top_blocked_queries,
        empty_text="No rejected queries were recorded for this day.",
    )

    return _BASE_EMAIL_TEMPLATE.format(
        analytics_date=analytics_date,
        total_queries=metrics.total_queries,
        queries_answered=metrics.answered,
        answered_rate=answered_rate,
        queries_blocked=metrics.blocked,
        blocked_rate=blocked_rate,
        blocked_by_agent_1=metrics.blocked_by_agent_1,
        blocked_by_agent_2=metrics.blocked_by_agent_2,
        blocked_by_both=metrics.blocked_by_both,
        passed_guardrails=metrics.passed_guardrails,
        no_answer_after_pass=metrics.no_answer_after_pass,
        top_answered_html=top_answered_html,
        top_blocked_html=top_blocked_html,
    )


def send_daily_email(
    metrics: DailyMetrics,
    to_addresses: List[str],
    from_address: Optional[str] = None,
    smtp_host: Optional[str] = None,
) -> None:
    """
    Send the daily analytics email via Upsun's SMTP proxy.

    - smtp_host defaults to PLATFORM_SMTP_HOST (or localhost as a fallback).
    - from_address defaults to DAILY_REPORT_FROM_EMAIL or 'chatbot@colby.edu'.
    """
    if not to_addresses:
        raise ValueError("At least one recipient address is required.")

    if from_address is None:
        from_address = os.environ.get("DAILY_REPORT_FROM_EMAIL", "chatbot@colby.edu")

    # SMTP host resolution order:
    # 1) Explicit smtp_host argument (if provided)
    # 2) SMTP_HOST env var (handy for local dev)
    # 3) PLATFORM_SMTP_HOST (set automatically inside Upsun)
    # 4) "localhost" as a final fallback
    if smtp_host is None:
        smtp_host = (
            os.environ.get("SMTP_HOST")
            or os.environ.get("PLATFORM_SMTP_HOST")
            or "localhost"
        )

    subject = f"Colby Chatbot – Daily Analytics ({metrics.target_date.isoformat()})"
    html_body = render_daily_email_html(metrics)

    msg = EmailMessage()
    msg["From"] = from_address
    msg["To"] = ", ".join(to_addresses)
    msg["Subject"] = subject
    msg.set_content(
        "This email contains an HTML daily analytics report. "
        "If you are seeing only plain text, please enable HTML view in your email client."
    )
    msg.add_alternative(html_body, subtype="html")

    port = int(os.environ.get("SMTP_PORT", "25"))
    with smtplib.SMTP(smtp_host, port) as server:
        # Upsun's SMTP proxy does not require auth from the app container.
        server.send_message(msg)


def main() -> None:
    """
    Entry point to generate and send a daily analytics email.

    Configuration is read from environment variables instead of CLI flags:

    - DAILY_ANALYTICS_TO: Comma-separated list of recipient email addresses (required).
    - DAILY_ANALYTICS_DATE: Optional YYYY-MM-DD report date in ET.
      If omitted, uses *yesterday's* ET calendar day.
    - DAILY_ANALYTICS_FROM: Optional from-address override. If unset,
      falls back to DAILY_REPORT_FROM_EMAIL or 'chatbot@colby.edu'.
    - DAILY_ANALYTICS_DRY_RUN: If set to a truthy value (1, true, yes, on),
      compute metrics and write the HTML report to disk without sending email.
    """
    # --- Read configuration from environment ---
    to_env = os.environ.get("DAILY_ANALYTICS_TO", "")
    to_addresses = [addr.strip() for addr in to_env.split(",") if addr.strip()]
    if not to_addresses:
        raise RuntimeError(
            "No recipients configured. Set DAILY_ANALYTICS_TO to a comma-separated "
            "list of email addresses."
        )

    date_str = os.environ.get("DAILY_ANALYTICS_DATE")
    if date_str:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        # When running each morning (e.g. 8–9am ET), we want a report for the
        # *previous* calendar day in ET rather than "so far today".
        est_tz = ZoneInfo("America/New_York")
        now_et = datetime.now(est_tz)
        target_date = now_et.date() - timedelta(days=1)

    from_address = os.environ.get("DAILY_ANALYTICS_FROM") or None
    dry_run_raw = os.environ.get("DAILY_ANALYTICS_DRY_RUN", "")
    dry_run = dry_run_raw.strip().lower() in {"1", "true", "yes", "on"}

    metrics = fetch_daily_metrics(target_date)

    if dry_run:
        # Print a concise summary to stdout and write the full HTML to disk.
        print(f"Daily metrics for {target_date.isoformat()} (ET day)")
        print(
            f"  Total={metrics.total_queries}, "
            f"answered={metrics.answered}, "
            f"blocked={metrics.blocked}, "
            f"error={metrics.error}"
        )
        print(
            f"  blocked_by_agent_1={metrics.blocked_by_agent_1}, "
            f"blocked_by_agent_2={metrics.blocked_by_agent_2}, "
            f"blocked_by_both={metrics.blocked_by_both}"
        )
        print(
            f"  passed_guardrails={metrics.passed_guardrails}, "
            f"no_answer_after_pass={metrics.no_answer_after_pass}"
        )

        if metrics.top_answered_queries:
            print("  Top answered queries:")
            for ex in metrics.top_answered_queries:
                preview = (ex.user_message or "").strip()
                if len(preview) > 80:
                    preview = preview[:77] + "..."
                suffix = f" ({ex.count}×)" if ex.count > 1 else ""
                print(f"    - {preview}{suffix}")
        else:
            print("  No answered queries recorded for this day.")

        if metrics.top_blocked_queries:
            print("  Top rejected queries:")
            for ex in metrics.top_blocked_queries:
                preview = (ex.user_message or "").strip()
                if len(preview) > 80:
                    preview = preview[:77] + "..."
                suffix = f" ({ex.count}×)" if ex.count > 1 else ""
                print(f"    - {preview}{suffix}")
        else:
            print("  No rejected queries recorded for this day.")

        html_report = render_daily_email_html(metrics)
        out_path = f"daily_analytics_{target_date.isoformat()}.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        print(f"\nFull HTML report written to {out_path}")
        return

    send_daily_email(
        metrics=metrics,
        to_addresses=to_addresses,
        from_address=from_address,
    )


if __name__ == "__main__":
    main()


