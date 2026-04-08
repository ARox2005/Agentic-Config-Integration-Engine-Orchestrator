"""
Intent Router — AI-powered adapter selection.

Given a raw payload (and optionally a natural language intent),
queries Ollama to determine which registered adapter(s) should
handle the request.
"""

import os
import json
from typing import Optional

import httpx

from .registry import get_all_adapters

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

ROUTING_PROMPT = """You are an intelligent API router. Your job is to examine an incoming data payload and determine which registered adapter should handle it.

You will receive:
1. A list of available adapters (each with name, description, expected_request_fields, and target_endpoint)
2. An incoming payload (JSON data)
3. Optionally, a natural language intent from the user

Your task:
- Match the payload's field names and structure against each adapter's expected_request_fields
- Consider the user's intent if provided
- Pick the BEST matching adapter (or multiple if the payload spans multiple services)
- If NO adapter matches, say so clearly

Return ONLY a JSON object in this exact format:
{
  "routed": true,
  "selected_adapters": [
    {
      "adapter_name": "<exact name from registry>",
      "confidence": <0.0 to 1.0>,
      "reason": "<one-line explanation of why this adapter was chosen>"
    }
  ]
}

If no adapter matches:
{
  "routed": false,
  "selected_adapters": [],
  "reason": "<why no adapter could handle this payload>"
}

Rules:
- adapter_name MUST exactly match a name from the registry
- confidence should reflect how well the payload matches the adapter's expected fields
- If multiple adapters match, list them in priority order
- Be strict: do NOT route to an adapter if the payload has no relevant fields for it
"""


async def route_intent(
    payload: dict,
    intent: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Use Ollama to determine which adapter(s) should handle the given payload.

    Args:
        payload: The raw incoming data payload
        intent: Optional natural language description of what the user wants
        model: Optional Ollama model override

    Returns:
        dict with routing decision, selected adapters, and reasoning
    """
    model_name = model or OLLAMA_MODEL

    # 1. Fetch the current adapter registry
    registry_result = get_all_adapters()
    adapters = registry_result.get("adapters", [])

    if not adapters:
        return {
            "success": False,
            "routed": False,
            "error": "No adapters registered. Deploy an integration first.",
            "selected_adapters": [],
        }

    # 2. Build a summary of available adapters for the LLM
    adapter_summaries = []
    for adapter in adapters:
        adapter_summaries.append({
            "name": adapter.get("name"),
            "description": adapter.get("description", ""),
            "expected_request_fields": adapter.get("expected_request_fields", []),
            "expected_response_fields": adapter.get("expected_response_fields", []),
            "target_endpoint": adapter.get("target_endpoint", ""),
        })

    # 3. Build the user prompt
    user_prompt = f"""Here are the available adapters:

{json.dumps(adapter_summaries, indent=2)}

Here is the incoming payload:

{json.dumps(payload, indent=2)}
"""

    if intent:
        user_prompt += f"""
The user's intent is: "{intent}"
"""

    user_prompt += """
Analyze the payload and determine which adapter(s) should handle this request. Return ONLY the JSON response."""

    # 4. Call Ollama
    ollama_payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": ROUTING_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=ollama_payload,
            )

            if response.status_code != 200:
                return {
                    "success": False,
                    "routed": False,
                    "error": f"Ollama returned status {response.status_code}",
                    "selected_adapters": [],
                }

            data = response.json()
            raw_content = data.get("message", {}).get("content", "")

    except httpx.ConnectError:
        return {
            "success": False,
            "routed": False,
            "error": "Cannot connect to Ollama. Is it running?",
            "selected_adapters": [],
        }
    except Exception as e:
        return {
            "success": False,
            "routed": False,
            "error": f"Ollama error: {str(e)}",
            "selected_adapters": [],
        }

    # 5. Parse the LLM response
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        return {
            "success": False,
            "routed": False,
            "error": "LLM returned invalid JSON for routing decision.",
            "raw_response": raw_content,
            "selected_adapters": [],
        }

    # 6. Validate adapter names against registry
    valid_names = {a.get("name") for a in adapters}
    selected = parsed.get("selected_adapters", [])

    validated_adapters = []
    for sel in selected:
        name = sel.get("adapter_name", "")
        if name in valid_names:
            validated_adapters.append(sel)
        # silently skip hallucinated adapter names

    return {
        "success": True,
        "routed": parsed.get("routed", len(validated_adapters) > 0),
        "selected_adapters": validated_adapters,
        "reason": parsed.get("reason"),
        "model_used": model_name,
        "adapters_available": len(adapters),
    }
