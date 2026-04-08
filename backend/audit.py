"""
Audit Trail — Full auditability of integration changes.

Logs every significant action (generate, deploy, simulate, reject)
to a local JSON file with timestamps.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

AUDIT_LOG_PATH = Path(__file__).parent.parent / "data" / "audit_log.json"


def _ensure_audit_log() -> list:
    """Ensure the audit log file exists and return its contents."""
    data_dir = AUDIT_LOG_PATH.parent
    data_dir.mkdir(parents=True, exist_ok=True)

    if not AUDIT_LOG_PATH.exists() or AUDIT_LOG_PATH.stat().st_size == 0:
        _write_audit_log([])
        return []

    try:
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []


def _write_audit_log(events: list) -> None:
    """Write audit events to disk."""
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)


def log_event(action: str, details: Optional[dict] = None) -> dict:
    """
    Log an audit event.

    Args:
        action: The action performed (e.g., generate_started, deploy_completed)
        details: Additional context about the action

    Returns:
        The logged event dict
    """
    events = _ensure_audit_log()

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "details": details or {},
    }

    events.append(event)

    # Keep last 500 events to prevent unbounded growth
    if len(events) > 500:
        events = events[-500:]

    _write_audit_log(events)
    return event


def get_recent_events(limit: int = 50) -> list:
    """
    Get the most recent audit events.

    Args:
        limit: Maximum number of events to return (default 50)

    Returns:
        List of event dicts, most recent first
    """
    events = _ensure_audit_log()
    return list(reversed(events[-limit:]))
