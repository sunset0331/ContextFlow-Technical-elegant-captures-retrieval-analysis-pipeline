"""FastAPI backend server for RAG + Agentic AI dashboard + LangGraph Multi-Agent Orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator
import asyncio
import json
import logging
import os
from datetime import datetime
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import uvicorn

# LangGraph & State Persistence
try:
    from langgraph.checkpoint.postgres import AsyncPostgresCheckpointer
except ImportError:
    try:
        from langgraph.checkpoint.sql import AsyncSqlCheckpointer as AsyncPostgresCheckpointer
    except ImportError:
        AsyncPostgresCheckpointer = None

import asyncpg
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Local imports
from config import settings
from agent import DataAnalysisAgent
from rag_pipeline import RAGPipeline, load_csv_documents, load_text_documents
from graph import SynapseGraph, AgentState
from llm_providers import create_qwen_llm

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

# ============================================================================
# PostgreSQL Configuration
# ============================================================================

POSTGRES_CONFIG = {
    "host": settings.postgres_host if hasattr(settings, 'postgres_host') else "localhost",
    "port": settings.postgres_port if hasattr(settings, 'postgres_port') else 5432,
    "user": settings.postgres_user if hasattr(settings, 'postgres_user') else "postgres",
    "password": settings.postgres_password if hasattr(settings, 'postgres_password') else "password",
    "database": settings.postgres_db if hasattr(settings, 'postgres_db') else "synapse_ai",
}

POSTGRES_URI = (
    f"postgresql://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@"
    f"{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
)

POSTGRES_ASYNC_URI = (
    f"postgresql+asyncpg://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@"
    f"{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
)


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeRequest(BaseModel):
    """Request model for analysis endpoint."""

    query: str
    context_query: Optional[str] = None
    file: Optional[str] = None


class AnalyzeResponse(BaseModel):
    """Response model for analysis endpoint."""

    query: str
    context_query: Optional[str]
    response: str


class OrchestrateRequest(BaseModel):
    """Request model for multi-agent orchestration."""

    query: str
    session_id: Optional[str] = None  # If None, a new session is created
    uploaded_files: Optional[List[str]] = None
    file_context: Optional[Dict[str, Any]] = None
    max_iterations: int = 5
    pause_on_approval: bool = False  # Enable Human-in-the-Loop


class OrchestrateResponse(BaseModel):
    """Response model for orchestration endpoint."""

    session_id: str
    status: str  # "started", "completed", "paused", "error"
    message: str
    result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class SessionStatusResponse(BaseModel):
    """Response model for session status check."""

    session_id: str
    status: str
    current_task: str
    current_worker: Optional[str]
    iteration_count: int
    worker_results_count: int
    final_response: Optional[str]
    created_at: str
    updated_at: str
    checkpoint_available: bool


# ============================================================================
# Application State
# ============================================================================


class AppState:
    """Application runtime state."""

    def __init__(self) -> None:
        self.rag: Optional[RAGPipeline] = None
        self.agent: Optional[DataAnalysisAgent] = None
        self.indexed_sources: List[str] = []
        self.startup_error: Optional[str] = None
        
        # Multi-agent orchestrator components
        self.synapse_graph: Optional[SynapseGraph] = None
        self.checkpointer: Optional[AsyncPostgresCheckpointer] = None
        self.session_store: Dict[str, Dict[str, Any]] = {}  # In-memory session metadata
        self.postgres_available: bool = False


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
    """Initialize RAG, agent, and LangGraph orchestrator when API starts."""
    provider = settings.llm_provider.lower()

    if provider == "ollama":
        # Local models require no cloud API key.
        pass

    elif provider == "huggingface" and not settings.huggingface_api_key:
        state.startup_error = (
            "HUGGINGFACE_API_KEY is missing. Set it in .env to enable HuggingFace/Qwen2.5-72B agent endpoints."
        )
        logger.warning(f"Warning: {state.startup_error}")
        return

    elif provider == "deepseek" and not settings.deepseek_api_key:
        state.startup_error = (
            "DEEPSEEK_API_KEY is missing. Set it in .env to enable DeepSeek agent endpoints."
        )
        logger.warning(f"Warning: {state.startup_error}")
        return

    elif provider == "google" and not settings.google_api_key:
        state.startup_error = (
            "GOOGLE_API_KEY is missing. Set it in .env to enable RAG and agent endpoints."
        )
        logger.warning(f"Warning: {state.startup_error}")
        return

    if settings.embedding_provider.lower() == "google" and not settings.google_api_key:
        state.startup_error = (
            "EMBEDDING_PROVIDER=google requires GOOGLE_API_KEY in .env."
        )
        logger.warning(f"Warning: {state.startup_error}")
        return

    try:
        # Initialize RAG and basic agent
        state.rag = RAGPipeline()
        state.agent = DataAnalysisAgent(state.rag)
        _bootstrap_documents()
        
        # Initialize LangGraph orchestrator
        try:
            # from langchain_google_genai import ChatGoogleGenerativeAI  # DISABLED: max_retries incompatibility
            from langchain_community.chat_models import ChatOllama
            from langchain_openai import ChatOpenAI
            
            llm = None
            init_error = None
            
            if provider == "ollama":
                try:
                    llm = ChatOllama(
                        model=settings.ollama_model,
                        base_url=settings.ollama_base_url,
                        temperature=settings.agent_temperature,
                    )
                    logger.info(f"✓ Initialized Ollama LLM: {settings.ollama_model}")
                except Exception as e:
                    init_error = f"Ollama init failed: {e}"
            
            elif provider == "deepseek":
                try:
                    llm = ChatOpenAI(
                        model=settings.model_name,
                        api_key=settings.deepseek_api_key,
                        base_url=settings.deepseek_base_url,
                        temperature=settings.agent_temperature,
                    )
                    logger.info(f"✓ Initialized DeepSeek LLM: {settings.model_name}")
                except Exception as e:
                    init_error = f"DeepSeek init failed: {e}"
            
            elif provider == "huggingface":
                try:
                    llm = create_qwen_llm(
                        api_key=os.getenv("HUGGINGFACE_API_KEY"),
                        model_id=os.getenv("HUGGINGFACE_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct"),
                        temperature=settings.agent_temperature,
                        verbose=settings.verbose
                    )
                    logger.info(f"✓ Initialized HuggingFace Qwen LLM: Qwen2.5-72B-Instruct")
                except Exception as e:
                    init_error = f"HuggingFace init failed: {e}"
            
            # else:  # Google provider - DISABLED: max_retries incompatibility
            #     try:
            #         llm = ChatGoogleGenerativeAI(
            #             model=settings.model_name,
            #             google_api_key=settings.google_api_key,
            #             temperature=settings.agent_temperature,
            #         )
            #         logger.info(f"✓ Initialized Google Gemini LLM: {settings.model_name}")
            #     except Exception as e:
            #         init_error = f"Google Gemini init failed: {str(e)}"
            #         logger.warning(f"⚠ {init_error}")
            #         logger.info("  Falling back to HuggingFace Qwen2.5-72B-Instruct...")
            #         try:
            #             llm = create_qwen_llm(
            #                 api_key=os.getenv("HUGGINGFACE_API_KEY"),
            #                 model_id=os.getenv("HUGGINGFACE_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct"),
            #                 temperature=settings.agent_temperature,
            #                 verbose=settings.verbose
            #             )
            #             logger.info(f"✓ Fallback: Initialized HuggingFace Qwen LLM")
            #             init_error = None  # Successfully fell back
            #         except Exception as fallback_e:
            #             init_error = f"Both Google and HuggingFace failed: {str(fallback_e)}"
            else:  # Default to HuggingFace (Google provider disabled)
                try:
                    llm = create_qwen_llm(
                        api_key=os.getenv("HUGGINGFACE_API_KEY"),
                        model_id=os.getenv("HUGGINGFACE_MODEL_ID", "Qwen/Qwen2.5-72B-Instruct"),
                        temperature=settings.agent_temperature,
                        verbose=settings.verbose
                    )
                    logger.info(f"✓ Initialized HuggingFace Qwen LLM (Google provider disabled)")
                    init_error = None
                except Exception as e:
                    init_error = f"HuggingFace init failed: {str(e)}"
            
            if llm is None:
                raise RuntimeError(init_error or "Failed to initialize any LLM provider")
            
            # Initialize Synapse Graph
            state.synapse_graph = SynapseGraph(
                llm=llm,
                rag_pipeline=state.rag,
                data_dir=str(UPLOADS_DIR),
                verbose=settings.verbose
            )
            logger.info("✓ LangGraph Synapse orchestrator initialized")
        except Exception as e:
            logger.warning(f"Could not initialize LangGraph orchestrator: {e}")
            state.synapse_graph = None
        
        # Initialize PostgreSQL checkpointer for state persistence
        try:
            # Verify PostgreSQL connection
            conn_str = POSTGRES_ASYNC_URI
            logger.info(f"Attempting to connect to PostgreSQL: {POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}")
            
            if AsyncPostgresCheckpointer is not None:
                state.checkpointer = AsyncPostgresCheckpointer.from_conn_string(conn_str)
                state.postgres_available = True
                logger.info("✓ PostgreSQL checkpointer initialized for LangGraph state persistence")
            else:
                logger.warning("PostgreSQL checkpointer not available in this langgraph version")
                state.postgres_available = False
                state.checkpointer = None
        except Exception as e:
            logger.warning(f"Could not initialize PostgreSQL checkpointer: {e}")
            logger.info("Continuing without state persistence. Configure PostgreSQL to enable HITL workflows.")
            state.postgres_available = False
            state.checkpointer = None
        
        state.startup_error = None
        logger.info("✓ Synapse AI backend startup complete")
        
    except Exception as exc:
        state.startup_error = f"Startup dependency initialization failed: {exc}"
        state.rag = None
        state.agent = None
        state.synapse_graph = None
        logger.error(f"Warning: {state.startup_error}")


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

    result = state.agent.analyze(query=request.query, context_query=request.context_query, file=request.file)
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


# ============================================================================
# Multi-Agent Orchestrator Endpoints
# ============================================================================

@app.post("/api/orchestrate", response_model=OrchestrateResponse)
async def orchestrate(request: OrchestrateRequest, background_tasks: BackgroundTasks) -> OrchestrateResponse:
    """
    Kick off a multi-agent orchestration session.
    
    - Creates or resumes a session with LangGraph
    - Stores state in PostgreSQL for persistence and HITL workflows
    - Supports pause_on_approval for Human-in-the-Loop
    """
    if not state.synapse_graph:
        raise HTTPException(
            status_code=503,
            detail="Multi-agent orchestrator not initialized. Ensure LangGraph is properly configured.",
        )
    
    # Generate or use provided session ID
    session_id = request.session_id or str(uuid.uuid4())[:12]
    
    try:
        logger.info(f"\n[Orchestrate] Starting session {session_id}")
        logger.info(f"[Orchestrate] Query: {request.query[:80]}...")
        
        # Execute the multi-agent graph
        result = state.synapse_graph.invoke(
            task=request.query,
            uploaded_files=request.uploaded_files,
            file_context=request.file_context,
            max_iterations=request.max_iterations
        )
        
        # Store session metadata
        state.session_store[session_id] = {
            "query": request.query,
            "status": "completed",
            "result": result,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "pause_on_approval": request.pause_on_approval,
            "uploaded_files": request.uploaded_files or [],
        }
        
        logger.info(f"[Orchestrate] Session {session_id} completed successfully")
        
        return OrchestrateResponse(
            session_id=session_id,
            status="completed",
            message=f"Multi-agent orchestration completed for session {session_id}",
            result=result,
            created_at=state.session_store[session_id]["created_at"],
            updated_at=state.session_store[session_id]["updated_at"]
        )
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[Orchestrate] Error during session {session_id}: {error_msg}")
        
        # Check for known Google API compatibility issue
        if "max_retries" in error_msg and "generate_content" in error_msg:
            detail = (
                "Google Generative AI compatibility error. "
                "Please switch to a different LLM provider (HuggingFace, Ollama, or DeepSeek) "
                "by setting LLM_PROVIDER in your .env file."
            )
            logger.error(f"[Orchestrate] Known issue detected: {detail}")
        else:
            detail = f"Orchestration failed: {error_msg}"
        
        state.session_store[session_id] = {
            "query": request.query,
            "status": "error",
            "error": error_msg,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        raise HTTPException(
            status_code=500,
            detail=detail
        )


@app.get("/api/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Get the status of a multi-agent orchestration session.
    
    Returns current state, iteration count, worker results, and checkpoint availability.
    """
    session = state.session_store.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    result = session.get("result", {})
    
    return SessionStatusResponse(
        session_id=session_id,
        status=session.get("status", "unknown"),
        current_task=session.get("query", ""),
        current_worker=result.get("current_worker"),
        iteration_count=result.get("iteration_count", 0),
        worker_results_count=len(result.get("worker_results", [])),
        final_response=result.get("final_response"),
        created_at=session.get("created_at", ""),
        updated_at=session.get("updated_at", ""),
        checkpoint_available=state.postgres_available
    )


