from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from .registry import get_all_adapters, get_adapter, get_adapter_versions, add_adapter
from .llm_engine import process_sow, check_ollama_status
from .deployer import split_deploy
from .text_extractor import extract_text_from_file, combine_texts
from .adapter_discovery import discover_adapter
from .audit import log_event, get_recent_events

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

app = FastAPI(
    title = "ZeroOne AI Orchestrator",
    description="AI-powered design-time tool that reads SOW documents and generates integration blueprints",
    version="0.1.0",
)

# Allow CORS for the orchestrator frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "orchestrator"}

@app.get("/health/ollama")
async def ollama_health():
    """Check if Ollama is running and the configured model is available."""
    status = await check_ollama_status()
    return status

# ──────────────────────────────────────────────
# Registry Endpoints (Adapter Catalog)
# ──────────────────────────────────────────────

@app.get("/api/orchestrator/registry")
def list_adapters():
    """List all adapters in the integration registry."""
    adapters = get_all_adapters()
    return {
        "total": len(adapters),
        "adapters": adapters,
    }

@app.get("/api/orchestrator/registry/{adapter_name}")
def lookup_adapter(adapter_name: str, version: Optional[str] = None):
    """Look up a specific adapter by name (and optional version query param)."""
    adapter = get_adapter(adapter_name, version)
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adapter '{adapter_name}' not found in registry." + (f" (version: {version})" if version else ""),
        )

    return adapter

@app.get("/api/orchestrator/registry/{adapter_name}/versions")
def list_adapter_versions(adapter_name: str):
    """List all versions of a specific adapter. Supports version coexistence."""
    versions = get_adapter_versions(adapter_name)
    if not versions:
        raise HTTPException(
            status_code=404,
            detail=f"No versions found for adapter '{adapter_name}'.",
        )
    return {"adapter_name": adapter_name, "versions": versions}

# ──────────────────────────────────────────────
# Audit Trail
# ──────────────────────────────────────────────

@app.get("/api/orchestrator/audit")
def get_audit_trail(limit: int = 50):
    """Return the most recent audit events."""
    events = get_recent_events(limit)
    return {"total": len(events), "events": events}

# ──────────────────────────────────────────────
# SOW Processing & Blueprint Generation
# ──────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """Request body for the /generate endpoint."""
    sow_text: str
    model: Optional[str] = None
    tenant_id: Optional[str] = "default"

class DeployRequest(BaseModel):
    """Request body for the /deploy endpoint."""
    blueprint: dict
    catalog_entry: dict
    service_name: Optional[str] = None
    tenant_id: Optional[str] = "default"

@app.post("/api/orchestrator/generate")
async def generate_blueprint(request: GenerateRequest):
    """
    Accept an SOW document, discover matching adapter, process with LLM.
    Returns: blueprint, catalog_entry, and discovery info.
    """
    if not request.sow_text.strip():
        raise HTTPException(status_code=400, detail="SOW text cannot be empty.")

    log_event("generate_started", {
        "tenant_id": request.tenant_id,
        "sow_length": len(request.sow_text),
        "model": request.model,
    })

    # Step 1: Adapter Discovery
    discovery = await discover_adapter(request.sow_text, model=request.model)

    # Step 2: Generate config (pass matched adapter if found)
    matched = discovery.get("matched_adapter") if discovery["match_found"] else None
    result = await process_sow(request.sow_text, model=request.model, matched_adapter=matched)

    # Handle rejections
    if result.get("rejected"):
        log_event("generate_rejected", {
            "tenant_id": request.tenant_id,
            "reason": result["rejection"].get("reason", ""),
        })
        return {
            "status": "rejected",
            "rejection": result["rejection"],
            "model_used": result.get("model_used"),
            "discovery": discovery,
        }

    if not result["success"]:
        log_event("generate_failed", {
            "tenant_id": request.tenant_id,
            "error": result.get("error"),
        })
        raise HTTPException(
            status_code=422,
            detail={
                "error": result["error"],
                "raw_response": result.get("raw_response"),
                "blueprint": result.get("blueprint"),
                "catalog_entry": result.get("catalog_entry"),
            },
        )

    log_event("generate_completed", {
        "tenant_id": request.tenant_id,
        "model_used": result.get("model_used"),
        "adapter_discovered": discovery.get("path"),
        "target_system": result["blueprint"].get("integration_metadata", {}).get("target_system"),
    })

    return {
        "status": "success",
        "blueprint": result["blueprint"],
        "catalog_entry": result["catalog_entry"],
        "model_used": result.get("model_used"),
        "discovery": discovery,
    }

@app.post("/api/orchestrator/deploy")
async def deploy_blueprint(request: DeployRequest):
    """
    Split deployment:
    1. Save the blueprint to middleware/configs/{tenant_id}/{service_name}.json
    2. Add the catalog entry to the integration registry
    """
    deployment = split_deploy(
        blueprint=request.blueprint,
        catalog_entry=request.catalog_entry,
        service_name=request.service_name,
        tenant_id=request.tenant_id,
    )

    if not deployment.success:
        log_event("deploy_failed", {
            "tenant_id": request.tenant_id,
            "error": deployment.config_message,
        })
        raise HTTPException(
            status_code=400,
            detail=deployment.to_dict(),
        )

    log_event("deploy_completed", {
        "tenant_id": request.tenant_id,
        "service_name": request.service_name or request.catalog_entry.get("service_name"),
        "config_status": deployment.config_status,
        "registry_action": deployment.registry_result.action if deployment.registry_result else None,
    })

    return deployment.to_dict()

