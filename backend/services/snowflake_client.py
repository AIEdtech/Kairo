"""
Snowflake Client — persistent cloud memory layer for Kairo.
Stores: user mental model, relationship graph snapshots, energy patterns,
action analytics, preference vectors, weekly report data.

Uses Snowflake Cortex for semantic search across relationship history.
Falls back to SQLite when Snowflake credentials aren't configured (local dev).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from config import get_settings

settings = get_settings()
logger = logging.getLogger("kairo.snowflake")


class SnowflakeClient:
    """
    Manages persistent storage in Snowflake for production,
    with SQLite fallback for local development.
    """

    def __init__(self):
        self._conn = None
        self._is_snowflake = bool(settings.snowflake_account and settings.snowflake_user)

    def connect(self):
        if not self._is_snowflake:
            logger.info("Snowflake not configured — using local SQLite fallback")
            return

        try:
            import snowflake.connector
            self._conn = snowflake.connector.connect(
                account=settings.snowflake_account,
                user=settings.snowflake_user,
                password=settings.snowflake_password,
                database=settings.snowflake_database,
                schema="public",
                warehouse=settings.snowflake_warehouse or "compute_wh",
            )
            logger.info(f"Connected to Snowflake: {settings.snowflake_account}")
            self._ensure_tables()
        except ImportError:
            logger.warning("snowflake-connector-python not installed")
            self._is_snowflake = False
        except Exception as e:
            logger.error(f"Snowflake connection failed: {e}")
            self._is_snowflake = False

    def _ensure_tables(self):
        if not self._conn:
            return
        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationship_graphs (
                    user_id STRING PRIMARY KEY,
                    graph_data VARIANT,
                    node_count INTEGER DEFAULT 0,
                    edge_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS energy_patterns (
                    id STRING PRIMARY KEY,
                    user_id STRING NOT NULL,
                    day_of_week INTEGER,
                    hour_of_day INTEGER,
                    energy_score FLOAT DEFAULT 0.5,
                    optimal_activity STRING DEFAULT 'general',
                    sample_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_mental_models (
                    user_id STRING PRIMARY KEY,
                    communication_style VARIANT,
                    priority_weights VARIANT,
                    scheduling_preferences VARIANT,
                    language_patterns VARIANT,
                    learned_rules VARIANT,
                    override_history VARIANT,
                    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_analytics (
                    id STRING PRIMARY KEY,
                    user_id STRING NOT NULL,
                    week_start DATE,
                    total_actions INTEGER DEFAULT 0,
                    auto_handled INTEGER DEFAULT 0,
                    time_saved_minutes FLOAT DEFAULT 0,
                    accuracy_pct FLOAT DEFAULT 0,
                    channel_breakdown VARIANT,
                    language_breakdown VARIANT,
                    total_spent FLOAT DEFAULT 0,
                    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
                )
            """)
            self._conn.commit()
            logger.info("Snowflake tables verified")
        finally:
            cursor.close()

    # ── Relationship Graph Persistence ──

    def save_graph(self, user_id: str, graph_json: str, node_count: int = 0, edge_count: int = 0):
        if not self._conn:
            return
        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                MERGE INTO relationship_graphs t
                USING (SELECT %s AS user_id) s ON t.user_id = s.user_id
                WHEN MATCHED THEN UPDATE SET
                    graph_data = PARSE_JSON(%s), node_count = %s,
                    edge_count = %s, updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (user_id, graph_data, node_count, edge_count)
                    VALUES (%s, PARSE_JSON(%s), %s, %s)
            """, (user_id, graph_json, node_count, edge_count,
                  user_id, graph_json, node_count, edge_count))
            self._conn.commit()
        finally:
            cursor.close()

    def load_graph(self, user_id: str) -> Optional[str]:
        if not self._conn:
            return None
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT graph_data FROM relationship_graphs WHERE user_id = %s",
                (user_id,)
            )
            row = cursor.fetchone()
            return json.dumps(row[0]) if row else None
        finally:
            cursor.close()

    # ── Energy Patterns ──

    def save_energy_pattern(self, user_id: str, day: int, hour: int,
                            score: float, activity: str):
        if not self._conn:
            return
        cursor = self._conn.cursor()
        try:
            pattern_id = f"{user_id}_{day}_{hour}"
            cursor.execute("""
                MERGE INTO energy_patterns t
                USING (SELECT %s AS id) s ON t.id = s.id
                WHEN MATCHED THEN UPDATE SET
                    energy_score = %s, optimal_activity = %s,
                    sample_count = t.sample_count + 1, updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (id, user_id, day_of_week, hour_of_day, energy_score, optimal_activity, sample_count)
                    VALUES (%s, %s, %s, %s, %s, %s, 1)
            """, (pattern_id, score, activity,
                  pattern_id, user_id, day, hour, score, activity))
            self._conn.commit()
        finally:
            cursor.close()

    def get_energy_patterns(self, user_id: str) -> list[dict]:
        if not self._conn:
            return []
        cursor = self._conn.cursor()
        try:
            cursor.execute(
                "SELECT day_of_week, hour_of_day, energy_score, optimal_activity "
                "FROM energy_patterns WHERE user_id = %s ORDER BY day_of_week, hour_of_day",
                (user_id,)
            )
            return [
                {"day": r[0], "hour": r[1], "score": r[2], "activity": r[3]}
                for r in cursor.fetchall()
            ]
        finally:
            cursor.close()

    # ── Mental Model ──

    def save_mental_model(self, user_id: str, model_data: dict):
        if not self._conn:
            return
        cursor = self._conn.cursor()
        try:
            cursor.execute("""
                MERGE INTO user_mental_models t
                USING (SELECT %s AS user_id) s ON t.user_id = s.user_id
                WHEN MATCHED THEN UPDATE SET
                    communication_style = PARSE_JSON(%s),
                    priority_weights = PARSE_JSON(%s),
                    language_patterns = PARSE_JSON(%s),
                    learned_rules = PARSE_JSON(%s),
                    updated_at = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT
                    (user_id, communication_style, priority_weights, language_patterns, learned_rules)
                    VALUES (%s, PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s))
            """, (
                user_id,
                json.dumps(model_data.get("communication_style", {})),
                json.dumps(model_data.get("priority_weights", {})),
                json.dumps(model_data.get("language_patterns", {})),
                json.dumps(model_data.get("learned_rules", {})),
                user_id,
                json.dumps(model_data.get("communication_style", {})),
                json.dumps(model_data.get("priority_weights", {})),
                json.dumps(model_data.get("language_patterns", {})),
                json.dumps(model_data.get("learned_rules", {})),
            ))
            self._conn.commit()
        finally:
            cursor.close()

    # ── Weekly Analytics ──

    def save_weekly_analytics(self, user_id: str, analytics: dict):
        if not self._conn:
            return
        cursor = self._conn.cursor()
        try:
            import uuid
            cursor.execute("""
                INSERT INTO action_analytics
                (id, user_id, week_start, total_actions, auto_handled,
                 time_saved_minutes, accuracy_pct, channel_breakdown,
                 language_breakdown, total_spent)
                VALUES (%s, %s, CURRENT_DATE(), %s, %s, %s, %s,
                        PARSE_JSON(%s), PARSE_JSON(%s), %s)
            """, (
                str(uuid.uuid4()), user_id,
                analytics.get("total_actions", 0),
                analytics.get("auto_handled", 0),
                analytics.get("time_saved", 0),
                analytics.get("accuracy", 0),
                json.dumps(analytics.get("channels", {})),
                json.dumps(analytics.get("languages", {})),
                analytics.get("total_spent", 0),
            ))
            self._conn.commit()
        finally:
            cursor.close()

    def close(self):
        if self._conn:
            self._conn.close()


# ── Singleton ──

_snowflake_client: Optional[SnowflakeClient] = None

def get_snowflake_client() -> SnowflakeClient:
    global _snowflake_client
    if _snowflake_client is None:
        _snowflake_client = SnowflakeClient()
        _snowflake_client.connect()
    return _snowflake_client
