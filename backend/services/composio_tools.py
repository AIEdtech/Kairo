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
            for conn in connections:
                app_name = conn.app_name.lower() if hasattr(conn, 'app_name') else ""
                if "gmail" in app_name or "google_mail" in app_name:
                    status["gmail"] = True
                elif "calendar" in app_name or "google_calendar" in app_name:
                    status["calendar"] = True
                elif "slack" in app_name:
                    status["slack"] = True
                elif "teams" in app_name or "microsoft_teams" in app_name:
                    status["teams"] = True
                elif "github" in app_name:
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
            from composio import App
            app_map = {
                "gmail": App.GMAIL,
                "calendar": App.GOOGLECALENDAR,
                "slack": App.SLACK,
                "teams": App.MICROSOFT_TEAMS,
                "github": App.GITHUB,
            }
            app = app_map.get(app_name.lower())
            if not app:
                return None

            connection = self._entity.initiate_connection(app, redirect_url=redirect_url)
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
            from composio import App

            if apps is None:
                apps = ["gmail", "calendar", "slack", "teams"]

            app_map = {
                "gmail": App.GMAIL,
                "calendar": App.GOOGLECALENDAR,
                "slack": App.SLACK,
                "teams": App.MICROSOFT_TEAMS,
                "github": App.GITHUB,
            }

            selected_apps = [app_map[a] for a in apps if a in app_map]
            tools = self._toolset.get_tools(apps=selected_apps)
            logger.info(f"Loaded {len(tools)} Composio tools for: {apps}")
            return tools

        except Exception as e:
            logger.error(f"Failed to get CrewAI tools: {e}")
            return []

    # ── Direct action methods (used by webhook handlers) ──

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

    async def create_calendar_event(self, title: str, start: str, end: str,
                                     attendees: list[str] = None) -> bool:
        """Create calendar event through Composio."""
        if not self._toolset:
            return False
        try:
            from composio import Action
            params = {"title": title, "start": start, "end": end}
            if attendees:
                params["attendees"] = attendees
            result = self._toolset.execute_action(
                Action.GOOGLE_CALENDAR_CREATE_EVENT,
                params=params,
                entity_id=self._entity.id if self._entity else "default",
            )
            return result.get("successful", False)
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
