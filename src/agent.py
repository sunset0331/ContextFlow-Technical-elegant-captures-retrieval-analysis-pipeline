"""Agentic AI using LangChain agents."""

from typing import Any, Dict, List, Optional
from langchain.agents import initialize_agent, AgentType
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from config import settings
from tools import AnalysisTools


class DataAnalysisAgent:
    """Autonomous agent for data analysis and insights."""
    
    def __init__(self, rag_pipeline):
        """
        Initialize the data analysis agent.
        
        Args:
            rag_pipeline: RAGPipeline instance for retrieving context
        """
        self.rag_pipeline = rag_pipeline
        self.tools_manager = AnalysisTools(rag_pipeline)
        self.llm = None
        self.agent = None
        self.memory = ConversationBufferMemory(memory_key="chat_history")
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the LangChain agent."""
        try:
            # Initialize selected LLM provider
            provider = settings.llm_provider.lower()
            if provider == "ollama":
                self.llm = ChatOllama(
                    model=settings.ollama_model,
                    base_url=settings.ollama_base_url,
                    temperature=settings.agent_temperature,
                )
            elif provider == "deepseek":
                self.llm = ChatOpenAI(
                    model=settings.model_name,
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url,
                    temperature=settings.agent_temperature,
                )
            else:
                self.llm = ChatGoogleGenerativeAI(
                    model=settings.model_name,
                    google_api_key=settings.google_api_key,
                    temperature=settings.agent_temperature,
                    verbose=settings.verbose
                )
            
            # Initialize agent with tools
            self.agent = initialize_agent(
                tools=self.tools_manager.get_tool_list(),
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                memory=self.memory,
                verbose=settings.verbose,
                max_iterations=settings.max_iterations,
                handle_parsing_errors=True,
                early_stopping_method="generate"
            )
            
            print("✓ Agent initialized successfully")
        except Exception as e:
            print(f"✗ Failed to initialize agent: {e}")
            raise

    def _is_quota_error(self, error_message: str) -> bool:
        """Detect provider quota/rate-limit errors from message text."""
        lowered = error_message.lower()
        return (
            "quota exceeded" in lowered
            or ("429" in lowered and ("gemini" in lowered or "deepseek" in lowered))
            or "rate limit" in lowered
        )

    def _mock_analysis(self, query: str, context_query: Optional[str] = None) -> str:
        """Provide deterministic local summary from retrieved context when provider quota is unavailable."""
        context = self.rag_pipeline.get_context(context_query or query)
        if context == "No relevant documents found.":
            return (
                "Quota fallback mode: no relevant context found for this query. "
                "Try a more specific context query (e.g., mrr, churn, cac, revenue)."
            )

        records: List[Dict[str, str]] = []
        current: Dict[str, str] = {}
        for raw_line in context.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("(Source:"):
                continue
            if line.startswith("["):
                if current:
                    records.append(current)
                    current = {}
                parts = line.split("]", 1)
                if len(parts) == 2 and ":" in parts[1]:
                    key, val = parts[1].split(":", 1)
                    current[key.strip()] = val.strip()
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                current[key.strip()] = val.strip()
        if current:
            records.append(current)

        def to_number(text: str) -> Optional[float]:
            cleaned = text.replace(",", "").replace("$", "").replace("%", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return None

        numeric_series: Dict[str, List[float]] = {}
        for rec in records:
            for key, val in rec.items():
                num = to_number(val)
                if num is not None:
                    numeric_series.setdefault(key, []).append(num)

        ranked_metrics: List[tuple[float, str, List[float]]] = []
        for key, vals in numeric_series.items():
            if len(vals) >= 2:
                ranked_metrics.append((abs(vals[-1] - vals[0]), key, vals))
        ranked_metrics.sort(key=lambda item: item[0], reverse=True)

        bullets: List[str] = []
        for _, key, vals in ranked_metrics[:2]:
            start = vals[0]
            end = vals[-1]
            delta = end - start
            direction = "increased" if delta >= 0 else "decreased"
            bullets.append(
                f"- {key}: {direction} from {start:.2f} to {end:.2f} (change {delta:+.2f}) across {len(vals)} records."
            )

        if not bullets:
            return (
                "Quota fallback mode: context was loaded, but no numeric fields were detected for trend summarization."
            )

        return (
            "Quota fallback mode (deterministic local summary based on retrieved context):\n"
            f"Query: {query}\n"
            + "\n".join(bullets)
            + "\n- Recommendation: Prioritize metrics with the largest absolute change and validate root causes with a deeper slice by region/channel."
        )
    
    def analyze(self, query: str, context_query: Optional[str] = None) -> str:
        """
        Run the analysis agent on a query.
        
        Args:
            query: Main analysis query
            context_query: Optional query to retrieve relevant context first
            
        Returns:
            Agent response and analysis
        """
        try:
            provider = settings.llm_provider.lower()
            if provider == "ollama" or settings.single_call_mode:
                context = ""
                if context_query:
                    context = self.rag_pipeline.get_context(context_query)
                prompt = (
                    "You are a concise data analyst.\n"
                    "Rules: Use only the provided context, keep numeric values exact, and do not invent facts.\n"
                    "Return exactly 2 bullet insights with numbers and one short recommendation.\n\n"
                    f"Context:\n{context or 'No external context provided.'}\n\n"
                    f"Question: {query}\n"
                )
                llm_response = self.llm.invoke(prompt)
                return getattr(llm_response, "content", str(llm_response))

            # Retrieve context if specified
            context = ""
            if context_query:
                context = self.rag_pipeline.get_context(context_query)
                enhanced_query = f"""
                Use this context to answer the following query:
                
                Context:
                {context}
                
                Query: {query}
                """
            else:
                enhanced_query = query
            
            # Run agent
            result = self.agent.run(enhanced_query)
            return result
        
        except Exception as e:
            error_message = str(e)
            if self._is_quota_error(error_message):
                if settings.enable_mock_on_quota_error:
                    return self._mock_analysis(query=query, context_query=context_query)
                return (
                    "Gemini API quota exceeded. Please enable billing/quota for your key and retry."
                )
            return f"Error during analysis: {error_message}"
    
    def multi_step_analysis(self, queries: List[str]) -> Dict[str, str]:
        """
        Perform multi-step analysis on multiple queries.
        
        Args:
            queries: List of analysis queries
            
        Returns:
            Dictionary mapping queries to results
        """
        results = {}
        for q in queries:
            results[q] = self.analyze(q)
        return results
    
    def get_conversation_history(self) -> str:
        """Get conversation history."""
        return self.memory.buffer
    
    def clear_memory(self):
        """Clear conversation memory."""
        self.memory.clear()
