from enum import Enum


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    IDLE = "idle"
    FAILED = "failed"
    CLOSED = "closed"
