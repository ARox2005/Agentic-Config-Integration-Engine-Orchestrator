import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .vector_store import upsert_adapter_profile

# Path to the registry file
REGISTRY_PATH = Path(__file__).parent.parent / "data" / "integration_registry.json"

# Fields that every adapter entry MUST have
REQUIRED_FIELDS = {
    "name",
    "version",
    "credential_reference",
    "target_endpoint",
}


class RegistryResult:
    """Encapsulates the result of a registry operation."""

    def __init__(self, success: bool, action: str, message: str, entry: Optional[dict] = None):
        self.success = success
        self.action = action  # "created" | "updated" | "skipped" | "error"
        self.message = message
        self.entry = entry

    def to_dict(self):
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "entry": self.entry,
        }


def _ensure_registry_exists() -> dict:
    """
    Ensures the registry file exists and contains valid JSON.
    Handles: missing file, empty file, corrupted JSON, missing 'adapters' key.
    Returns the parsed registry dict.
    """
    data_dir = REGISTRY_PATH.parent
    data_dir.mkdir(parents=True, exist_ok=True)

    # Scenario 1: File does not exist
    if not REGISTRY_PATH.exists():
        _write_registry({"adapters": []})
        print(f"[REGISTRY] Created new registry at {REGISTRY_PATH}")
        return {"adapters": []}

    # Scenario 2: File exists but is empty
    if REGISTRY_PATH.stat().st_size == 0:
        _write_registry({"adapters": []})
        print("[REGISTRY] Registry file was empty — initialized.")
        return {"adapters": []}

    # Scenario 3: File exists, try to parse
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Corrupted file — back it up and start fresh
        backup_path = REGISTRY_PATH.with_suffix(".json.bak")
        shutil.copy2(REGISTRY_PATH, backup_path)
        print(f"[REGISTRY] Corrupted registry backed up to {backup_path.name}")
        _write_registry({"adapters": []})
        return {"adapters": []}

    # Scenario 4: Valid JSON but missing 'adapters' key
    if not isinstance(data, dict):
        _write_registry({"adapters": []})
        return {"adapters": []}

    if "adapters" not in data:
        data["adapters"] = []
        _write_registry(data)
        print("[REGISTRY] Added missing 'adapters' key.")

    if not isinstance(data["adapters"], list):
        data["adapters"] = []
        _write_registry(data)

    return data


def _write_registry(data: dict) -> None:
    """Write the registry dict to disk with pretty formatting."""
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _validate_entry(entry: dict) -> Optional[str]:
    """
    Validates that a new adapter entry has all required fields.
    Returns an error message string if invalid, None if valid.
    """
    if not isinstance(entry, dict):
        return "Adapter entry must be a dictionary."

    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        return f"Missing required fields: {', '.join(sorted(missing))}"

    # Check that required fields are non-empty strings
    for field in REQUIRED_FIELDS:
        value = entry[field]
        if not isinstance(value, str) or not value.strip():
            return f"Field '{field}' must be a non-empty string. Got: {repr(value)}"

    # Validate credential_reference format
    cred_ref = entry.get("credential_reference", "")
    if not cred_ref.startswith("ENV."):
        return (
            f"credential_reference must start with 'ENV.' — "
            f"got '{cred_ref}'. Example: 'ENV.MY_API_KEY'"
        )

    return None


def _entries_are_identical(existing: dict, new: dict) -> bool:
    """
    Compare two adapter entries, ignoring metadata fields
    like 'created_at' and 'updated_at'.
    """
    ignore_keys = {"created_at", "updated_at"}
    filtered_existing = {k: v for k, v in existing.items() if k not in ignore_keys}
    filtered_new = {k: v for k, v in new.items() if k not in ignore_keys}
    return filtered_existing == filtered_new


def _find_existing_index(adapters: list, name: str, version: str) -> int:
    """
    Find the index of an adapter with matching name + version.
    Returns -1 if not found.
    """
    for i, adapter in enumerate(adapters):
        if adapter.get("name") == name and adapter.get("version") == version:
            return i
    return -1


