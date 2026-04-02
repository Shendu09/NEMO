"""Topic name constants for the NEMO-OS IPC message bus."""

from __future__ import annotations


class Topics:
    """All topic names used in the bus system."""

    # Voice layer publishes here
    VOICE_TRANSCRIPT = "voice.transcript"
    VOICE_WAKE_WORD = "voice.wake_word"
    VOICE_ERROR = "voice.error"

    # Vision layer publishes here
    VISION_SCREENSHOT = "vision.screenshot"
    VISION_CONTEXT = "vision.context"
    VISION_ERROR = "vision.error"

    # AI Brain publishes here
    AI_DECISION = "ai.decision"
    AI_COMMAND = "ai.command"
    AI_RESPONSE = "ai.response"
    AI_ERROR = "ai.error"

    # System events
    SYSTEM_HEALTH = "system.health"
    SYSTEM_AUDIT = "system.audit"
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPING = "system.stopping"

    # Action results
    ACTION_RESULT = "action.result"
    ACTION_ERROR = "action.error"

    @classmethod
    def all(cls) -> list[str]:
        """Return all topic names as a list."""
        return [
            v for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, str)
        ]

    @classmethod
    def for_layer(cls, layer: str) -> list[str]:
        """Return all topics for a specific layer."""
        prefix = f"{layer}."
        return [t for t in cls.all() if t.startswith(prefix)]
