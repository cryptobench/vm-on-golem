from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from provider.errors import NotFoundError
from provider.utils.time import ensure_utc, utc_now

from .domain import (
    WEBHOOK_EVENT_TYPES,
    WebhookConfig,
    WebhookDeliveryAttempt,
    WebhookTemplate,
)


def _dt(value: datetime | str | None = None) -> datetime:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        return ensure_utc(value)
    return ensure_utc(datetime.fromisoformat(value))


class WebhookRepository:
    """SQLite repository for provider webhook configuration and deliveries."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    last_status TEXT,
                    last_error TEXT,
                    last_delivered_at TEXT
                )
                """
            )
            self._ensure_columns(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_delivery_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    http_status INTEGER,
                    error TEXT,
                    attempted_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_webhook_delivery_attempts_lookup
                ON webhook_delivery_attempts(webhook_id, attempted_at DESC, id DESC)
                """
            )
            conn.execute(
                """
                UPDATE webhooks
                SET service_type = COALESCE(service_type, 'generic_json'),
                    events = COALESCE(events, ?),
                    template = COALESCE(template, ?)
                """,
                (
                    json.dumps(list(WEBHOOK_EVENT_TYPES)),
                    WebhookTemplate().model_dump_json(),
                ),
            )

    def list_webhooks(self) -> list[WebhookConfig]:
        self.init_schema()
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM webhooks ORDER BY id").fetchall()
        return [self._webhook_from_row(row) for row in rows]

    def get_webhook(self, webhook_id: int) -> WebhookConfig:
        self.init_schema()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM webhooks WHERE id = ?", (webhook_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError("webhook not found")
        return self._webhook_from_row(row)

    def create_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        self.init_schema()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO webhooks
                (name, url, enabled, service_type, events, template)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                self._webhook_values(webhook),
            )
            webhook.id = int(cur.lastrowid)
        return self.get_webhook(webhook.id)

    def update_webhook(self, webhook_id: int, webhook: WebhookConfig) -> WebhookConfig:
        self.init_schema()
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE webhooks
                SET name = ?, url = ?, enabled = ?, service_type = ?, events = ?, template = ?
                WHERE id = ?
                """,
                (*self._webhook_values(webhook), webhook_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError("webhook not found")
        return self.get_webhook(webhook_id)

    def delete_webhook(self, webhook_id: int) -> None:
        self.init_schema()
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
            if cur.rowcount == 0:
                raise NotFoundError("webhook not found")
            conn.execute(
                "DELETE FROM webhook_delivery_attempts WHERE webhook_id = ?",
                (webhook_id,),
            )

    def update_webhook_result(
        self,
        webhook_id: int,
        status: str,
        http_status: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        self.init_schema()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE webhooks
                SET last_status = ?, last_http_status = ?, last_error = ?, last_delivered_at = ?
                WHERE id = ?
                """,
                (status, http_status, error, utc_now().isoformat(), webhook_id),
            )

    def add_delivery_attempt(
        self, attempt: WebhookDeliveryAttempt
    ) -> WebhookDeliveryAttempt:
        self.init_schema()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO webhook_delivery_attempts
                (webhook_id, event_id, event_type, attempt, status, http_status, error, attempted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.webhook_id,
                    attempt.event_id,
                    attempt.event_type,
                    attempt.attempt,
                    attempt.status,
                    attempt.http_status,
                    attempt.error,
                    ensure_utc(attempt.attempted_at).isoformat(),
                ),
            )
            attempt.id = int(cur.lastrowid)
            conn.execute(
                """
                DELETE FROM webhook_delivery_attempts
                WHERE webhook_id = ?
                  AND id NOT IN (
                    SELECT id FROM webhook_delivery_attempts
                    WHERE webhook_id = ?
                    ORDER BY attempted_at DESC, id DESC
                    LIMIT 100
                  )
                """,
                (attempt.webhook_id, attempt.webhook_id),
            )
        return attempt

    def list_delivery_attempts(
        self, webhook_id: int, limit: int = 100
    ) -> list[WebhookDeliveryAttempt]:
        self.init_schema()
        self.get_webhook(webhook_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM webhook_delivery_attempts
                WHERE webhook_id = ?
                ORDER BY attempted_at DESC, id DESC
                LIMIT ?
                """,
                (webhook_id, limit),
            ).fetchall()
        return [self._attempt_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _ensure_columns(conn: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(webhooks)").fetchall()
        }
        additions = {
            "service_type": "TEXT",
            "events": "TEXT",
            "template": "TEXT",
            "last_http_status": "INTEGER",
        }
        for name, column_type in additions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE webhooks ADD COLUMN {name} {column_type}")

    @staticmethod
    def _webhook_values(webhook: WebhookConfig) -> tuple:
        return (
            webhook.name,
            webhook.url,
            int(webhook.enabled),
            webhook.service_type,
            json.dumps(webhook.events),
            webhook.template.model_dump_json(),
        )

    @staticmethod
    def _webhook_from_row(row: sqlite3.Row) -> WebhookConfig:
        return WebhookConfig(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            enabled=bool(row["enabled"]),
            service_type=row["service_type"] or "generic_json",
            events=json.loads(row["events"] or json.dumps(list(WEBHOOK_EVENT_TYPES))),
            template=WebhookTemplate.model_validate_json(row["template"])
            if row["template"]
            else WebhookTemplate(),
            last_status=row["last_status"],
            last_http_status=row["last_http_status"],
            last_error=row["last_error"],
            last_delivered_at=_dt(row["last_delivered_at"])
            if row["last_delivered_at"]
            else None,
        )

    @staticmethod
    def _attempt_from_row(row: sqlite3.Row) -> WebhookDeliveryAttempt:
        return WebhookDeliveryAttempt(
            id=row["id"],
            webhook_id=row["webhook_id"],
            event_id=row["event_id"],
            event_type=row["event_type"],
            attempt=row["attempt"],
            status=row["status"],
            http_status=row["http_status"],
            error=row["error"],
            attempted_at=_dt(row["attempted_at"]),
        )
