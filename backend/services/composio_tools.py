"""
Composio integration — OAuth-managed tools for Gmail, Calendar, Slack, Teams, GitHub.
Provides CrewAI-compatible tool wrappers for all integrations.
"""

import logging
from typing import Optional
from config import get_settings

settings = get_settings()
logger = logging.getLogger("kairo.composio")


class ComposioClient:
    """
    Manages Composio OAuth connections and provides callable tools
    for CrewAI agents to interact with Gmail, Slack, Teams, etc.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or settings.composio_api_key
        self._toolset = None
        self._entity = None

    def initialize(self, entity_id: str = "default"):
        """
        Initialize Composio toolset for a specific user entity.
        Called when an agent is launched.
        """
        if not self.api_key:
            logger.warning("Composio API key not set — integrations disabled")
            return

        try:
            from composio import ComposioToolSet, App, Action

            self._toolset = ComposioToolSet(api_key=self.api_key)
            self._entity = self._toolset.get_entity(entity_id)
            logger.info(f"Composio initialized for entity: {entity_id}")
        except ImportError:
            logger.warning("composio-core not installed — pip install composio-core")
        except Exception as e:
            logger.error(f"Composio init failed: {e}")

    def get_connection_status(self) -> dict:
        """Check which integrations are connected."""
        status = {
            "gmail": False,
            "calendar": False,
            "slack": False,
            "teams": False,
            "github": False,
        }
        if not self._entity:
            return status

        try:
            connections = self._entity.get_connections()
            logger.info(f"Composio returned {len(connections)} connections")
            for conn in connections:
                # Use camelCase attributes (Composio SDK uses Pydantic models)
                app_name = getattr(conn, 'appName', '') or getattr(conn, 'appUniqueId', '') or getattr(conn, 'app_name', '')
                conn_status = getattr(conn, 'status', 'unknown')
                logger.info(f"  Connection: app={app_name}, status={conn_status}")
                
                # Only count ACTIVE connections
                if str(conn_status).upper() != 'ACTIVE':
                    continue
                
                app_lower = str(app_name).lower()
                if "gmail" in app_lower or "google_mail" in app_lower or "googlemail" in app_lower:
                    status["gmail"] = True
                elif "calendar" in app_lower or "google_calendar" in app_lower or "googlecalendar" in app_lower:
                    status["calendar"] = True
                elif "slack" in app_lower:
                    status["slack"] = True
                elif "teams" in app_lower or "microsoft_teams" in app_lower:
                    status["teams"] = True
                elif "github" in app_lower:
                    status["github"] = True
        except Exception as e:
            logger.error(f"Failed to check connections: {e}")

        return status

    def get_auth_url(self, app_name: str, redirect_url: str = "") -> Optional[str]:
        """
        Get the OAuth URL for connecting a new integration.
        Frontend redirects user here, Composio handles OAuth flow.
        """
        if not self._entity:
            return None

        try:
            # Use string app names — App enum doesn't work in this SDK version
            app_map = {
                "gmail": "GMAIL",
                "calendar": "GOOGLECALENDAR",
                "slack": "SLACK",
                "teams": "MICROSOFT_TEAMS",
                "github": "GITHUB",
            }
            app = app_map.get(app_name.lower())
            if not app:
                logger.error(f"Unknown app name: {app_name}")
                return None

            connection = self._entity.initiate_connection(app_name=app, redirect_url=redirect_url)
            logger.info(f"Initiated connection for {app_name}: status={connection.connectionStatus}, url={connection.redirectUrl}")
            return connection.redirectUrl if hasattr(connection, 'redirectUrl') else None
        except Exception as e:
            logger.error(f"Failed to get auth URL for {app_name}: {e}")
            return None

    def get_crewai_tools(self, apps: list[str] = None) -> list:
        """
        Get CrewAI-compatible tools for specified apps.
        Used by the agent runtime to equip CrewAI agents with real tools.
        """
        if not self._toolset:
            logger.warning("Composio not initialized — returning empty tools")
            return []

        try:
            if apps is None:
                apps = ["gmail", "calendar", "slack", "teams"]

            app_map = {
                "gmail": "GMAIL",
                "calendar": "GOOGLECALENDAR",
                "slack": "SLACK",
                "teams": "MICROSOFT_TEAMS",
                "github": "GITHUB",
            }

            selected_apps = [app_map[a] for a in apps if a in app_map]
            
            # composio-core doesn't have get_tools — return action schemas
            # which work directly with execute_action in agent_runtime
            schemas = self._toolset.get_action_schemas(apps=selected_apps)
            logger.info(f"Loaded {len(schemas)} Composio action schemas for: {apps}")
            return schemas

        except Exception as e:
            logger.error(f"Failed to get CrewAI tools: {e}")
            return []

    # ── Direct action methods (used by webhook handlers) ──

    async def fetch_recent_emails(self, max_results: int = 10, max_age_hours: int = 1) -> list[dict]:
        """Fetch recent unread emails from Gmail inbox, filtered to last max_age_hours."""
        if not self._toolset:
            return []
        try:
            from composio import Action
            from datetime import datetime, timezone, timedelta
            
            result = self._toolset.execute_action(
                Action.GMAIL_FETCH_EMAILS,
                params={"max_results": max_results, "label": "INBOX", "query": "is:unread category:primary"},
                entity_id=self._entity.id if self._entity else "default",
            )
            
            emails = []
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            
            def parse_email(msg: dict) -> dict:
                return {
                    "id": msg.get("messageId", msg.get("id", "")),
                    "from": msg.get("sender", msg.get("from", "")),
                    "to": msg.get("to", msg.get("recipient", "")),
                    "subject": msg.get("subject", ""),
                    "body": msg.get("messageText", msg.get("body", msg.get("snippet", msg.get("preview", "")))),
                    "date": msg.get("messageTimestamp", msg.get("date", msg.get("receivedAt", ""))),
                    "thread_id": msg.get("threadId", msg.get("thread_id", "")),
                    "labels": msg.get("labelIds", msg.get("labels", [])),
                }
            
            def is_recent(email: dict) -> bool:
                """Filter out old emails by timestamp."""
                date_str = email.get("date", "")
                if not date_str:
                    return True  # Keep if we can't determine age
                try:
                    # Try parsing ISO format
                    ts = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
                    return ts >= cutoff
                except (ValueError, TypeError):
                    pass
                try:
                    # Try parsing epoch timestamp (milliseconds)
                    ts = datetime.fromtimestamp(int(date_str) / 1000, tz=timezone.utc)
                    return ts >= cutoff
                except (ValueError, TypeError, OSError):
                    pass
                return True  # Keep if unparseable
            
            def is_not_promo(email: dict) -> bool:
                """Filter out promotional/marketing emails."""
                labels = email.get("labels", [])
                if isinstance(labels, list):
                    promo_labels = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_UPDATES", "CATEGORY_FORUMS", "SPAM"}
                    if any(lbl in promo_labels for lbl in labels):
                        return False
                return True
            
            # Handle various response formats
            if isinstance(result, dict):
                if result.get("successful") and isinstance(result.get("data"), dict):
                    data = result["data"]
                    messages = data.get("messages", data.get("emails", []))
                    if isinstance(messages, list):
                        for msg in messages:
                            emails.append(parse_email(msg))
                elif isinstance(result.get("data"), list):
                    for msg in result["data"]:
                        emails.append(parse_email(msg))
            
            # Filter: only recent, non-promo emails
            filtered = [e for e in emails if is_recent(e) and is_not_promo(e)]
            logger.info(f"Fetched {len(emails)} emails, {len(filtered)} after filtering (recent + non-promo)")
            return filtered
        except Exception as e:
            logger.error(f"Fetch emails failed: {e}")
            return []

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email via Gmail through Composio."""
        if not self._toolset:
            return False
        try:
            from composio import Action
            result = self._toolset.execute_action(
                Action.GMAIL_SEND_EMAIL,
                params={"to": to, "subject": subject, "body": body},
                entity_id=self._entity.id if self._entity else "default",
            )
            return result.get("successful", False)
        except Exception as e:
            logger.error(f"Send email failed: {e}")
            return False

    async def mark_email_read(self, message_id: str) -> bool:
        """Mark an email as read via Gmail through Composio to prevent re-fetching."""
        if not self._toolset or not message_id:
            return False
        try:
            from composio import Action
            result = self._toolset.execute_action(
                Action.GMAIL_MODIFY_MESSAGE,
                params={"message_id": message_id, "removeLabelIds": ["UNREAD"]},
                entity_id=self._entity.id if self._entity else "default",
            )
            success = result.get("successful", False) if isinstance(result, dict) else False
            if success:
                logger.info(f"Marked email {message_id[:20]} as read")
            return success
        except Exception as e:
            logger.debug(f"Mark email read failed (non-critical): {e}")
            return False

    async def send_slack_message(self, channel: str, text: str) -> bool:
        """Send Slack message through Composio."""
        if not self._toolset:
            return False
        try:
            from composio import Action
            result = self._toolset.execute_action(
                Action.SLACK_SEND_MESSAGE,
                params={"channel": channel, "text": text},
                entity_id=self._entity.id if self._entity else "default",
            )
            return result.get("successful", False)
        except Exception as e:
            logger.error(f"Send Slack message failed: {e}")
            return False

    async def send_teams_message(self, chat_id: str, content: str) -> bool:
        """Send Teams message through Composio."""
        if not self._toolset:
            return False
        try:
            from composio import Action
            result = self._toolset.execute_action(
                Action.MICROSOFT_TEAMS_SEND_MESSAGE,
                params={"chatId": chat_id, "content": content},
                entity_id=self._entity.id if self._entity else "default",
            )
            return result.get("successful", False)
        except Exception as e:
            logger.error(f"Send Teams message failed: {e}")
            return False

    async def get_calendar_events(self, days_ahead: int = 7) -> list[dict]:
        """
        Fetch calendar events for the next N days.
        Returns: [{"title": "...", "start": "2026-02-27T14:00:00", "end": "2026-02-27T15:00:00"}, ...]
        """
        if not self._toolset:
            return []
        try:
            from datetime import datetime, timedelta, timezone
            from composio import Action
            
            now = datetime.now(timezone.utc)
            start_time = now.isoformat()
            end_time = (now + timedelta(days=days_ahead)).isoformat()
            
            params = {
                "timeMin": start_time,
                "timeMax": end_time,
            }
            
            result = self._toolset.execute_action(
                Action.GOOGLECALENDAR_EVENTS_LIST,
                params=params,
                entity_id=self._entity.id if self._entity else "default",
            )
            
            events = []
            if isinstance(result, dict):
                data = result.get("data", result)
                items = data.get("items", data.get("events", []))
                if isinstance(items, list):
                    for e in items:
                        start_dt = e.get("start", {})
                        end_dt = e.get("end", {})
                        if isinstance(start_dt, dict):
                            start_val = start_dt.get("dateTime") or start_dt.get("date", "")
                        else:
                            start_val = str(start_dt)
                        if isinstance(end_dt, dict):
                            end_val = end_dt.get("dateTime") or end_dt.get("date", "")
                        else:
                            end_val = str(end_dt)
                        events.append({
                            "title": e.get("summary", e.get("title", "Busy")),
                            "start": start_val,
                            "end": end_val,
                        })
            
            logger.info(f"Calendar has {len(events)} events in next {days_ahead} days")
            return events
        except Exception as e:
            logger.warning(f"Get calendar events failed: {e}")
            return []

    def find_available_slots(self, calendar_events: list[dict], 
                            days_ahead: int = 7, 
                            duration_minutes: int = 30,
                            skip_deep_work: bool = True,
                            deep_work_start: str = "09:00",
                            deep_work_end: str = "17:00") -> list[dict]:
        """
        Find available time slots in the next N days.
        
        Returns:
          [
              {"date": "2026-02-27", "start": "14:00", "end": "14:30", 
               "start_iso": "2026-02-27T14:00:00", "end_iso": "2026-02-27T14:30:00"},
              ...
          ]
        """
        from datetime import datetime, timedelta, timezone, time
        import json
        
        now = datetime.now(timezone.utc)
        available_slots = []
        
        for day_offset in range(days_ahead):
            check_date = now + timedelta(days=day_offset)
            date_str = check_date.strftime("%Y-%m-%d")
            
            # Skip night hours (before 8am, after 10pm)
            for hour in range(8, 22):
                for minute in [0, 30]:
                    slot_start = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    
                    # Skip deep work hours if enabled
                    if skip_deep_work:
                        deep_start_time = datetime.strptime(deep_work_start, "%H:%M").time()
                        deep_end_time = datetime.strptime(deep_work_end, "%H:%M").time()
                        slot_time = slot_start.time()
                        
                        if deep_start_time <= slot_time < deep_end_time:
                            continue
                    
                    # Check for conflicts
                    conflict = False
                    for event in calendar_events:
                        event_start_str = event.get("start", "")
                        event_end_str = event.get("end", "")
                        
                        if not event_start_str or not event_end_str:
                            continue
                        
                        try:
                            # Parse ISO format datetimes
                            event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                            event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                            
                            # Check overlap
                            if not (slot_end <= event_start or slot_start >= event_end):
                                conflict = True
                                break
                        except:
                            pass
                    
                    if not conflict:
                        available_slots.append({
                            "date": date_str,
                            "start": slot_start.strftime("%H:%M"),
                            "end": slot_end.strftime("%H:%M"),
                            "start_iso": slot_start.isoformat(),
                            "end_iso": slot_end.isoformat(),
                        })
        
        return available_slots

    async def create_calendar_event(self, title: str, start_datetime: str, 
                                     duration_minutes: int = 30,
                                     attendees: list[str] = None,
                                     timezone: str = "America/Chicago") -> bool:
        """Create calendar event through Composio.
        
        Args:
            title: Event title/summary
            start_datetime: ISO 8601 format e.g. '2026-02-28T15:00:00'
            duration_minutes: Event duration in minutes (default 30)
            attendees: List of email addresses
            timezone: IANA timezone (default America/Chicago)
        """
        if not self._toolset:
            return False
        try:
            from composio import Action
            params = {
                "start_datetime": start_datetime,
                "summary": title,
                "event_duration_hour": duration_minutes // 60,
                "event_duration_minutes": duration_minutes % 60,
                "timezone": timezone,
                "create_meeting_room": False,
                "sendUpdates": False,  # Suppress Google Calendar invitation emails — we send our own reply
            }
            if attendees:
                params["attendees"] = attendees
            result = self._toolset.execute_action(
                Action.GOOGLECALENDAR_CREATE_EVENT,
                params=params,
                entity_id=self._entity.id if self._entity else "default",
            )
            success = result.get("successful", False) if isinstance(result, dict) else False
            logger.info(f"Create calendar event: {title} at {start_datetime} -> success={success}")
            if not success:
                logger.warning(f"Create event response: {str(result)[:300]}")
            return success
        except Exception as e:
            logger.error(f"Create calendar event failed: {e}")
            return False


# ── Singleton ──

_composio_client: Optional[ComposioClient] = None


def get_composio_client() -> ComposioClient:
    global _composio_client
    if _composio_client is None:
        _composio_client = ComposioClient()
    return _composio_client
