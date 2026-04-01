# Interview Project Guide: RAG + Agentic AI Analytics System

## 1) Project Snapshot

### Project Name
RAG + Agentic AI Analytics Dashboard

### One-Line Pitch
A production-style Python application that combines retrieval-augmented generation (RAG), agentic reasoning, and an interactive dashboard to analyze uploaded business data and return grounded insights.

### Why This Project Matters
This project demonstrates practical AI engineering beyond a chatbot:
- Grounded responses using retrieved context (RAG)
- Tool-using reasoning flow (Agentic AI)
- Full-stack integration (FastAPI backend + dashboard frontend)
- Defensive design for real-world issues like API quotas, parsing failures, and missing dependencies

## 2) Problem Statement (PS)

### Business Problem
Teams want natural-language insights from internal business data (CSV/text) without manually writing SQL or BI queries every time.

### Technical Problem
Pure LLM answers can hallucinate and may ignore available local data. We need a system that:
- Retrieves relevant local context first
- Feeds context into reasoning flow
- Produces concise, numeric insights
- Handles provider outages and quota failures gracefully

### Goal
Build a reliable assistant that can ingest files, retrieve context, analyze trends, and visualize metrics in a dashboard.

## 3) Final Scope and Deliverables

### What Was Built
- RAG ingestion and retrieval pipeline
- Agentic analysis layer with provider abstraction
- FastAPI backend with ingestion, context, analysis, and stats APIs
- Browser dashboard with charts and forms
- Configurable support for Google Gemini, DeepSeek, and local Ollama (local path was tested and later removed from machine)
- Quota-safe deterministic fallback mode

### Key User Flows
1. Upload a CSV or TXT file
2. Ingest data into retrieval pipeline
3. Ask analytical question
4. Receive grounded response
5. View charts that update from latest uploaded data

## 4) Architecture Overview

## High-Level Flow
1. User uploads a file from dashboard
2. Backend parses file and converts rows into LangChain Documents
3. RAG pipeline chunks + stores locally, attempts Weaviate indexing
4. User asks analysis query
5. Agent retrieves context and calls LLM with concise prompt strategy
6. API returns answer; dashboard displays text + charts

## Logical Layers
- Presentation: frontend (HTML/CSS/JS + Chart.js)
- API: FastAPI endpoints
- Intelligence: LangChain agent + tools
- Retrieval: Weaviate (when available) + lexical fallback
- Config and infra: env-driven settings and provider switches

## 5) Tech Stack and Why Each Choice Was Made

### Core Language and Runtime
- Python 3.12 virtual environment chosen for library compatibility and stable LangChain/Pydantic behavior.

### AI and Orchestration
- LangChain: reusable abstractions for agent, tools, vector retrieval, and LLM wrappers.
- Google Gemini (primary): strong reasoning quality and easy API integration.
- DeepSeek (optional): OpenAI-compatible fallback path.
- Ollama (optional path in code): local inference support for zero-cloud mode.

### Retrieval and Data
- Weaviate: vector DB integration path for semantic retrieval.
- Local lexical fallback: ensures app still works when vector DB is unavailable.
- Pandas: robust CSV parsing and chart metrics generation.

### API and Frontend
- FastAPI + Uvicorn: fast API development and typing.
- Vanilla HTML/CSS/JS + Chart.js: lightweight dashboard with no framework overhead.

### Config and Validation
- pydantic-settings + dotenv: centralized environment-driven configuration.

## 6) Repository Structure and File Responsibilities

