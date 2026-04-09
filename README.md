---
title: Agentic Config Integration Engine Orchestrator
emoji: 📈
colorFrom: gray
colorTo: green
sdk: docker
pinned: false
short_description: An enterprise-grade design-time AI tool that reads SOW
---
# AI-Assisted Integration Orchestration Engine (Agentic LangChain)

An enterprise-grade **design-time AI tool** that reads SOW (Statement of Work) documents — via text, PDF, or DOCX uploads — generates executable JSON configuration blueprints, simulates them against live APIs, and deploys them to a middleware gateway. All with zero manual coding.

The core AI-engine of FinSpark. It takes SOW documents, performs autonomous adapter discovery using ChromaDB, and generates deployment blueprints using LangChain agentic flows and Pydantic validation schemas. Contains both the FastAPI Backend and the Vite/React Design-time UI.

---

## 🚀 Live Demos

Experience the FinSpark ecosystem instantly via our live deployed frontends:
- **AI Orchestrator (Design-time UI)**: [Orchestrator Live App](https://agentic-config-integration-engine-o.vercel.app)
- **Main App (End-User Demo)**: [Main App Live](https://agentic-config-integration-engine-m.vercel.app)

*(Note: The Backend APIs, Middleware, and Mock APIs run as hidden background services and are accessed internally by these frontends).*

---

## Full Ecosystem Architecture

The AI Orchestrator is the design-time intelligence engine within the larger FinSpark ecosystem. It acts as the brain that configures the runtime middleware.

```text
    ┌───────────────────────────┐
    │       End User Apps       │      ┌───────────────────────────┐
    │     (Main App: 5173)      │      │  Integration Engineers    │
    └─────────────┬─────────────┘      │  (Orchestrator UI: 5174)  │
                  │                    └─────────────┬─────────────┘
                  ▼                                  ▼
    ┌───────────────────────────┐      ┌───────────────────────────┐
    │    Middleware Gateway     │◄─────┤  AI Orchestrator Backend  │
    │     (Runtime: 8002)       │      │  (Design-time API: 8003)  │
    └─────────────┬─────────────┘      └─────────────┬─────────────┘
                  │                                  │
                  ▼                                  ▼
    ┌───────────────────────────┐      ┌───────────────────────────┐
    │      External APIs        │◄─────┤       LLM Provider        │
    │  (Mock Providers: 8004)   │ sim. │(Ollama, Gemini, NVIDIA)   │
    └───────────────────────────┘      └───────────────────────────┘
```

### Components & Repositories

Use the table below to track the GitHub repositories for the FinSpark ecosystem.

| Component | Description | GitHub Repository Link |
|-----------|-------------|------------------------|
| **Middleware Gateway** | Runtime API gateway that isolates tenant traffic | [Middleware Repo](https://github.com/ARox2005/Agentic-Config-Integration-Engine-Middleware.git) |
| **Main App (Frontend Demo)**| Mock banking portal to test tenant configurations | [Main App Repo](https://github.com/ARox2005/Agentic-Config-Integration-Engine-Main-App.git) |
| **Mock APIs** | Simulated third-party providers (KYC, GST, etc.) | [Mock APIs Repo](https://github.com/ARox2005/Agentic-Config-Integration-Engine-mock-api-.git) |

**Orchestrator Tech Stack**: React + FastAPI + LangChain + ChromaDB + Multi-LLM Support.

## Key Features

- **Multi-format Input**: Paste text directly or upload PDF, DOCX, DOC, TXT, MD, and CSV files — or combine both
- **Multiple File Upload**: Drag-and-drop multiple documents simultaneously — all content is merged and sent to the LLM
- **RAG-Powered Adapter Discovery**: Uses ChromaDB and HuggingFace local embeddings (`all-MiniLM-L6-v2`) for semantic vector search, instantly retrieving the top 3 adapter matches to prevent context window overload.
- **Agentic Generation (LangChain)**: Uses `with_structured_output()` and strict Pydantic models to guarantee 100% compliant JSON blueprint outputs.
- **LangSmith Observability**: Complete tracing of prompt inputs, JSON outputs, tokens, and latency across the pipeline.
- **Mandatory vs Optional Detection**: The AI classifies each integration service as mandatory or optional based on SOW business rules
- **Scope Validation**: The AI rejects out-of-scope or impossible integrations with clear reasons and suggestions
- **Live Simulation**: Test the generated config against real APIs before deploying — see the full request/response pipeline
- **Split Deployment**: Config is saved to middleware (tenant-isolated), and a catalog entry is auto-added to the adapter registry
- **Tenant-Level Config Isolation**
- **API Version Coexistence**: Multiple versions of the same adapter can coexist in the registry — the AI selects the appropriate version
- **Full Audit Trail**: Every action (generate, deploy, reject, reset) is logged with timestamps and tenant context — viewable in the UI
- **Dynamic Registry**: The adapter catalog is built and maintained entirely by the AI — zero manual data entry

## Supported File Types

| Extension | Handler |
|-----------|---------|
| `.pdf` | PyPDF2 text extraction (page-by-page) |
| `.docx` / `.doc` | python-docx (paragraphs + tables) |
| `.txt` / `.md` / `.csv` | Direct UTF-8 decode |
| Others | Returned as unsupported with error message |

> **Note:** Scanned/image-based PDFs cannot be extracted. A warning is returned if no text is found.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- **An LLM Backend**: Choose either an **API Key** (OpenAI / NVIDIA NIM) OR a local **Ollama** installation.
- **LangSmith API Key** (optional but highly recommended for tracing)

## Local Setup & Quick Start (Full Ecosystem)

To run the entire FinSpark pipeline locally, you will need to open **5 separate terminal tabs** and start each service in this workflow.

> **Tip**: Since this is a monorepo structure, ensure you run these commands from within their respective root folders.

### 1. Mock APIs (Port 8004)
Provides simulated external endpoints (KYC, GST, etc.) for testing configurations during design-time.
1. `cd mock-apis`
2. `python -m venv .venv` and activate it (e.g., `.venv\Scripts\activate` on Windows)
3. `pip install -r requirements.txt`
4. `uvicorn src.main:app --reload --port 8004`

### 2. Middleware Gateway (Port 8002)
The runtime engine that intercepts requests from the Main App, validates them, and routes them to mock/real APIs based on tenant configs.
1. `cd middleware`
2. `python -m venv .venv` and activate it
3. `pip install -r requirements.txt`
4. `uvicorn src.main:app --reload --port 8002`

### 3. AI Orchestrator Backend (Port 8003)
The design-time AI engine. **Requires an LLM `.env` file first.**

Create a `.env` file inside the `orchestrator/` folder:
```env
# LLM Configuration - Depending on your backend, configure one of the following:

# Option A: NVIDIA API (Cloud)
NVIDIA_API_KEY="your_nvidia_key_here"
NVIDIA_MODEL="google/gemma-3n-e4b-it"

# Option B: Ollama (Local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:latest
OLLAMA_API_KEY="" # Usually empty for local deployment

# (Optional) LangSmith MLOps Tracking
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="your_langsmith_key_here"
LANGCHAIN_PROJECT="FinSpark_Orchestrator_v2"
```

1. `cd orchestrator`
2. `python -m venv .venv` and activate it
3. `pip install -r requirements.txt`
4. Verify backend: `curl http://localhost:8003/health`
5. `uvicorn backend.main:app --reload --port 8003`

### 4. AI Orchestrator Frontend (Port 5174)
The React dashboard for uploading SOWs and generating configurations.
1. `cd orchestrator/frontend`
2. `npm install`
3. `npm run dev` (Check that it opens on **http://localhost:5174**)

### 5. FinSpark Main App (Port 5173)
The end-user banking demo application that tests the runtime tenant integrations.
1. `cd main-app`
2. `npm install`
3. `npm run dev` (Check that it opens on **http://localhost:5173**)

## Demo Walkthrough

### Flow A: Generate, Simulate & Deploy
1. Open **http://localhost:5174** (Orchestrator UI)
2. Check the status bar — the API connection should show as online
3. **Select a tenant** from the dropdown (Default, Tenant A, or Tenant B)
4. **Input** — choose one or more:
   - Click **"Load sample SOW"** for a quick test
   - Paste SOW text directly into the text area
   - Drag-and-drop PDF/DOCX files into the upload zone (multiple files supported)
5. Click **"→ Generate Blueprint"** — wait for the AI (~2–10 seconds)
   - The AI first runs **Adapter Discovery** — checking the registry for existing matching profiles
   - If a match is found (Path A), the AI generates a config tailored to that adapter
   - If no match (Path B), the AI generates both a new adapter profile and the config from scratch
   - The AI classifies the integration as **mandatory** or **optional** based on SOW business rules
6. **Preview** — review the generated Blueprint and Catalog Entry
   - A **discovery banner** shows: 🔗 "Matched Adapter: KYC Provider v1.0 (95%)" or 🆕 "New adapter profile"
   - Both JSON outputs are editable. Switch between tabs and tweak if needed
7. Click **"▶ Simulate"** — the config is tested against the live mock API
8. If satisfied, click **"🚀 Deploy to Middleware"**
9. ✅ Config saved to middleware, registry entry created
10. Click **"📋 Show Audit Trail"** to view the logged events

### Flow C: Test Adapter Discovery (Reuse an Existing Adapter)
After deploying a KYC config (Flow A), test that the AI recognizes it:
1. Paste a **different KYC SOW** (different client, same service)
2. Click **"→ Generate Blueprint"**
3. The discovery banner should show: 🔗 **"Matched Adapter: KYC Provider v1.0"**
4. The AI generates a config tailored to the existing adapter rather than creating a new profile.

### Flow D: GST Service — Full Demo with Example SOW
This demonstrates the complete pipeline for a new service. Copy-paste this SOW:
```
Integration SOW: GST Validation Service

Business Rule:
Before processing a business loan application, validate the applicant's GST registration status.
If gst_status is "INACTIVE" or the registration is not found, reject the application.

API Details:
- Service Name: gst_service
- Version: v1.0
- Endpoint: http://localhost:8004/mock-gst/validate
- Method: POST
- Auth Type: Bearer
- Credential Vault Reference: ENV.GST_SERVICE_KEY

Expected Request Fields:
- gstin (GST Identification Number)
- business_name
- pan_number

Expected Response Fields:
- status
- gst_status (ACTIVE / INACTIVE)
- business_name
- registration_date
- gst_type

Source Data Mapping:
- gstin comes from: $.business_data.gstin
- business_name comes from: $.business_data.businessName
- pan_number comes from: $.business_data.panNumber

Response Logic:
- If $.gst_status == "INACTIVE" then return "REJECTED"
```
**Testing steps:**
1. Open Orchestrator → paste the SOW above → click **Generate Blueprint**
2. In the **Preview**, verify the mappings.
3. Click **Simulate** → should see a successful response from the mock API.
4. Click **Deploy** → config saved!

### Flow F: Test Rejection (Out-of-Scope Documents)
1. Paste irrelevant text (e.g., a marketing document or random text)
2. Click **"→ Generate Blueprint"**
3. The AI will return a **rejection** with:
   - **Reason**: Why this can't be an integration
   - **Missing Info**: What specific details are needed
   - **Suggestion**: What the user should provide

## Switching LLM Providers

Because FinSpark uses **LangChain**, switching underlying models takes just two lines of code (no massive rewrites required!).

### Option 1: Ollama (Default — Local, Free)
No changes needed. Ensure `llama3.2` is running via `ollama serve`.

### Option 2: OpenAI / NVIDIA / Gemma (API Based)
Install the LangChain plugin: `pip install langchain-openai`
Add your key to `.env`: `OPENAI_API_KEY="..."`

Change the engine in `llm_engine.py`:
```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o-mini",          # Or "google/gemma-3n-e4b-it" 
    base_url="https://api.openai.com/v1",  # Or "https://integrate.api.nvidia.com/v1"
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)
```

### What Stays the Same Across All Providers
Regardless of which LLM you use, these parts **never change**:
- `SYSTEM_PROMPT` — same instructions for all models (including scope validation)
- `_extract_json_from_response()` — triple-fallback JSON parser
- `_validate_blueprint()` / `_validate_catalog_entry()` — structural validators
- `text_extractor.py` — file processing is LLM-agnostic

## API Reference (Port 8003)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/health/ollama` | Ollama + model status |
| GET | `/api/orchestrator/registry` | List all adapters in catalog |
| GET | `/api/orchestrator/registry/{name}` | Lookup specific adapter |
| GET | `/api/orchestrator/registry/{name}/versions` | List all versions of an adapter |
| GET | `/api/orchestrator/audit?limit=50` | View audit trail (recent events) |
| POST | `/api/orchestrator/generate` | Generate blueprint from SOW text |
| POST | `/api/orchestrator/generate-from-upload` | Generate blueprint from uploaded files + text |
| POST | `/api/orchestrator/deploy` | Deploy blueprint + registry entry (tenant-isolated) |
| POST | `/api/orchestrator/generate-and-deploy` | One-shot generate + deploy (tenant-isolated) |
| POST | `/api/orchestrator/reset-configs` | Delete deployed configs (optional `tenant_id` filter) |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `Cannot connect to AI Backend` | For API providers, check your API key in `.env`. For local, run `ollama serve` |
| `Model not found` | For API providers, verify the exact model string. For Ollama, run `ollama pull <model>` |
| `OpenAIError: API key must be set` | Ensure your `.env` contains the correct key and the FastAPI server was restarted. |
| LLM returns invalid JSON | Try a larger model (e.g., `llama3:70b`) or use Gemini/GPT |
| PDF extraction empty | The PDF may be scanned/image-based. Use a text-based PDF or DOCX instead |
| `Integration Rejected` | The uploaded document doesn't describe a valid API integration. Check the rejection message for details |
| File upload not working | Ensure `python-multipart` is installed: `pip install python-multipart` |

## Deployment
The backend strictly requires a persistent disk volume since it utilizes ChromaDB and maintains local JSON registries. Hugging Face Spaces (via Docker) is recommended for the backend, and Vercel for the frontend.

## License
Built for the FinSpark Hackathon.
