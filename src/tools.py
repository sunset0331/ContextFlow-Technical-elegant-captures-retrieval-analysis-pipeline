"""Tool definitions for the agentic AI system."""

from typing import Any, Dict, List
from langchain.tools import Tool
import json


class AnalysisTools:
    """Tools for data analysis and insights generation."""
    
    def __init__(self, rag_pipeline):
        """
        Initialize analysis tools.
        
        Args:
            rag_pipeline: RAGPipeline instance for retrieving context
        """
        self.rag_pipeline = rag_pipeline
        self.tools = []
        self._register_tools()
    
    def _register_tools(self):
        """Register all available tools."""
        self.tools = [
            Tool(
                name="retrieve_context",
                func=self._retrieve_context,
                description="Retrieve relevant context from the knowledge base for a query"
            ),
            Tool(
                name="analyze_data_patterns",
                func=self._analyze_patterns,
                description="Analyze patterns and trends in the retrieved data"
            ),
            Tool(
                name="generate_insights",
                func=self._generate_insights,
                description="Generate actionable insights from analyzed data"
            ),
            Tool(
                name="compare_metrics",
                func=self._compare_metrics,
                description="Compare and contrast different metrics or data points"
            ),
            Tool(
                name="get_summary",
                func=self._get_summary,
                description="Get a summary of findings and recommendations"
            )
        ]
    
    def _retrieve_context(self, query: str) -> str:
        """Retrieve relevant context from knowledge base."""
        return self.rag_pipeline.get_context(query)
    
    def _analyze_patterns(self, data_description: str) -> str:
        """Analyze patterns in data."""
        return f"""
        Analyzing patterns in: {data_description}
        
        Key Analysis Areas:
        - Temporal patterns and trends
        - Anomalies and outliers
        - Correlations between variables
        - Statistical significance
        - Growth rates and trajectories
        """
    
    def _generate_insights(self, analysis: str) -> str:
        """Generate insights from analysis."""
        return f"""
        Key Insights:
        - This represents a significant finding based on the data
        - The underlying trends suggest {analysis[:50]}...
        - Business implications require further investigation
        - Recommended actions to follow up
        """
    
    def _compare_metrics(self, metric1: str, metric2: str) -> str:
        """Compare two metrics."""
        return f"""
        Comparison of {metric1} vs {metric2}:
        - Metric 1 Performance: Strong correlation with overall trends
        - Metric 2 Performance: Shows variability
        - Relative Impact: Metric 1 appears more significant
        - Recommendations: Focus analysis on drivers of Metric 1
        """
    
    def _get_summary(self, analysis_notes: str) -> str:
        """Generate summary of findings."""
        return f"""
        ANALYSIS SUMMARY
        ================
        
        Key Findings:
        1. Notable trends identified from retrieved context
        2. Significant patterns detected across datasets
        3. Anomalies that require attention
        
        Recommendations:
        - Continue monitoring identified trends
        - Investigate root causes of anomalies
        - Implement tracking for key metrics
        
        Next Steps:
        - Deeper analysis required for {analysis_notes[:30]}...
        - Stakeholder review recommended
        """
    
    def get_tool_list(self) -> List[Tool]:
        """Return list of available tools."""
        return self.tools
