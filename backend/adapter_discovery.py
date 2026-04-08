"""
Adapter Discovery Engine — Semantic matching of SOW requirements
against registered adapter profiles.

Given an SOW document, reads the adapter registry's Technical Profiles
and determines if an existing adapter can handle the integration.
If found, returns the matched adapter so the LLM can generate a
targeted client configuration. If not found, signals Path B (new profile).
"""

import os
import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .registry import get_adapter_profiles_for_discovery
from .vector_store import search_similar_adapters

# NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

DISCOVERY_PROMPT = """You are an adapter discovery engine for an enterprise integration middleware.

You will receive:
1. A list of registered adapter Technical Profiles (each with name, category, provider, supported_actions, technical_interface, data_schema, and target_endpoint)
2. An SOW (Statement of Work) or BRD (Business Requirement Document)

Your job is to determine if any EXISTING adapter profile can handle the integration described in the SOW.

**Matching Criteria (in priority order):**
1. **Category/Provider match**: Does the SOW mention the same service category or provider name? (e.g., SOW says "KYC verification" and adapter category is "Identity Verification")
2. **Endpoint match**: Does the SOW reference the same or similar endpoint URL?
3. **Field compatibility**: Do the SOW's required fields overlap with the adapter's mandatory_fields?
4. **Protocol/Auth match**: Does the SOW's auth type (Bearer, OAuth2, API Key) match the adapter's authentication_methods?
5. **Version selection**: If the adapter has multiple versions, pick the one mentioned in the SOW or default to the latest stable version.

**Return ONLY a JSON object in this exact format:**

If an existing adapter matches:
{
  "path": "existing",
  "match_found": true,
  "matched_adapter": {
    "name": "<exact adapter name from registry>",
    "version": "<selected version>",
    "confidence": <0.0 to 1.0>,
    "reason": "<why this adapter matches the SOW requirements>",
    "field_coverage": "<which mandatory fields are covered vs missing>"
  }
}

If no adapter matches:
{
  "path": "new",
  "match_found": false,
  "matched_adapter": null,
  "reason": "<why no existing adapter matches — be specific>"
}

**Rules:**
- adapter name MUST exactly match a name from the registry
- confidence 0.8+ = strong match (same provider/category + compatible fields)
- confidence 0.6-0.8 = partial match (same category but field gaps)
- Below 0.6 = not a match — return path "new"
- If the SOW explicitly names a provider that exists in the registry, that should strongly boost confidence
- Only match if the adapter can genuinely handle the SOW's requirements. A KYC adapter cannot handle a payment gateway SOW.
"""


async def discover_adapter(
    sow_text: str,
    model: Optional[str] = None,
) -> dict:
    """
    Analyze the SOW and check the adapter registry for a matching profile.

    Args:
        sow_text: The SOW/BRD document text
        model: Optional Ollama model override

    Returns:
        dict with:
        - path: "existing" or "new"
        - match_found: bool
        - matched_adapter: dict or None (name, version, confidence, reason)
        - profiles_checked: int
    """

    # 1. Get adapter profiles from registry
    profiles = get_adapter_profiles_for_discovery()

    if not profiles:
        return {
            "path": "new",
            "match_found": False,
            "matched_adapter": None,
            "reason": "Registry is empty — no adapter profiles to match against.",
            "profiles_checked": 0,
        }

    # RAG: Search ChromaDB for the Top 3 most semantically similar adapters to the SOW
    try:
        candidate_profiles = search_similar_adapters(sow_text=sow_text, top_k=3)
    except Exception as e:
        print(f"[DISCOVERY] ChromaDB search failed: {e}. Fallback to passing all profiles.")
        candidate_profiles = profiles
        
    if not candidate_profiles:
        return {
            "path": "new",
            "match_found": False,
            "matched_adapter": None,
            "reason": "Vector search returned no results.",
            "profiles_checked": len(profiles),
        }

    # 2. Build prompt
    user_prompt = f"""Here are the registered adapter Technical Profiles:

{json.dumps(candidate_profiles, indent=2)}

Here is the SOW/BRD document to analyze:

--- START OF SOW ---
{sow_text}
--- END OF SOW ---

Determine if any existing adapter can handle this integration. Return the JSON result."""

    model_name = model or "meta/llama-3.3-70b-instruct"

    # 3. Call NVIDIA API via Langchain
    try:
        llm = ChatOpenAI(
            model="meta/llama-3.3-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_API_KEY"),
            temperature=0.1
        )
        
        messages = [
            SystemMessage(content=DISCOVERY_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        # We don't use structured output here since we want raw JSON text to parse
        response = await llm.ainvoke(messages)
        raw_content = response.content

    except Exception as e:
        return {
            "path": "new",
            "match_found": False,
            "matched_adapter": None,
            "reason": f"Discovery unavailable ({str(e)}). Defaulting to new profile.",
            "profiles_checked": len(profiles),
        }


    # 4. Parse
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return {
            "path": "new",
            "match_found": False,
            "matched_adapter": None,
            "reason": "Discovery returned invalid JSON. Defaulting to new profile.",
            "profiles_checked": len(profiles),
        }

    # 5. Validate
    matched = parsed.get("matched_adapter")
    if matched and parsed.get("match_found"):
        # Verify the adapter name actually exists in registry
        valid_names = {p["name"] for p in profiles}
        if matched.get("name") not in valid_names:
            return {
                "path": "new",
                "match_found": False,
                "matched_adapter": None,
                "reason": "Discovery returned a non-existent adapter name. Defaulting to new profile.",
                "profiles_checked": len(profiles),
            }

        # Check confidence threshold
        confidence = matched.get("confidence", 0)
        if confidence < 0.6:
            return {
                "path": "new",
                "match_found": False,
                "matched_adapter": None,
                "reason": f"Best match was {matched.get('name')} at {confidence:.0%} — too low. Creating new profile.",
                "profiles_checked": len(profiles),
            }

        # Find the full profile for the matched adapter
        full_profile = next((p for p in profiles if p["name"] == matched["name"]), None)

        return {
            "path": "existing",
            "match_found": True,
            "matched_adapter": {
                **matched,
                "profile": full_profile,  # Include full profile for the config generator
            },
            "profiles_checked": len(profiles),
        }

    return {
        "path": parsed.get("path", "new"),
        "match_found": False,
        "matched_adapter": None,
        "reason": parsed.get("reason", "No match found."),
        "profiles_checked": len(profiles),
    }