def add_adapter(entry: dict) -> RegistryResult:
    """
    Add or update an adapter entry in the registry.

    Scenarios handled:
    - New adapter → append
    - Same name+version, identical data → skip
    - Same name+version, different data → update in-place
    - Invalid entry → reject with error
    """
    # Scenario 8: Validate the entry
    validation_error = _validate_entry(entry)
    if validation_error:
        return RegistryResult(
            success=False,
            action="error",
            message=f"Validation failed: {validation_error}",
        )

    # Ensure registry file is in a good state
    registry = _ensure_registry_exists()
    adapters = registry["adapters"]

    name = entry["name"]
    version = entry["version"]

    existing_index = _find_existing_index(adapters, name, version)

    if existing_index == -1:
        # Scenario 5: New adapter — append
        entry["created_at"] = datetime.now(timezone.utc).isoformat()
        adapters.append(entry)
        _write_registry(registry)

        # Convert this new adapter to a vector and save it in ChromaDB
        upsert_adapter_profile(entry)

        return RegistryResult(
            success=True,
            action="created",
            message=f"New adapter '{name}' (v{version}) added to registry.",
            entry=entry,
        )

    existing = adapters[existing_index]

    if _entries_are_identical(existing, entry):
        # Scenario 6: Already exists, data identical — skip
        return RegistryResult(
            success=True,
            action="skipped",
            message=f"Adapter '{name}' (v{version}) already exists with identical data. No changes.",
            entry=existing,
        )

    # Scenario 7: Exists but data changed — update in-place
    entry["created_at"] = existing.get("created_at", datetime.now(timezone.utc).isoformat())
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    adapters[existing_index] = entry
    _write_registry(registry)

    # Re-embed the updated adapter to keep ChromaDB in sync
    upsert_adapter_profile(entry)

    return RegistryResult(
        success=True,
        action="updated",
        message=f"Adapter '{name}' (v{version}) updated with new data.",
        entry=entry,
    )


def get_all_adapters() -> list:
    """Return all adapters currently in the registry."""
    registry = _ensure_registry_exists()
    return registry["adapters"]


def get_adapter(name: str, version: Optional[str] = None) -> Optional[dict]:
    """
    Look up a specific adapter by name (and optionally version).
    If version is None, returns the latest adapter with that name.
    """
    registry = _ensure_registry_exists()
    matches = [a for a in registry["adapters"] if a.get("name") == name]

    if not matches:
        return None

    if version:
        for adapter in matches:
            if adapter.get("version") == version:
                return adapter
        return None

    # Return the most recently added (last in list)
    return matches[-1]


def get_adapter_versions(name: str) -> list:
    """
    Get all versions of a specific adapter.
    Returns a list of {version, created_at} dicts.
    Supports the 'multiple API versions must coexist' requirement.
    """
    registry = _ensure_registry_exists()
    versions = []
    for adapter in registry["adapters"]:
        if adapter.get("name") == name:
            versions.append({
                "version": adapter.get("version"),
                "created_at": adapter.get("created_at"),
                "target_endpoint": adapter.get("target_endpoint"),
            })
    return versions


def get_adapter_profiles_for_discovery() -> list:
    """
    Return adapter entries formatted as rich Technical Profiles
    for the adapter discovery engine.
    
    Each profile is a "resume" that the LLM uses to match
    against SOW requirements.
    """
    registry = _ensure_registry_exists()
    adapters = registry["adapters"]

    profiles = []
    for adapter in adapters:
        profile = {
            # Functional Capabilities
            "name": adapter.get("name", ""),
            "description": adapter.get("description", ""),
            "category": adapter.get("category", "General"),
            "provider": adapter.get("provider", adapter.get("name", "")),
            "supported_actions": adapter.get("supported_actions", []),

            # Technical Interface
            "technical_interface": adapter.get("technical_interface", {
                "protocol": "REST",
                "method": "POST",
                "authentication_methods": [],
                "available_versions": [
                    {"version": adapter.get("version", "1.0"), "status": "stable"}
                ],
            }),

            # Data Schema
            "data_schema": adapter.get("data_schema", {
                "mandatory_fields": adapter.get("expected_request_fields", []),
                "optional_fields": [],
                "output_structure": adapter.get("expected_response_fields", []),
            }),

            # Connection
            "target_endpoint": adapter.get("target_endpoint", ""),
            "credential_reference": adapter.get("credential_reference", ""),
            "version": adapter.get("version", ""),
        }
        profiles.append(profile)

    return profiles

