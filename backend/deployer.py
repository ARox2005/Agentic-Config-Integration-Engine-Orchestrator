import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .registry import add_adapter, RegistryResult

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# Path to the middleware configs directory
MIDDLEWARE_CONFIGS_DIR = Path(__file__).parent.parent.parent / "middleware" / "configs"

# ──────────────────────────────────────────────
# Deployment Result
# ──────────────────────────────────────────────

class DeploymentResult:
    """Encapsulates the result of a full split deployment."""

    def __init__(
        self,
        success: bool,
        config_status: str,
        config_message: str,
        registry_result: Optional[RegistryResult] = None,
        config_path: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ):
        self.success = success
        self.config_status = config_status      # "created" | "updated" | "error"
        self.config_message = config_message
        self.registry_result = registry_result
        self.config_path = config_path
        self.tenant_id = tenant_id

    def to_dict(self):
        return {
            "success": self.success,
            "tenant_id": self.tenant_id,
            "config_deployment": {
                "status": self.config_status,
                "message": self.config_message,
                "path": self.config_path,
            },
            "registry_update": self.registry_result.to_dict() if self.registry_result else None,
        }

# ──────────────────────────────────────────────
# Config Deployment (to Middleware)
# ──────────────────────────────────────────────

def _sanitize_service_name(name: str) -> str:
    """
    Convert a service name into a safe filename.
    Strips version suffixes so filenames match what consumers expect.
    'KYC Provider' → 'kyc_provider'
    'KYC Provider v1.0' → 'kyc_provider'
    'GST Service v2.0' → 'gst_service'
    """
    # Strip trailing version info (v1.0, v2, 1.0, etc.)
    safe = re.sub(r'\s*v?\d+[\.\\d]*\s*$', '', name, flags=re.IGNORECASE)
    safe = safe.lower().strip()
    safe = safe.replace(" ", "_")
    safe = safe.replace(".", "_")
    safe = safe.replace("-", "_")
    safe = "".join(c for c in safe if c.isalnum() or c == "_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe.strip("_")


def deploy_config(
    blueprint: dict,
    service_name: str,
    tenant_id: str = "default",
    backup_existing: bool = True,
) -> dict:
    """
    Deploy a blueprint config file to the middleware's configs directory.
    Configs are isolated by tenant: middleware/configs/{tenant_id}/{service}.json

    Args:
        blueprint: The JSON config blueprint to write.
        service_name: Name for the config file (e.g., "kyc_provider").
        tenant_id: Tenant identifier for config isolation.
        backup_existing: If True, backs up any existing config before overwriting.

    Returns:
        dict with keys: success, status, message, path
    """
    # Sanitize the filename
    safe_name = _sanitize_service_name(service_name)
    if not safe_name:
        return {
            "success": False,
            "status": "error",
            "message": f"Invalid service name: '{service_name}'. Cannot create filename.",
            "path": None,
        }

    # Tenant-isolated directory
    tenant_configs_dir = MIDDLEWARE_CONFIGS_DIR / tenant_id

    # Ensure configs directory exists
    try:
        tenant_configs_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return {
            "success": False,
            "status": "error",
            "message": f"Permission denied: cannot create directory {tenant_configs_dir}",
            "path": None,
        }

    config_path = tenant_configs_dir / f"{safe_name}.json"
    is_update = config_path.exists()

    # Backup existing config if present
    if is_update and backup_existing:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.with_suffix(f".{timestamp}.bak")
        try:
            shutil.copy2(config_path, backup_path)
            print(f"[DEPLOYER] Backed up existing config to {backup_path.name}")
        except Exception as e:
            print(f"[DEPLOYER] Warning: Could not backup existing config: {e}")

    # Write the config file
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": f"Failed to write config file: {str(e)}",
            "path": None,
        }

    action = "updated" if is_update else "created"

    return {
        "success": True,
        "status": action,
        "message": f"Config '{tenant_id}/{safe_name}.json' {action} successfully.",
        "path": str(config_path),
    }

# ──────────────────────────────────────────────
# Split Deployment (Config + Registry)
# ──────────────────────────────────────────────

def split_deploy(
    blueprint: dict,
    catalog_entry: dict,
    service_name: Optional[str] = None,
    tenant_id: str = "default",
) -> DeploymentResult:
    """
    Perform the full split deployment:
    1. Deploy the blueprint config to the middleware (tenant-isolated)
    2. Add the catalog entry to the registry

    Args:
        blueprint: The config blueprint JSON for the middleware.
        catalog_entry: The metadata entry for the adapter registry.
        service_name: Optional override for the config filename.
        tenant_id: Tenant identifier for config isolation.
    """
    # Derive service_name: prefer catalog_entry.service_name, then param, then fallback
    if not service_name:
        service_name = catalog_entry.get("service_name")
    if not service_name:
        adapter_name = catalog_entry.get("name", "")
        if not adapter_name:
            return DeploymentResult(
                success=False,
                config_status="error",
                config_message="Cannot determine service name: no service_name in catalog_entry and no 'name' field.",
                tenant_id=tenant_id,
            )
        service_name = _sanitize_service_name(adapter_name)

    # Step 1: Deploy config to middleware (tenant-isolated)
    config_result = deploy_config(blueprint, service_name, tenant_id=tenant_id)

    if not config_result["success"]:
        return DeploymentResult(
            success=False,
            config_status=config_result["status"],
            config_message=config_result["message"],
            config_path=config_result.get("path"),
            tenant_id=tenant_id,
        )

    # Step 2: Add catalog entry to registry
    registry_result = add_adapter(catalog_entry)
    if not registry_result.success:
        return DeploymentResult(
            success=False,
            config_status=config_result["status"],
            config_message=config_result["message"] + " (but registry update failed)",
            registry_result=registry_result,
            config_path=config_result.get("path"),
            tenant_id=tenant_id,
        )
        
    # Both succeeded
    return DeploymentResult(
        success=True,
        config_status=config_result["status"],
        config_message=config_result["message"],
        registry_result=registry_result,
        config_path=config_result.get("path"),
        tenant_id=tenant_id,
    )