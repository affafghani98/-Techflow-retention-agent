"""
RAG System - Vector store for policy documents retrieval
Uses HuggingFace sentence-transformers (free, local, no API key) so only Groq key is needed for chat.
"""
import os
import json
from typing import List, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class RAGSystem:
    """RAG system for retrieving relevant policy information"""
    
    def __init__(self, api_key: str = None):
        """Initialize RAG system with embeddings and vector store (api_key unused; uses free HuggingFace embeddings)"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.vector_store = None
        self._build_vector_store()
    
    def _build_vector_store(self):
        """Build FAISS vector store from policy documents"""
        # Get directory paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.join(current_dir, '..')
        
        # Policy documents to load (all provided documents)
        policy_files = [
            'return_policy.md',
            'care_plus_benefits.md',
            'troubleshooting_guide.md',
            'retention_playbook.md',
            'retention_rules.json'  # Business rules - convert JSON to readable text
        ]
        
        documents = []
        
        # Load each policy document
        for filename in policy_files:
            file_path = os.path.join(base_dir, filename)
            if os.path.exists(file_path):
                if filename.endswith('.json'):
                    # Handle JSON files - convert to readable text format
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Convert JSON to readable text format
                        content = self._json_to_text(data)
                    doc = Document(
                        page_content=content,
                        metadata={"source": filename, "type": "business_rules"}
                    )
                else:
                    # Handle markdown/text files
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    doc = Document(
                        page_content=content,
                        metadata={"source": filename, "type": "policy"}
                    )
                documents.append(doc)
        
        if not documents:
            raise ValueError("No policy documents found!")
        
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        chunks = text_splitter.split_documents(documents)
        
        # Create FAISS vector store
        self.vector_store = FAISS.from_documents(chunks, self.embeddings)
    
    def _json_to_text(self, data: dict) -> str:
        """Convert retention_rules.json to readable text format for RAG"""
        text_parts = []
        
        # Authorization levels section
        if "authorization_levels" in data:
            auth = data["authorization_levels"]
            text_parts.append("AUTHORIZATION LEVELS:")
            if "agent" in auth:
                agent = auth["agent"]
                text_parts.append(f"\nAGENT CAN:")
                text_parts.append(f"- Maximum discount: {agent.get('max_discount_percentage', 25)}%")
                text_parts.append(f"- Can pause subscriptions: {agent.get('can_pause', False)}")
                text_parts.append(f"- Can downgrade plans: {agent.get('can_downgrade', False)}")
            if "manager" in auth:
                manager = auth["manager"]
                text_parts.append(f"\nMANAGER CAN:")
                text_parts.append(f"- Maximum discount: {manager.get('max_discount_percentage', 50)}%")
                text_parts.append(f"- Can create custom offers: {manager.get('can_custom_offers', False)}")
            text_parts.append("\n")
        
        # Financial hardship offers
        if "financial_hardship" in data:
            text_parts.append("FINANCIAL HARDSHIP OFFERS:")
            fh = data["financial_hardship"]
            for tier, offers in fh.items():
                if isinstance(offers, list):
                    text_parts.append(f"\n{tier.replace('_', ' ').title()}:")
                    for offer in offers:
                        auth_level = offer.get("authorization", "agent")
                        text_parts.append(f"- {offer.get('description', '')} (Authorization: {auth_level})")
                        if "percentage" in offer:
                            text_parts.append(f"  Discount: {offer['percentage']}%")
                        if "new_cost" in offer:
                            text_parts.append(f"  New cost: ${offer['new_cost']}")
                        if "duration_months" in offer:
                            text_parts.append(f"  Duration: {offer['duration_months']} months")
            text_parts.append("\n")
        
        # Product issues offers
        if "product_issues" in data:
            text_parts.append("PRODUCT ISSUES OFFERS:")
            pi = data["product_issues"]
            for issue_type, offers in pi.items():
                if isinstance(offers, list):
                    text_parts.append(f"\n{issue_type.replace('_', ' ').title()}:")
                    for offer in offers:
                        auth_level = offer.get("authorization", "agent")
                        text_parts.append(f"- {offer.get('description', '')} (Authorization: {auth_level})")
            text_parts.append("\n")
        
        # Service value offers
        if "service_value" in data:
            text_parts.append("SERVICE VALUE OFFERS:")
            sv = data["service_value"]
            for plan_type, offers in sv.items():
                if isinstance(offers, list):
                    text_parts.append(f"\n{plan_type.replace('_', ' ').title()}:")
                    for offer in offers:
                        if offer.get("type") == "explain_benefits":
                            text_parts.append(f"- Benefits: {', '.join(offer.get('benefits', []))}")
                        else:
                            auth_level = offer.get("authorization", "agent")
                            text_parts.append(f"- {offer.get('description', '')} (Authorization: {auth_level})")
            text_parts.append("\n")
        
        return "\n".join(text_parts)
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """Search for relevant policy information
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of relevant document chunks with metadata
        """
        if not self.vector_store:
            return []
        
        # Perform similarity search
        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "score": float(score)
            })
        
        return formatted_results
    
    def get_relevant_context(self, query: str, k: int = 5) -> str:
        """Get relevant context as formatted string for agent prompts
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            Formatted string with relevant policy information
        """
        results = self.search(query, k)
        
        if not results:
            return "No relevant policy information found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Source: {result['source']}]\n{result['content']}\n"
            )
        
        return "\n---\n".join(context_parts)
