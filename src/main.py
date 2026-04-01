"""Main application for RAG + Agentic AI system."""

import os
from pathlib import Path
from rag_pipeline import RAGPipeline, load_text_documents
from agent import DataAnalysisAgent


def main():
    """Run the RAG + Agentic AI application."""
    
    print("=" * 60)
    print("RAG + AGENTIC AI - Data Analysis System")
    print("=" * 60)
    
    # Initialize RAG pipeline
    print("\n[1] Initializing RAG Pipeline...")
    rag = RAGPipeline()
    
    # Load sample documents
    print("\n[2] Loading Documents...")
    data_dir = Path(__file__).parent.parent / "data"
    
    if not data_dir.exists():
        data_dir.mkdir(exist_ok=True)
    
    # Create sample data if it doesn't exist
    sample_file = data_dir / "sample_data.txt"
    if not sample_file.exists():
        sample_content = """
        Company Performance Report 2024
        
        Sales Performance:
        - Q1 Revenue: $2.5M (↑ 15% YoY)
        - Q2 Revenue: $2.8M (↑ 12% YoY)
        - Q3 Revenue: $3.1M (↑ 10% YoY)
        
        Customer Metrics:
        - Total Customers: 5,000
        - Customer Retention Rate: 92%
        - Net Promoter Score: 65
        - Customer Acquisition Cost: $500
        
        Product Performance:
        - Product A: 45% of revenue
        - Product B: 35% of revenue
        - Product C: 20% of revenue
        
        Market Analysis:
        - Market Size: $10B
        - Company Market Share: 3%
        - Competitors: 5 major players
        - Growth Trend: Steady expansion into new segments
        
        Team and Operations:
        - Employees: 150
        - Employee Satisfaction: 8.2/10
        - Project Delivery: 98% on-time
        - System Uptime: 99.9%
        """
        with open(sample_file, 'w') as f:
            f.write(sample_content)
        print(f"✓ Created sample data at {sample_file}")
    
    # Load documents
    try:
        documents = load_text_documents(str(sample_file))
        rag.ingest_documents(documents)
        print(f"✓ Ingested {len(documents)} documents")
    except Exception as e:
        print(f"✗ Error loading documents: {e}")
        return
    
    # Initialize agent
    print("\n[3] Initializing Data Analysis Agent...")
    agent = DataAnalysisAgent(rag)
    
    # Run example analyses
    print("\n[4] Running Analysis Queries...")
    print("-" * 60)
    
    queries = [
        "What are the key sales trends and what insights can you provide?",
        "Based on customer metrics, what recommendations would you make?",
        "How is our product portfolio performing and what's the outlook?"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\nQuery {i}: {query}")
        print("-" * 40)
        try:
            response = agent.analyze(query, context_query="company performance metrics")
            print(f"Response:\n{response}\n")
        except Exception as e:
            print(f"Error: {e}\n")
    
    # Interactive mode
    print("\n" + "=" * 60)
    print("Interactive Analysis Mode")
    print("=" * 60)
    print("Enter your analysis queries below. Type 'quit' to exit.\n")
    
    while True:
        user_query = input("Your Query: ").strip()
        
        if user_query.lower() in ['quit', 'exit', 'q']:
            print("Exiting... Thank you!")
            break
        
        if not user_query:
            print("Please enter a valid query.\n")
            continue
        
        print("\nAnalyzing...")
        try:
            response = agent.analyze(user_query)
            print(f"\nResponse:\n{response}\n")
        except Exception as e:
            print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
