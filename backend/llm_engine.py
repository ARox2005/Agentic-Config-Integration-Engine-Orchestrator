import json
import os
import re
import httpx
from typing import Optional

from ollama import AsyncClient

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .schemas import AgentOutput

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# ──────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are an enterprise integration architect AI. Your job is to read a Statement of Work (SOW) document and generate configuration JSON for a middleware gateway.

You operate in two modes depending on context provided:

**MODE A — Existing Adapter Profile Provided**
When you receive an "MATCHED ADAPTER PROFILE" section, an existing adapter has been identified. Your job is to generate ONLY the client-level configuration (blueprint) that maps the SOW's data fields into the adapter's expected schema.
- Use the adapter's target_endpoint, credential_reference, and mandatory_fields as your template.
- The catalog_entry should match the existing adapter (same name, same version).
- Focus on generating precise field mappings from the SOW's source data to the adapter's mandatory_fields.

**MODE B — No Adapter Match (New Profile)**
When no matched adapter is provided, you must generate BOTH:
- A blueprint (the client configuration)
- A catalog_entry (the base API profile for the registry — so future SOWs can match against it)
Extract all technical details (endpoint, auth, fields) directly from the SOW.

---
**SCOPE CHECK — IMPORTANT**
Before generating, evaluate whether the SOW describes a valid, achievable API integration. If the document:
- Does NOT describe an API integration (e.g., it's a marketing document, a legal contract, or irrelevant text)
- Contains contradictory or impossible requirements
- Lacks the minimum information needed (no endpoint, no field mappings, no clear target system)
Then return this rejection response instead:
{
  "blueprint": null,
  "catalog_entry": null,
  "rejection": {
    "reason": "<Clear explanation of why this cannot be turned into an integration>",
    "missing_info": ["<list of specific missing pieces, e.g., 'endpoint URL', 'field mapping'>"],
    "suggestion": "<What the user should provide to make this work>"
  }
}
Only reject if the document genuinely cannot produce a valid integration. If you can reasonably infer missing details, proceed with generation.

---
**MANDATORY vs OPTIONAL SERVICE DETECTION**
Analyze the SOW to classify each integration service as mandatory or optional:
- **Mandatory**: The SOW states the integration MUST happen, or it's a prerequisite for the business process (e.g., "KYC verification is required before loan approval")
- **Optional**: The SOW describes the integration as a nice-to-have, conditional, or future phase (e.g., "optionally check credit score if available")
Include this classification in the blueprint under "service_classification".

---

**Output 1: "blueprint"**
This is an executable configuration file for a middleware gateway. It MUST follow this exact schema:
{
  "integration_metadata": {
    "target_system": "<Name of the external API/service>",
    "api_version": "<Version from the SOW>"
  },
  "service_classification": {
    "priority": "<mandatory | optional>",
    "reason": "<Why this service is mandatory or optional, based on the SOW's business rules>"
  },
  "security_config": {
    "auth_type": "<Bearer | ApiKey | Basic>",
    "credential_vault_reference": "<ENV.VARIABLE_NAME — extract from SOW>",
    "target_url": "<Full endpoint URL from the SOW>"
  },
  "schema_transformation_rules": {
    "request_mapping": {
      "<target_field>": "<JSONPath expression like $.source_object.field_name>"
    },
    "response_logic": "<Business rule from SOW, e.g., if $.field > value then return 'ACTION'>"
  }
}
Rules for the blueprint:
- credential_vault_reference MUST start with "ENV." — never put actual keys or passwords.
- request_mapping values MUST use JSONPath notation starting with "$."
- For field concatenation, use: "$.obj.field1 + ' ' + $.obj.field2"
- response_logic should be a human-readable conditional from the SOW's business rules.
---
**Output 2: "catalog_entry"**
This is the adapter's Technical Profile for the registry. Multiple versions of the same adapter can coexist.
It MUST follow this schema:
{
  "name": "<Human-readable name of the target system>",
  "service_name": "<lowercase_snake_case config filename from the SOW, e.g., kyc_provider, gst_service. This becomes the config file name.>",
  "version": "<API version — e.g., v1.0, v2.0. Multiple versions of the same adapter can coexist in the registry.>",
  "description": "<One-line description of what this integration does>",
  "category": "<Category: e.g., Identity Verification, Payment Gateway, Credit Bureau>",
  "provider": "<Provider name: e.g., Experian, Razorpay>",
  "supported_actions": ["<list of actions: e.g., Verify Identity, Check Credit Score>"],
  "credential_reference": "<Same ENV.XXX as in the blueprint>",
  "target_endpoint": "<Same URL as in the blueprint>",
  "technical_interface": {
    "protocol": "<REST | SOAP | GraphQL>",
    "method": "<POST | GET | PUT>",
    "authentication_methods": ["<Bearer | ApiKey | OAuth2 | Basic>"]
  },
  "data_schema": {
    "mandatory_fields": ["<fields the API requires>"],
    "optional_fields": ["<fields the API can accept but doesn't require>"],
    "output_structure": ["<fields the API returns>"]
  },
  "expected_request_fields": ["<same as mandatory_fields — for backward compatibility>"],
  "expected_response_fields": ["<same as output_structure — for backward compatibility>"]
}
---
**Your complete response must be exactly this structure, nothing else:**

Success case:
{
  "blueprint": { ... },
  "catalog_entry": { ... }
}

Rejection case:
{
  "blueprint": null,
  "catalog_entry": null,
  "rejection": { ... }
}
"""

# ──────────────────────────────────────────────
# Core LLM Engine
# ──────────────────────────────────────────────

async def process_sow(sow_text: str, model: Optional[str] = None, matched_adapter: Optional[dict] = None) -> dict:
    """
    Process a Statement of Work document through the LLM.
    Args:
        sow_text: The full SOW document text.
        model: Override the default Ollama model.
        matched_adapter: If adapter discovery found a match, pass the adapter profile here.
                         The LLM will generate a config targeted to this adapter (Path A).
                         If None, the LLM generates both profile + config from scratch (Path B).
    Returns:
        dict with keys:
        - success: bool
        - blueprint: dict (the middleware config)
        - catalog_entry: dict (the registry entry)
        - error: str (if failed)
        - raw_response: str (the raw LLM output, for debugging)
    """
    model_name = model or "meta/llama-3.3-70b-instruct"

    # 1. Initialize the LangChain Chat model
    # We set temperature to 0 for highly deterministic generation
    llm = ChatOpenAI(
        model="meta/llama-3.3-70b-instruct",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
        temperature=0.2,
    )
    
    # 2. Bind our Pydantic model directly to the LLM. 
    # This forces the LLM to return data exactly matching the AgentOutput schema we defined.
    structured_llm = llm.with_structured_output(AgentOutput)
    
    # 3. Construct raw messages (Bypassing LangChain's template parser to avoid JSON {} errors)
    if matched_adapter:
        # Path A: Match Found
        adapter_profile = matched_adapter.get("profile", matched_adapter)
        human_text = f"""An existing adapter profile matches. Generate ONLY the client mapping blueprint.
            
--- MATCHED ADAPTER PROFILE ---
{json.dumps(adapter_profile, indent=2)}
--- END ADAPTER PROFILE ---
--- START OF SOW DOCUMENT ---
{sow_text}
--- END OF SOW DOCUMENT ---"""
    else:
        # Path B: No Match Found
        human_text = f"""No existing adapter matches. Generate BOTH the catalog_entry and the mapping blueprint.
--- START OF SOW DOCUMENT ---
{sow_text}
--- END OF SOW DOCUMENT ---"""

    # Assemble the final message array
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=human_text)
    ]
    
    try:
        # Execute the LLM directly with our messages! 
        result: AgentOutput = await structured_llm.ainvoke(messages)

        
        # Check if the AI decided to reject the SOW
        if result.rejection and result.blueprint is None:
            return {
                "success": False,
                "rejected": True,
                "rejection": result.rejection.model_dump(),  # Convert Pydantic object back to dict 
                "blueprint": None,
                "catalog_entry": None,
                "raw_response": "LangChain Structured Output",
                "model_used": model_name,
                "error": None,
            }

        catalog = result.catalog_entry.model_dump() if result.catalog_entry else None
        if matched_adapter and not catalog:
            catalog = matched_adapter.get("profile", matched_adapter)

        # Return Success
        return {
            "success": True,
            "blueprint": result.blueprint.model_dump() if result.blueprint else None,
            "catalog_entry": catalog,
            "raw_response": "LangChain Structured Output",
            "model_used": model_name,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"LangChain Generation failed: {str(e)}",
            "blueprint": None,
            "catalog_entry": None,
            "raw_response": None,
            "model_used": model_name
        }

async def check_ollama_status() -> dict:
    """Check if the NVIDIA API is reachable and the model is available."""
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return {
            "ollama_running": False, # Kept for UI compatibility
            "configured_model": "meta/llama-3.3-70b-instruct",
            "model_available": False,
            "available_models": [],
            "error": "NVIDIA_API_KEY is missing from .env",
        }
    
    try:
        # We ping the OpenAI-compatible /models endpoint provided by NVIDIA
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            available_models = [m.get("id") for m in data.get("data", [])]
            
            return {
                "ollama_running": True,  # Tricks UI into showing green status
                "configured_model": "meta/llama-3.3-70b-instruct",
                "model_available": "meta/llama-3.3-70b-instruct" in available_models,
                "available_models": available_models,
            }
    except Exception as e:
        return {
            "ollama_running": False,
            "configured_model": "meta/llama-3.3-70b-instruct",
            "model_available": False,
            "available_models": [],
            "error": f"Cannot connect to NVIDIA API. Error: {str(e)}",
        }

