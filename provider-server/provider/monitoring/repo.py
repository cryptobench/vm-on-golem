import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional

from .domain import AlertRule, MetricSample, MetricScope, MetricSource, WebhookConfig


def _dt(value: datetime | str | None = None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class MonitoringRepository:
    """SQLite repository for provider-local monitoring state."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS metric_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    source TEXT NOT NULL,
                    vm_id TEXT,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metric_samples_lookup
                    ON metric_samples(scope, source, vm_id, metric, ts);

                CREATE TABLE IF NOT EXISTS guest_tokens (
                    vm_id TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    source TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    enabled INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_id INTEGER NOT NULL,
                    vm_id TEXT,
                    status TEXT NOT NULL,
                    fired_at TEXT NOT NULL,
                    resolved_at TEXT,
                    last_value REAL,
                    UNIQUE(rule_id, vm_id, status)
                );

                CREATE TABLE IF NOT EXISTS webhooks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    last_status TEXT,
                    last_error TEXT,
                    last_delivered_at TEXT
                );
                """
            )
            self._ensure_default_rules(conn)

    def add_samples(self, samples: Iterable[MetricSample]) -> None:
        rows = [
            (
                sample.timestamp.isoformat(),
                sample.scope.value,
                sample.source.value,
                sample.vm_id,
                sample.metric,
                sample.value,
                sample.unit,
            )
            for sample in samples
        ]
        if not rows:
            return
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO metric_samples
                (ts, scope, source, vm_id, metric, value, unit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def latest_samples(self) -> list[MetricSample]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ms.ts, ms.scope, ms.source, ms.vm_id, ms.metric, ms.value, ms.unit
                FROM metric_samples ms
                JOIN (
                    SELECT scope, source, COALESCE(vm_id, '') AS vm_key, metric, MAX(ts) AS ts
                    FROM metric_samples
                    GROUP BY scope, source, vm_key, metric
                ) latest ON latest.scope = ms.scope
                    AND latest.source = ms.source
                    AND latest.vm_key = COALESCE(ms.vm_id, '')
                    AND latest.metric = ms.metric
                    AND latest.ts = ms.ts
                ORDER BY ms.ts DESC
                """
            ).fetchall()
        return [self._sample_from_row(row) for row in rows]

    def history(
        self,
        scope: MetricScope,
        since: datetime,
        vm_id: Optional[str] = None,
        source: Optional[MetricSource] = None,
    ) -> list[MetricSample]:
        query = """
            SELECT ts, scope, source, vm_id, metric, value, unit
            FROM metric_samples
            WHERE scope = ? AND ts >= ?
        """
        params: list[Any] = [scope.value, since.isoformat()]
        if vm_id is not None:
            query += " AND vm_id = ?"
            params.append(vm_id)
        if source is not None:
            query += " AND source = ?"
            params.append(source.value)
        query += " ORDER BY ts ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._sample_from_row(row) for row in rows]

    def prune(self, retention_days: int) -> None:
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM metric_samples WHERE ts < ?", (cutoff.isoformat(),)
            )

    def issue_guest_token(self, vm_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO guest_tokens (vm_id, token, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(vm_id) DO UPDATE SET token=excluded.token, created_at=excluded.created_at
                """,
                (vm_id, token, datetime.utcnow().isoformat()),
            )
        return token

    def validate_guest_token(self, vm_id: str, token: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT token FROM guest_tokens WHERE vm_id = ?", (vm_id,)
            ).fetchone()
        return bool(row and secrets.compare_digest(row["token"], token))

    def delete_guest_token(self, vm_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM guest_tokens WHERE vm_id = ?", (vm_id,))

    def list_alert_rules(self) -> list[AlertRule]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM alert_rules ORDER BY id").fetchall()
        return [self._rule_from_row(row) for row in rows]

    def create_alert_rule(self, rule: AlertRule) -> AlertRule:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO alert_rules
                (name, metric, scope, source, operator, threshold, duration_seconds, severity, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.name,
                    rule.metric,
                    rule.scope.value,
                    rule.source.value,
                    rule.operator,
                    rule.threshold,
                    rule.duration_seconds,
                    rule.severity,
                    int(rule.enabled),
                ),
            )
            rule.id = int(cur.lastrowid)
        return rule

    def active_alerts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, r.name, r.metric, r.severity, r.scope, r.source
                FROM alerts a
                JOIN alert_rules r ON r.id = a.rule_id
                WHERE a.status = 'active'
                ORDER BY a.fired_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_active_alert(
        self, rule: AlertRule, vm_id: Optional[str], value: float
    ) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM alerts
                WHERE rule_id = ? AND COALESCE(vm_id, '') = COALESCE(?, '') AND status = 'active'
                """,
                (rule.id, vm_id),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE alerts SET last_value = ? WHERE id = ?",
                    (value, row["id"]),
                )
                return False
            conn.execute(
                """
                INSERT INTO alerts (rule_id, vm_id, status, fired_at, last_value)
                VALUES (?, ?, 'active', ?, ?)
                """,
                (rule.id, vm_id, datetime.utcnow().isoformat(), value),
            )
            return True

    def resolve_alert(self, rule: AlertRule, vm_id: Optional[str]) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM alerts
                WHERE rule_id = ? AND COALESCE(vm_id, '') = COALESCE(?, '') AND status = 'active'
                """,
                (rule.id, vm_id),
            ).fetchone()
            if not row:
                return False
            conn.execute(
                """
                UPDATE alerts SET status = 'resolved', resolved_at = ?
                WHERE id = ?
                """,
                (datetime.utcnow().isoformat(), row["id"]),
            )
            return True

    def list_webhooks(self) -> list[WebhookConfig]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM webhooks ORDER BY id").fetchall()
        return [self._webhook_from_row(row) for row in rows]

    def create_webhook(self, webhook: WebhookConfig) -> WebhookConfig:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO webhooks (name, url, enabled)
                VALUES (?, ?, ?)
                """,
                (webhook.name, webhook.url, int(webhook.enabled)),
            )
            webhook.id = int(cur.lastrowid)
        return webhook

    def update_webhook_result(
        self, webhook_id: int, status: str, error: Optional[str] = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE webhooks
                SET last_status = ?, last_error = ?, last_delivered_at = ?
                WHERE id = ?
                """,
                (status, error, datetime.utcnow().isoformat(), webhook_id),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _sample_from_row(row: sqlite3.Row) -> MetricSample:
        return MetricSample(
            timestamp=_dt(row["ts"]),
            scope=MetricScope(row["scope"]),
            source=MetricSource(row["source"]),
            vm_id=row["vm_id"],
            metric=row["metric"],
            value=float(row["value"]),
            unit=row["unit"],
        )

    @staticmethod
    def _rule_from_row(row: sqlite3.Row) -> AlertRule:
        return AlertRule(
            id=row["id"],
            name=row["name"],
            metric=row["metric"],
            scope=MetricScope(row["scope"]),
            source=MetricSource(row["source"]),
            operator=row["operator"],
            threshold=float(row["threshold"]),
            duration_seconds=int(row["duration_seconds"]),
            severity=row["severity"],
            enabled=bool(row["enabled"]),
        )

    @staticmethod
    def _webhook_from_row(row: sqlite3.Row) -> WebhookConfig:
        return WebhookConfig(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            enabled=bool(row["enabled"]),
            last_status=row["last_status"],
            last_error=row["last_error"],
            last_delivered_at=_dt(row["last_delivered_at"])
            if row["last_delivered_at"]
            else None,
        )

    @staticmethod
    def _ensure_default_rules(conn: sqlite3.Connection) -> None:
        count = conn.execute("SELECT COUNT(*) AS n FROM alert_rules").fetchone()["n"]
        if count:
            return
        defaults = [
            AlertRule(
                name="Host memory high",
                metric="memory_percent",
                scope=MetricScope.HOST,
                source=MetricSource.INFRASTRUCTURE,
                threshold=85,
                duration_seconds=300,
                severity="warning",
            ),
            AlertRule(
                name="Host disk high",
                metric="disk_percent",
                scope=MetricScope.HOST,
                source=MetricSource.INFRASTRUCTURE,
                threshold=90,
                duration_seconds=300,
                severity="critical",
            ),
            AlertRule(
                name="Guest agent heartbeat stale",
                metric="guest_agent_age_seconds",
                scope=MetricScope.VM,
                source=MetricSource.INFRASTRUCTURE,
                threshold=180,
                duration_seconds=180,
                severity="warning",
            ),
            AlertRule(
                name="Guest memory high",
                metric="memory_percent",
                scope=MetricScope.VM,
                source=MetricSource.GUEST_AGENT,
                threshold=90,
                duration_seconds=300,
                severity="warning",
            ),
            AlertRule(
                name="Guest disk high",
                metric="disk_percent",
                scope=MetricScope.VM,
                source=MetricSource.GUEST_AGENT,
                threshold=90,
                duration_seconds=300,
                severity="critical",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO alert_rules
            (name, metric, scope, source, operator, threshold, duration_seconds, severity, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    rule.name,
                    rule.metric,
                    rule.scope.value,
                    rule.source.value,
                    rule.operator,
                    rule.threshold,
                    rule.duration_seconds,
                    rule.severity,
                    int(rule.enabled),
                )
                for rule in defaults
            ],
        )