- .env.example: environment template for provider keys and toggles
- requirements.txt: dependency definitions
- README.md: quick-start documentation
- data/sample_business_metrics.csv: realistic sample dataset
- data/uploads/*.csv: runtime uploaded files
- src/config.py: all runtime settings and provider controls
- src/embeddings.py: embedding provider selection (google/local)
- src/rag_pipeline.py: ingestion, chunking, retrieval, fallback logic
- src/tools.py: agent tool registry and helper tools
- src/agent.py: LLM/provider initialization and analysis flow
- src/backend_server.py: FastAPI app and endpoint handlers
- src/main.py: CLI-style demo runner
- frontend/index.html: dashboard UI layout
- frontend/styles.css: visual design system
- frontend/app.js: API calls, chart rendering, form handlers
- frontend/server.py: static file server

## 7) How the Project Was Built (Step-by-Step Timeline)

### Phase 1: Baseline AI Core
Created core AI components:
1. Configuration model
2. Embedding initializer
3. RAG ingestion/retrieval pipeline
4. Agent tools and analysis agent
5. Demo entry point

### Phase 2: Full-Stack Experience
Added execution-ready UI and API:
1. FastAPI backend endpoints
2. Static frontend dashboard
3. Upload + analyze + stats workflow

### Phase 3: Dependency and Runtime Stabilization
Handled compatibility issues:
1. Updated package pins
2. Migrated to Python 3.12 environment
3. Fixed LangChain import path changes
4. Updated pydantic settings usage

### Phase 4: Provider and Quota Resilience
Improved reliability:
1. Provider abstraction (google/deepseek/ollama)
2. Startup validation for missing keys
3. Single-call analysis mode to reduce token/call cost
4. Context-size capping and low top-k retrieval
5. Deterministic local fallback when quota is exceeded

### Phase 5: Dashboard Data Correctness
Fixed chart update behavior:
1. Stats endpoint switched to latest uploaded CSV logic
2. Revenue grouping and month order normalization
3. Pie chart dimension fallback added (region -> channel -> product -> category -> segment)
4. Generic textual-column fallback for datasets without expected category fields

## 8) Backend API Contracts

### GET /health
Purpose:
- Service liveness
- Startup dependency status
- Indexed sources visibility

Typical response fields:
- status
- indexed_sources
- rag_enabled
- agent_enabled
- startup_error

### GET /api/stats
Purpose:
- Chart-ready metrics for dashboard

Returns:
- revenue_millions
- revenue_labels
- product_share
- total_sources

Behavior:
- Reads latest uploaded CSV first
- Chooses revenue column from mrr_usd/revenue/revenue_usd
- Derives pie dimension from known columns or generic textual fallback

### GET /api/context?query=...
Purpose:
- Retrieve compact context snippets from RAG

### POST /api/analyze
Body:
- query
- context_query (optional)

Returns:
- response string from provider or deterministic local fallback

### POST /api/ingest
Purpose:
- Upload and index TXT/CSV files

Returns:
- loaded_documents
- indexed_sources

## 9) RAG Design Details

### Ingestion
- TXT: full content as one Document
- CSV: each row converted to newline key:value text block

### Chunking
- RecursiveCharacterTextSplitter
- chunk_size and overlap controlled by settings

### Retrieval Strategy
1. Try vector similarity search if Weaviate store is active
2. If unavailable/fails, use local lexical overlap fallback

### Context Construction
- Maximum context size cap
- Each document block clipped to keep prompt compact
- Includes source metadata for traceability

## 10) Agent Design Details

### Provider Selection
In src/config.py:
- llm_provider controls runtime model source
- Supports google/deepseek/ollama

In src/agent.py:
- Google: ChatGoogleGenerativeAI
- DeepSeek: ChatOpenAI with custom base_url
- Ollama: ChatOllama

### Cost and Quota Controls
- single_call_mode sends one concise prompt instead of multi-iteration tool loops
- top_k_retrieval reduced for compact prompts
- max_context_chars limits payload size

### Quota Fallback
When quota/rate-limit errors are detected:
- deterministic local numeric summary is generated from retrieved context
- avoids complete feature outage
- provides actionable trend bullets with exact observed numbers

## 11) Frontend Design and Behavior

### UI Layout
- KPI cards: total revenue + indexed source count
- Revenue line chart
- Share doughnut chart
- Analyze form
- File upload form

### Data Flow
- On load: fetch stats and render KPIs/charts
- On ingest success: refresh dashboard metrics immediately
- On analyze submit: render response in text panel

### UX Goals
- Immediate visual feedback
- Minimal clicks to get first insight
- Works on desktop and mobile breakpoints

## 12) Configuration Model

Important .env keys:
- LLM_PROVIDER
- MODEL_NAME
- GOOGLE_API_KEY
- DEEPSEEK_API_KEY
- DEEPSEEK_BASE_URL
- OLLAMA_BASE_URL
- OLLAMA_MODEL
- EMBEDDING_PROVIDER
- EMBEDDING_MODEL
- WEAVIATE_URL
- WEAVIATE_API_KEY
- ENABLE_MOCK_ON_QUOTA_ERROR

Interview point:
The app is environment-driven, so switching providers does not require code edits.

## 13) Setup Guide (macOS/Linux and PowerShell)

### A) Create Virtual Environment
macOS/Linux:
- python3.12 -m venv .venv312
- source .venv312/bin/activate

PowerShell:
- py -3.12 -m venv .venv312
- .\.venv312\Scripts\Activate.ps1

### B) Install Dependencies
- pip install --upgrade pip setuptools wheel
- pip install -r requirements.txt

### C) Configure Environment
- copy .env.example to .env
- set provider and keys

### D) Start Backend
- ./.venv312/bin/python -m uvicorn backend_server:app --app-dir src --host 0.0.0.0 --port 8000

PowerShell equivalent:
- .\.venv312\Scripts\python -m uvicorn backend_server:app --app-dir src --host 0.0.0.0 --port 8000

### E) Start Frontend
- cd frontend
- python server.py

### F) Open App
- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health

## 14) Interview-Ready Deep Dive: File-by-File Creation Logic

### src/config.py
Why created:
- single source of truth for all environment/runtime settings

What to highlight:
- provider switching
- backward compatibility mapping for deprecated model names
- quota and retrieval control knobs

### src/rag_pipeline.py
Why created:
- isolate ingestion/retrieval complexity from API and agent

What to highlight:
- vector + lexical fallback architecture
- robust CSV parsing with delimiter and encoding tolerance
- context compaction to control token usage

### src/agent.py
Why created:
- centralize LLM orchestration and resilience strategy

What to highlight:
- provider-specific client initialization
- single-call prompt strategy for cost reduction
- deterministic fallback when cloud provider fails

### src/backend_server.py
Why created:
- expose platform as a reusable HTTP service

What to highlight:
- startup dependency checks
- strict file type validation on ingest
- latest-upload-driven stats with category fallback logic

### frontend/app.js
Why created:
- bridge backend endpoints to UI behavior

What to highlight:
- async fetch flows
- chart lifecycle management (destroy/recreate)
- ingestion triggers data refresh

### frontend/index.html and frontend/styles.css
Why created:
- simple, maintainable dashboard without framework overhead

What to highlight:
- deliberate visual system (typography/color/spacing)
- responsive grid behavior

## 15) Major Issues Encountered and How They Were Solved

### Dependency Compatibility
Issue:
- installation failures and version conflicts

Fix:
- modernized package versions and pinned stable combinations
- moved execution to Python 3.12 environment

### Model Availability Errors
Issue:
- model names unavailable for a specific key/project

Fix:
- listed available models from provider API
- switched to supported model id

### Quota Exceeded (429)
Issue:
- cloud model unavailable under free quota

Fix:
- reduced calls and context size
- implemented deterministic local fallback response

### Vector DB/Client Drift
Issue:
- Weaviate warnings and connectivity issues

Fix:
- added local retrieval fallback and continued operation

### Charts Not Updating Properly
Issue:
- stats endpoint did not always use latest uploaded dataset

Fix:
- sorted uploads by modification time
- expanded share-dimension detection logic

## 16) Performance and Cost Controls

Implemented controls:
- top_k_retrieval = 3
- max_context_chars = 1800
- single_call_mode = true
- local embeddings fallback option

Why this is interview-worthy:
- shows practical AI ops maturity (latency, cost, reliability)

## 17) Security and Production Considerations

Current baseline:
- API key usage through .env
- file type filtering on ingestion

Recommended production upgrades:
- authentication/authorization for endpoints
- request rate limiting
- upload size limits and malware scanning
- PII redaction before prompt construction
- structured logging and tracing

## 18) Trade-offs and Design Decisions

### Why FastAPI + Vanilla Frontend
- rapid development and easy debugging
- less build tooling complexity

### Why Keep Weaviate + Local Fallback
- best-effort semantic retrieval with graceful degradation

### Why Deterministic Fallback Instead of Hard Failure
- preserves user trust and app usability during provider incidents

## 19) How to Demo This in an Interview (5-7 Minutes)

Suggested script:
1. Show architecture at high level
2. Upload a CSV in dashboard
3. Show /api/context retrieval output
4. Ask an analysis query and show grounded response
5. Explain quota fallback and trigger/describe behavior
6. Show chart update from uploaded file
7. Close with production improvements roadmap

## 20) Common Interview Questions and Strong Answers

Q1: How did you reduce hallucination risk?
A:
- Forced retrieval context path and compact source snippets
- Prompt instructed model to use provided context only
- Added deterministic fallback for provider failures

Q2: What happens if vector DB is down?
A:
- App continues with local lexical retrieval
- No complete outage; quality may be lower but system remains functional

Q3: How did you handle LLM quota limits?
A:
- Reduced request size/calls and added deterministic fallback mode
- This preserves service continuity and user experience

Q4: How do you switch model providers?
A:
- Environment variables only; no core code changes required
- Provider abstraction in configuration + agent initialization

Q5: What would you do next for production?
A:
- add auth, observability, robust file governance, CI tests, and infrastructure hardening

## 21) Resume and Portfolio Bullet Points

Use these as-is or adapt:
- Built an end-to-end RAG + agentic analytics platform using Python, LangChain, FastAPI, and Chart.js.
- Implemented multi-provider LLM architecture (Google/DeepSeek/Ollama paths) with env-driven switching.
- Designed resilient retrieval with Weaviate primary path and lexical local fallback.
- Added quota-aware optimizations and deterministic local summary fallback to maintain uptime.
- Developed dynamic dashboard metrics pipeline that updates charts from newly ingested CSV files.

## 22) Exact Runbook Commands

Backend (macOS/Linux):
- cd /Users/utkarshgaur/python3/project_new
- ./.venv312/bin/python -m uvicorn backend_server:app --app-dir src --host 0.0.0.0 --port 8000

Frontend:
- cd /Users/utkarshgaur/python3/project_new/frontend
- python server.py

Quick checks:
- curl -s http://localhost:8000/health
- curl -s http://localhost:8000/api/stats

Analyze example:
- curl -s -X POST http://localhost:8000/api/analyze -H "Content-Type: application/json" -d '{"query":"Summarize revenue trend with numbers.","context_query":"revenue churn cac"}'

## 23) Current Known Gaps

- Weaviate client integration still emits deprecation/compatibility warnings in this environment.
- FastAPI startup hook uses on_event which is deprecated in newer versions (lifespan migration recommended).
- Automated tests are not yet added (unit/integration/e2e).

## 24) Improvement Roadmap

Priority 1:
- add test suite for ingest, stats, and analyze endpoints

Priority 2:
- migrate startup lifecycle to FastAPI lifespan

Priority 3:
- improve CSV schema inference and chart typing

Priority 4:
- add auth and per-user data isolation

Priority 5:
- formal observability (metrics, tracing, error budgets)

## 25) Final Interview Summary

This project proves end-to-end AI application engineering capability:
- LLM orchestration
- retrieval grounding
- API productization
- frontend integration
- reliability engineering under quota and dependency failures

If you present this with a short live demo plus the trade-offs section, it reads as practical product-building, not just a model wrapper.
