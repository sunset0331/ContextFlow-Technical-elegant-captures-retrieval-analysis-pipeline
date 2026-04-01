# Interview Revision Sheet (Quick Read)

## 1) 30-Second Pitch
I built an end-to-end AI analytics application that blends RAG and Agentic AI. Users upload CSV/TXT data, the system retrieves relevant context, the agent generates grounded insights, and a dashboard visualizes trends in real time. The stack is Python + FastAPI + LangChain + Chart.js with provider-switching support (Google/DeepSeek/Ollama path) and reliability fallbacks for quota and vector DB issues.

## 2) Problem -> Solution
Problem:
- Business teams need quick, trustworthy insights from internal data without writing queries manually.

Solution:
- Retrieval first (RAG) to ground answers in uploaded data.
- Agent orchestration for analysis behavior.
- API + dashboard for usable product experience.
- Quota-safe and dependency-safe fallback behavior for reliability.

## 3) Architecture in 6 Steps
1. Upload file from dashboard.
2. Backend parses TXT/CSV into documents.
3. RAG pipeline chunks and stores docs.
4. Retrieval finds relevant context for query.
5. Agent prompts LLM with compact grounded context.
6. Response + chart updates returned to UI.

## 4) Core Tech and Why
- Python 3.12: stable dependency compatibility.
- FastAPI: fast typed backend development.
- LangChain: agent, tools, and retrieval abstractions.
- Weaviate (primary) + lexical fallback: resilient retrieval.
- Pandas: robust CSV processing and stats aggregation.
- Chart.js: lightweight visual dashboard.

## 5) Most Important Files to Explain
- [src/config.py](src/config.py): provider toggles, model settings, quota controls.
- [src/rag_pipeline.py](src/rag_pipeline.py): ingestion, chunking, retrieval, local fallback.
- [src/agent.py](src/agent.py): provider initialization, single-call mode, quota fallback summary.
- [src/backend_server.py](src/backend_server.py): API endpoints, startup checks, dynamic stats logic.
- [frontend/app.js](frontend/app.js): fetch APIs, render charts, handle analyze/ingest flows.
- [INTERVIEW_PROJECT_GUIDE.md](INTERVIEW_PROJECT_GUIDE.md): full deep-dive narrative.

## 6) Endpoints You Should Memorize
- GET /health
- GET /api/stats
- GET /api/context?query=...
- POST /api/analyze
- POST /api/ingest

## 7) Biggest Engineering Decisions
- Environment-driven provider switch (no code change needed per provider).
- Single-call analysis mode to reduce cost/latency.
- Context-size cap and low top-k retrieval for quota control.
- Deterministic local summary fallback for 429/quota events.
- Stats built from latest uploaded CSV, not static sample values.

## 8) Debugging Stories (Great Interview Material)
1. Dependency/runtime mismatch:
- Problem: install/runtime breaks on newer Python path.
- Action: moved to Python 3.12 and aligned package versions.
- Result: stable backend startup and consistent behavior.

2. Model not available / quota exceeded:
- Problem: provider/model incompatibility and 429s.
- Action: supported model selection + reduced calls/context + fallback summary.
- Result: app remains usable even when cloud quota is exhausted.

3. Charts not updating correctly:
- Problem: stats source selection didn’t always reflect latest upload.
- Action: switched to most-recent-file logic and stronger category fallback.
- Result: pie/line charts update with uploaded dataset dimensions.

## 9) Trade-Offs (Say This Clearly)
- Using vanilla frontend over React: faster delivery, less tooling overhead.
- Keeping Weaviate plus local fallback: better resilience over strict dependence on one store.
- Deterministic fallback is less fluent than LLM output but guarantees continuity.

## 10) 5-Minute Demo Script
1. Open dashboard.
2. Upload sample CSV.
3. Show /api/stats changes in charts.
4. Run one analysis query with context_query.
5. Explain fallback behavior under quota limits.
6. Close with roadmap (tests, auth, observability).

## 11) Quick Q&A Prompts
Q: How do you reduce hallucinations?
A: Retrieval grounding, compact source context, and strict prompt framing.

Q: What if vector DB is down?
A: Local lexical fallback keeps system functional.

Q: How do you control cost?
A: Single-call mode, top-k limit, context caps, local fallback option.

Q: How do you switch LLM providers?
A: Change .env provider fields; agent wiring is already abstracted.

## 12) Resume-Style Bullets
- Built a production-style RAG + agentic analytics app using Python, FastAPI, LangChain, and Chart.js.
- Implemented multi-provider LLM architecture with environment-based switching and quota-safe fallback.
- Designed resilient retrieval pipeline with vector-store primary path and lexical fallback.
- Improved dashboard correctness by deriving visual metrics directly from latest uploaded CSV.

## 13) Last-Minute Checklist (Before Interview)
- Be ready to explain RAG vs fine-tuning.
- Be ready to explain why fallback modes matter in production.
- Know one concrete debugging incident end-to-end.
- Mention measurable improvements: reliability, continuity, lower token usage.
- Keep answers structured as Problem -> Action -> Result.
