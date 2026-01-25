"""
Sonorium Plugin EventBus

Provides event-based communication between plugins and the core system.
This enables loose coupling between components and allows plugins to react
to system events without direct dependencies.

CORE CODE: This module is shared across all platforms.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Awaitable
import logging

logger = logging.getLogger("sonorium.plugins.events")


@dataclass
class Event:
    """Represents a single event in the system."""
    type: str
    data: Dict[str, Any]
    source: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
        }


class EventTypes:
    """Standard event type constants for the plugin system."""

    # Playback events
    PLAYBACK_STARTED = "playback.started"
    PLAYBACK_STOPPED = "playback.stopped"
    PLAYBACK_PAUSED = "playback.paused"
    PLAYBACK_RESUMED = "playback.resumed"
    VOLUME_CHANGED = "playback.volume_changed"

    # Theme events
    THEME_CHANGED = "theme.changed"
    THEME_CREATED = "theme.created"
    THEME_DELETED = "theme.deleted"
    THEME_UPDATED = "theme.updated"

    # Session/Channel events
    SESSION_CREATED = "session.created"
    SESSION_DELETED = "session.deleted"
    SESSION_UPDATED = "session.updated"
    CHANNEL_SPEAKERS_CHANGED = "channel.speakers_changed"

    # Plugin lifecycle events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ACTIVATED = "plugin.activated"
    PLUGIN_DEACTIVATED = "plugin.deactivated"
    PLUGIN_ERROR = "plugin.error"

    # Speaker events
    SPEAKER_DISCOVERED = "speaker.discovered"
    SPEAKER_LOST = "speaker.lost"
    SPEAKER_STATE_CHANGED = "speaker.state_changed"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "config.changed"

    # Schedule events (for future scheduler plugin)
    SCHEDULE_TRIGGERED = "schedule.triggered"
    SCHEDULE_OVERRIDDEN = "schedule.overridden"

    # Home Assistant events (for HA addon)
    HA_STATE_CHANGED = "ha.state_changed"
    HA_CONNECTED = "ha.connected"
    HA_DISCONNECTED = "ha.disconnected"


# Type alias for event handlers
EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class Subscription:
    """Represents a subscription to an event type."""
    id: str
    event_type: str
    handler: EventHandler
    source_filter: Optional[str] = None  # Only receive events from this source

    def matches(self, event: Event) -> bool:
        """Check if this subscription matches the given event."""
        if event.type != self.event_type and self.event_type != "*":
            return False
        if self.source_filter and event.source != self.source_filter:
            return False
        return True


class EventBus:
    """
    Central event bus for plugin communication.

    Provides publish/subscribe functionality for loose coupling between
    plugins and the core system. Supports async handlers and wildcard
    subscriptions.

    Usage:
        bus = EventBus()

        async def on_theme_changed(event):
            print(f"Theme changed to {event.data['theme_id']}")

        sub_id = bus.subscribe(EventTypes.THEME_CHANGED, on_theme_changed)
        await bus.emit(EventTypes.THEME_CHANGED, {"theme_id": "forest"})
        bus.unsubscribe(sub_id)
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._subscription_index: Dict[str, Subscription] = {}
        self._wildcard_subscriptions: List[Subscription] = []
        self._event_history: List[Event] = []
        self._max_history = 100
        self._lock = asyncio.Lock()

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        source_filter: Optional[str] = None,
    ) -> str:
        """
        Subscribe to an event type.

        Args:
            event_type: The event type to subscribe to (use "*" for all events)
            handler: Async callback function that receives the Event
            source_filter: Optional source filter to only receive events from
                          a specific source (e.g., a plugin ID)

        Returns:
            Subscription ID that can be used to unsubscribe
        """
        sub_id = str(uuid.uuid4())
        subscription = Subscription(
            id=sub_id,
            event_type=event_type,
            handler=handler,
            source_filter=source_filter,
        )

        if event_type == "*":
            self._wildcard_subscriptions.append(subscription)
        else:
            if event_type not in self._subscriptions:
                self._subscriptions[event_type] = []
            self._subscriptions[event_type].append(subscription)

        self._subscription_index[sub_id] = subscription
        logger.debug(f"Subscription created: {sub_id} for {event_type}")
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from an event.

        Args:
            subscription_id: The subscription ID returned from subscribe()

        Returns:
            True if the subscription was found and removed
        """
        subscription = self._subscription_index.pop(subscription_id, None)
        if subscription is None:
            return False

        if subscription.event_type == "*":
            self._wildcard_subscriptions = [
                s for s in self._wildcard_subscriptions if s.id != subscription_id
            ]
        else:
            if subscription.event_type in self._subscriptions:
                self._subscriptions[subscription.event_type] = [
                    s for s in self._subscriptions[subscription.event_type]
                    if s.id != subscription_id
                ]

        logger.debug(f"Subscription removed: {subscription_id}")
        return True

    async def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str = "core",
    ) -> None:
        """
        Emit an event to all subscribers.

        Args:
            event_type: The type of event being emitted
            data: Event data dictionary
            source: The source of the event (plugin ID or "core")
        """
        event = Event(
            type=event_type,
            data=data,
            source=source,
        )

        # Store in history
        async with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

        logger.debug(f"Event emitted: {event_type} from {source}")

        # Gather matching subscriptions
        handlers_to_call: List[Subscription] = []

        # Add type-specific subscriptions
        if event_type in self._subscriptions:
            handlers_to_call.extend(self._subscriptions[event_type])

        # Add wildcard subscriptions
        handlers_to_call.extend(self._wildcard_subscriptions)

        # Filter by source and call handlers
        for subscription in handlers_to_call:
            if subscription.matches(event):
                try:
                    await subscription.handler(event)
                except Exception as e:
                    logger.error(
                        f"Error in event handler {subscription.id} for {event_type}: {e}"
                    )

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Event]:
        """
        Get recent event history.

        Args:
            event_type: Filter by event type (None for all)
            limit: Maximum number of events to return

        Returns:
            List of recent events, newest first
        """
        events = self._event_history.copy()
        if event_type:
            events = [e for e in events if e.type == event_type]
        return list(reversed(events[-limit:]))

    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()

    def get_subscription_count(self, event_type: Optional[str] = None) -> int:
        """
        Get the number of active subscriptions.

        Args:
            event_type: Count subscriptions for a specific type (None for all)

        Returns:
            Number of active subscriptions
        """
        if event_type:
            return len(self._subscriptions.get(event_type, []))
        return len(self._subscription_index)

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all active subscriptions (for debugging)."""
        return [
            {
                "id": sub.id,
                "event_type": sub.event_type,
                "source_filter": sub.source_filter,
            }
            for sub in self._subscription_index.values()
        ]


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global EventBus (for testing)."""
    global _event_bus
    _event_bus = None
