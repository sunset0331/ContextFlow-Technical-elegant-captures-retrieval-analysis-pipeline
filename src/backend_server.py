"""FastAPI backend server for RAG + Agentic AI dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import uvicorn

from config import settings
from agent import DataAnalysisAgent
from rag_pipeline import RAGPipeline, load_csv_documents, load_text_documents

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"


class AnalyzeRequest(BaseModel):
    """Request model for analysis endpoint."""

    query: str
    context_query: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Response model for analysis endpoint."""

    query: str
    context_query: Optional[str]
    response: str


class AppState:
    """Application runtime state."""

    def __init__(self) -> None:
        self.rag: Optional[RAGPipeline] = None
        self.agent: Optional[DataAnalysisAgent] = None
        self.indexed_sources: List[str] = []
        self.startup_error: Optional[str] = None


state = AppState()
app = FastAPI(title="RAG Agent Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_stats() -> Dict[str, Any]:
    """Build dashboard-ready stats from uploaded CSVs or sample text fallback."""
    csv_candidates = sorted(
        UPLOADS_DIR.glob("*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for csv_path in csv_candidates:
        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                continue

            # Prefer MRR-style column, then generic revenue column.
            revenue_col = None
            for candidate in ["mrr_usd", "revenue", "revenue_usd"]:
                if candidate in df.columns:
                    revenue_col = candidate
                    break

            if revenue_col is None:
                continue

            if "month" in df.columns:
                month_order = pd.unique(df["month"].astype(str))
                month_series = pd.Categorical(df["month"].astype(str), categories=month_order, ordered=True)
                grouped = (
                    df.assign(month=month_series)
                    .groupby("month", as_index=False, sort=False)[revenue_col]
                    .sum()
                )
                labels = grouped["month"].astype(str).tolist()
                revenue_values = grouped[revenue_col].astype(float).tolist()
            else:
                labels = [f"R{i+1}" for i in range(len(df))]
                revenue_values = df[revenue_col].astype(float).tolist()

            # Convert to millions for chart scale consistency.
            revenue_millions = [round(v / 1_000_000, 3) for v in revenue_values]

            share_dimension = None
            for candidate in ["region", "channel", "product", "category", "segment"]:
                if candidate in df.columns:
                    share_dimension = candidate
                    break

            if share_dimension is None:
                # Fall back to the first non-time textual column for meaningful pie charts.
                excluded = {"month", revenue_col}
                for col in df.columns:
                    if col in excluded:
                        continue
                    if df[col].dtype == "object":
                        share_dimension = col
                        break

            if share_dimension:
                share_series = (
                    df.groupby(share_dimension, as_index=False)[revenue_col]
                    .sum()
                    .sort_values(revenue_col, ascending=False)
                )
                total = float(share_series[revenue_col].sum()) or 1.0
                product_share = {
                    str(row[share_dimension]): int(round((float(row[revenue_col]) / total) * 100))
                    for _, row in share_series.head(6).iterrows()
                }
            else:
                product_share = {"Total": 100}

            return {
                "revenue_millions": revenue_millions[:12],
                "revenue_labels": labels[:12],
                "product_share": product_share,
                "total_sources": len(state.indexed_sources),
            }
        except Exception as exc:
            print(f"Warning: could not build stats from {csv_path.name}: {exc}")

    sample_file = DATA_DIR / "sample_data.txt"
    revenue = [2.5, 2.8, 3.1]
    product_share = {"Product A": 45, "Product B": 35, "Product C": 20}

    if sample_file.exists():
        text = sample_file.read_text()
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- Q1 Revenue:"):
                revenue[0] = float(line.split("$")[1].split("M")[0])
            if line.startswith("- Q2 Revenue:"):
                revenue[1] = float(line.split("$")[1].split("M")[0])
            if line.startswith("- Q3 Revenue:"):
                revenue[2] = float(line.split("$")[1].split("M")[0])
            if line.startswith("- Product A:"):
                product_share["Product A"] = int(line.split(":")[1].split("%")[0].strip())
            if line.startswith("- Product B:"):
                product_share["Product B"] = int(line.split(":")[1].split("%")[0].strip())
            if line.startswith("- Product C:"):
                product_share["Product C"] = int(line.split(":")[1].split("%")[0].strip())

    return {
        "revenue_millions": revenue,
        "revenue_labels": ["Q1", "Q2", "Q3"],
        "product_share": product_share,
        "total_sources": len(state.indexed_sources),
    }


def _ingest_file(path: Path) -> int:
    """Ingest a single file and return number of loaded documents."""
    if path.suffix.lower() == ".csv":
        docs = load_csv_documents(str(path))
    else:
        docs = load_text_documents(str(path))

    state.rag.ingest_documents(docs)
    source = str(path)
    if source not in state.indexed_sources:
        state.indexed_sources.append(source)
    return len(docs)


def _bootstrap_documents() -> None:
    """Load initial text/csv files from data directory."""
    DATA_DIR.mkdir(exist_ok=True)
    UPLOADS_DIR.mkdir(exist_ok=True)

    for path in DATA_DIR.glob("*.*"):
        if path.suffix.lower() in {".txt", ".csv"}:
            try:
                _ingest_file(path)
            except Exception as exc:
                print(f"Warning: failed to ingest {path.name}: {exc}")


@app.on_event("startup")
def startup_event() -> None:
    """Initialize RAG and agent when API starts."""
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        # Local models require no cloud API key.
        pass

    elif provider == "deepseek" and not settings.deepseek_api_key:
        state.startup_error = (
            "DEEPSEEK_API_KEY is missing. Set it in .env to enable DeepSeek agent endpoints."
        )
        print(f"Warning: {state.startup_error}")
        return

    elif provider == "google" and not settings.google_api_key:
        state.startup_error = (
            "GOOGLE_API_KEY is missing. Set it in .env to enable RAG and agent endpoints."
        )
        print(f"Warning: {state.startup_error}")
        return

    if settings.embedding_provider.lower() == "google" and not settings.google_api_key:
        state.startup_error = (
            "EMBEDDING_PROVIDER=google requires GOOGLE_API_KEY in .env."
        )
        print(f"Warning: {state.startup_error}")
        return

    try:
        state.rag = RAGPipeline()
        state.agent = DataAnalysisAgent(state.rag)
        _bootstrap_documents()
        state.startup_error = None
    except Exception as exc:
        state.startup_error = f"Startup dependency initialization failed: {exc}"
        state.rag = None
        state.agent = None
        print(f"Warning: {state.startup_error}")


@app.get("/health")
def health() -> Dict[str, Any]:
    """Liveness endpoint."""
    return {
        "status": "ok",
        "indexed_sources": state.indexed_sources,
        "rag_enabled": state.rag is not None,
        "agent_enabled": state.agent is not None,
        "startup_error": state.startup_error,
    }


@app.get("/api/stats")
def stats() -> Dict[str, Any]:
    """Provide chart-friendly summary metrics for dashboard."""
    return _extract_stats()


@app.get("/api/context")
def context(query: str) -> Dict[str, str]:
    """Retrieve context from vector store."""
    if not state.rag:
        raise HTTPException(
            status_code=503,
            detail=state.startup_error or "RAG pipeline not initialized",
        )
    return {"query": query, "context": state.rag.get_context(query)}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Run agent-based analysis for a query."""
    if not state.agent:
        raise HTTPException(
            status_code=503,
            detail=state.startup_error or "Agent not initialized",
        )

    result = state.agent.analyze(query=request.query, context_query=request.context_query)
    return AnalyzeResponse(
        query=request.query,
        context_query=request.context_query,
        response=result,
    )


@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload and ingest a text/csv document into RAG."""
    if not state.rag:
        raise HTTPException(
            status_code=503,
            detail=state.startup_error or "RAG pipeline not initialized",
        )

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".txt", ".csv"}:
        raise HTTPException(status_code=400, detail="Only .txt and .csv files are supported")

    UPLOADS_DIR.mkdir(exist_ok=True)
    target = UPLOADS_DIR / file.filename
    content = await file.read()
    target.write_bytes(content)

    try:
        loaded_docs = _ingest_file(target)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    return {
        "message": "File ingested",
        "file": str(target),
        "loaded_documents": loaded_docs,
        "indexed_sources": state.indexed_sources,
    }


if __name__ == "__main__":
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8000, reload=True)
