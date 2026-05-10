"""Agentic AI using LangChain agents."""

from typing import Any, Dict, List, Optional
from langchain.agents import initialize_agent, AgentType
# from langchain_google_genai import ChatGoogleGenerativeAI  # DISABLED: max_retries incompatibility
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from config import settings
from tools import AnalysisTools
import os


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
            elif provider == "huggingface":
                # Use HuggingFace Qwen2.5-72B-Instruct for superior quality
                from llm_providers import create_qwen_llm
                self.llm = create_qwen_llm(
                    api_key=settings.huggingface_api_key,
                    model_id=settings.huggingface_model_id,
                    temperature=settings.agent_temperature,
                    verbose=settings.verbose,
                )
            else:  # Default to HuggingFace
                from llm_providers import create_qwen_llm
                self.llm = create_qwen_llm(
                    api_key=settings.huggingface_api_key,
                    model_id=settings.huggingface_model_id,
                    temperature=settings.agent_temperature,
                    verbose=settings.verbose,
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
    
    def analyze(self, query: str, context_query: Optional[str] = None, file: Optional[str] = None) -> str:
        """
        Run the analysis agent on a query.
        
        Args:
            query: Main analysis query
            context_query: Optional query to retrieve relevant context first
            file: Optional CSV file name to include in context
            
        Returns:
            Agent response and analysis
        """
        try:
            provider = settings.llm_provider.lower()
            # Use direct LLM call for ollama, huggingface, and single_call_mode
            if provider in ["ollama", "huggingface"] or settings.single_call_mode:
                context = ""
                if context_query:
                    context = self.rag_pipeline.get_context(context_query)
                
                # Add file context if specified
                file_context = ""
                if file:
                    file_path = f"../data/uploads/{file}"
                    try:
                        import pandas as pd
                        df = pd.read_csv(file_path)
                        file_context = f"📊 **Analyzing file: {file}**\n"
                        file_context += f"- Total rows: {len(df)}\n"
                        file_context += f"- Columns: {', '.join(df.columns.tolist())}\n"
                        
                        # Extract unique values for categorical columns
                        categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
                        for col in categorical_cols:
                            unique_vals = df[col].nunique()
                            if unique_vals <= 20:  # Only show for reasonable cardinality
                                vals = df[col].unique().tolist()
                                file_context += f"- Unique {col}: {unique_vals} ({', '.join(map(str, vals[:10]))}{'...' if len(vals) > 10 else ''})\n"
                        
                        # For specific questions, explicitly extract key columns
                        key_columns = ['region', 'product', 'channel', 'sales_rep', 'deal_size_category']
                        for col in key_columns:
                            if col in df.columns:
                                count = df[col].nunique()
                                vals = df[col].unique().tolist()
                                file_context += f"- {col.title()} count: {count} (unique: {', '.join(map(str, vals))})\n"
                        
                        file_context += f"\n"
                    except Exception as e:
                        file_context = f"⚠️ Could not load file {file}: {str(e)}\n"
                
                prompt = (
                    "You are a precise data analyst. CRITICAL INSTRUCTIONS:\n"
                    "1. The data context is ALWAYS provided above\n"
                    "2. ALWAYS look for the answer in the DATA CONTEXT provided\n"
                    "3. Extract EXACT numbers and values from the context\n"
                    "4. Never say 'data does not provide' if the information is in the context above\n"
                    "5. Answer the user question directly using only the data context\n\n"
                    f"DATA CONTEXT:\n{file_context}\n"
                    f"Additional Context:\n{context or 'None provided.'}\n\n"
                    f"USER QUESTION: {query}\n\n"
                    "ANSWER (use exact information from the data context above):"
                )
                # DEBUG: Log the prompt being sent
                print(f"DEBUG: file={file}, context_length={len(file_context)}")
                print(f"DEBUG: Prompt length: {len(prompt)}")
                print(f"DEBUG: First 200 chars of file_context: {file_context[:200]}")
                
                llm_response = self.llm.invoke(prompt)
                response_text = getattr(llm_response, "content", str(llm_response))
                print(f"DEBUG: Response length: {len(response_text)}")
                return response_text

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