@app.post("/api/orchestrator/generate-and-deploy")
async def generate_and_deploy(request: GenerateRequest):
    """
    One-shot endpoint: SOW in → blueprint generated → deployed to middleware + registry.
    """
    if not request.sow_text.strip():
        raise HTTPException(status_code=400, detail="SOW text cannot be empty.")

    result = await process_sow(request.sow_text, model=request.model)

    if not result["success"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error": result["error"],
                "raw_response": result.get("raw_response"),
            },
        )

    deployment = split_deploy(
        blueprint=result["blueprint"],
        catalog_entry=result["catalog_entry"],
        tenant_id=request.tenant_id,
    )

    log_event("generate_and_deploy", {
        "tenant_id": request.tenant_id,
        "model_used": result.get("model_used"),
        "deploy_success": deployment.success,
    })
    
    return {
        "status": "success" if deployment.success else "partial_failure",
        "generation": {
            "blueprint": result["blueprint"],
            "catalog_entry": result["catalog_entry"],
            "model_used": result.get("model_used"),
        },
        "deployment": deployment.to_dict(),
    }

@app.post("/api/orchestrator/generate-from-upload")
async def generate_from_upload(
    sow_text: Optional[str] = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    model: Optional[str] = Form(default=None),
    tenant_id: Optional[str] = Form(default="default"),
):
    """Generate blueprint from uploaded files and/or pasted text."""
    # Extract text from uploaded files
    file_results = []
    for uploaded_file in files:
        content = await uploaded_file.read()
        extracted = extract_text_from_file(content, uploaded_file.filename)
        file_results.append((uploaded_file.filename, extracted))

    # Combine all text
    combined_text = combine_texts(sow_text or "", file_results)

    if not combined_text.strip():
        raise HTTPException(
            status_code=400,
            detail="No content provided. Paste text or upload at least one file.",
        )

    log_event("generate_upload_started", {
        "tenant_id": tenant_id,
        "files": [f[0] for f in file_results],
        "text_length": len(combined_text),
    })

    # Step 1: Adapter Discovery
    discovery = await discover_adapter(combined_text, model=model)

    # Step 2: Generate config (pass matched adapter if found)
    matched = discovery.get("matched_adapter") if discovery["match_found"] else None
    result = await process_sow(combined_text, model=model, matched_adapter=matched)

    # Handle rejections
    if result.get("rejected"):
        log_event("generate_rejected", {
            "tenant_id": tenant_id,
            "reason": result["rejection"].get("reason", ""),
        })
        return {
            "status": "rejected",
            "rejection": result["rejection"],
            "model_used": result.get("model_used"),
            "combined_text_preview": combined_text[:500] + "..." if len(combined_text) > 500 else combined_text,
            "discovery": discovery,
        }

    if not result["success"]:
        log_event("generate_failed", {"tenant_id": tenant_id, "error": result.get("error")})
        raise HTTPException(
            status_code=422,
            detail={
                "error": result["error"],
                "raw_response": result.get("raw_response"),
            },
        )

    log_event("generate_completed", {
        "tenant_id": tenant_id,
        "model_used": result.get("model_used"),
        "files_processed": [f[0] for f in file_results],
        "adapter_discovered": discovery.get("path"),
    })

    return {
        "status": "success",
        "blueprint": result["blueprint"],
        "catalog_entry": result["catalog_entry"],
        "model_used": result.get("model_used"),
        "files_processed": [f[0] for f in file_results],
        "discovery": discovery,
    }

@app.post("/api/orchestrator/reset-configs")
async def reset_configs(tenant_id: Optional[str] = None):
    """Demo utility: Deletes deployed config files from middleware/configs/."""
    configs_dir = Path(__file__).parent.parent.parent / "middleware" / "configs"
    deleted = []

    if tenant_id:
        # Reset specific tenant
        tenant_dir = configs_dir / tenant_id
        if tenant_dir.exists():
            for config_file in tenant_dir.glob("*.json"):
                config_file.unlink()
                deleted.append(f"{tenant_id}/{config_file.name}")
    else:
        # Reset all configs (flat + tenant dirs)
        if configs_dir.exists():
            for config_file in configs_dir.glob("*.json"):
                config_file.unlink()
                deleted.append(config_file.name)
            for tenant_dir in configs_dir.iterdir():
                if tenant_dir.is_dir():
                    for config_file in tenant_dir.glob("*.json"):
                        config_file.unlink()
                        deleted.append(f"{tenant_dir.name}/{config_file.name}")

    log_event("configs_reset", {"tenant_id": tenant_id or "all", "deleted": deleted})

    return {
        "status": "configs_cleared",
        "deleted": deleted,
        "count": len(deleted),
    }