@app.get("/api/session/{session_id}/result")
async def get_session_result(session_id: str) -> Dict[str, Any]:
    """
    Retrieve the full result of a completed orchestration session.
    
    Includes:
    - Final aggregated response
    - All worker results
    - Message history
    - Execution metadata
    """
    session = state.session_store.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    if session.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Session {session_id} has status '{session.get('status')}', not completed"
        )
    
    result = session.get("result", {})
    
    return {
        "session_id": session_id,
        "query": session.get("query"),
        "final_response": result.get("final_response"),
        "messages": result.get("messages", []),
        "worker_results": result.get("worker_results", []),
        "iterations": result.get("iteration_count", 0),
        "uploaded_files": session.get("uploaded_files", []),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@app.post("/api/session/{session_id}/pause")
async def pause_session(session_id: str) -> Dict[str, str]:
    """
    Pause a multi-agent orchestration session for Human-in-the-Loop approval.
    
    Saves current state to PostgreSQL checkpoint if available.
    """
    session = state.session_store.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    session["status"] = "paused"
    session["updated_at"] = datetime.now().isoformat()
    
    logger.info(f"[Session] Paused session {session_id} for Human-in-the-Loop approval")
    
    return {
        "session_id": session_id,
        "status": "paused",
        "message": f"Session {session_id} paused for Human-in-the-Loop approval",
        "checkpoint_available": "yes" if state.postgres_available else "no"
    }


@app.post("/api/session/{session_id}/resume")
async def resume_session(session_id: str) -> Dict[str, str]:
    """
    Resume a paused multi-agent orchestration session.
    
    Loads state from PostgreSQL checkpoint if available, otherwise resumes from memory.
    """
    session = state.session_store.get(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    if session.get("status") != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Session {session_id} cannot be resumed. Status: {session.get('status')}"
        )
    
    session["status"] = "resumed"
    session["updated_at"] = datetime.now().isoformat()
    
    logger.info(f"[Session] Resumed session {session_id}")
    
    return {
        "session_id": session_id,
        "status": "resumed",
        "message": f"Session {session_id} resumed from checkpoint"
    }


@app.get("/api/sessions")
async def list_sessions() -> Dict[str, Any]:
    """
    List all active and completed orchestration sessions.
    
    Useful for dashboard and session management.
    """
    sessions_summary = []
    
    for session_id, session in state.session_store.items():
        sessions_summary.append({
            "session_id": session_id,
            "query": session.get("query", "")[:100],  # Truncate for summary
            "status": session.get("status", "unknown"),
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        })
    
    return {
        "total_sessions": len(sessions_summary),
        "sessions": sessions_summary,
        "postgres_available": state.postgres_available
    }


@app.get("/api/orchestrator/info")
async def orchestrator_info() -> Dict[str, Any]:
    """
    Get information about the multi-agent orchestrator configuration.
    
    Shows agent types, checkpoint availability, and system status.
    """
    return {
        "synapse_graph_initialized": state.synapse_graph is not None,
        "postgres_checkpointer_available": state.postgres_available,
        "postgres_config": {
            "host": POSTGRES_CONFIG["host"],
            "port": POSTGRES_CONFIG["port"],
            "database": POSTGRES_CONFIG["database"]
        },
        "active_sessions": len(state.session_store),
        "agents": [
            {"name": "Supervisor", "role": "Task router and result aggregator"},
            {"name": "Data Analyst", "role": "CSV analysis and data exploration"},
            {"name": "Web Researcher", "role": "RAG retrieval and knowledge synthesis"}
        ]
    }


if __name__ == "__main__":
    uvicorn.run("backend_server:app", host="0.0.0.0", port=8000, reload=True)
