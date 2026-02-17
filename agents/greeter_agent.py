"""
Agent 1: Greeter & Orchestrator
- Identifies customer
- Classifies intent (cancellation vs tech support vs billing)
- Routes to appropriate agent
"""
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import sys
import os
import re
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.customer_tools import get_customer_data


class GreeterAgent:
    """Greeter agent that identifies customers and routes them"""

    def __init__(self, api_key: str, rag_system):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            temperature=0.3,
        )
        self.rag_system = rag_system

    def process(self, customer_message: str, customer_email: str = None) -> Dict[str, Any]:
        """Process customer message and classify intent."""
        if not customer_email:
            emails = re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", customer_message)
            if emails:
                customer_email = emails[0]

        customer_data = None
        if customer_email:
            customer_result = get_customer_data.invoke({"email": customer_email})
            if customer_result.get("success"):
                customer_data = customer_result["customer"]

        context = self.rag_system.get_relevant_context(
            f"Customer says: {customer_message}. What type of support do they need?", k=2
        )

        customer_info_str = ""
        if customer_data:
            customer_info_str = f"Customer Info: {customer_data.get('name', 'Unknown')}, Tier: {customer_data.get('tier', 'unknown')}"

        full_prompt = f"""You are a customer service greeter for TechFlow Electronics. Classify customer intent based on these rules:

INTENT CLASSIFICATION RULES:
1. "cancellation" - Customer wants to cancel Care+ service OR change payment terms. Includes:
   - "can't afford", "can't pay", "too expensive", "need to cancel", "want to cancel"
   - Financial hardship mentions
   - Requests for discounts/pauses due to affordability
   - "get rid of", "remove", "cancel my subscription"
   - "custom billing arrangements", "payment plan", "special payment terms", "flexible payment"
   - Any request to change how/when they pay due to financial reasons

2. "technical_support" - Technical issues WITHOUT cancellation intent:
   - Phone problems (overheating, charging, won't work)
   - Device issues
   - NO mention of cancellation or payment changes

3. "billing" - Questions about charges/statements WITHOUT cancellation intent:
   - "got charged X but thought Y", "what's the extra charge"
   - Questions about billing statements, charges, fees
   - NO mention of affordability, cancellation, or wanting to change payment terms

4. "general" - Everything else (greetings, unclear)

Customer Message: {customer_message}

{customer_info_str}

Relevant Policy Context:
{context}

Classify intent. Respond in JSON:
{{
    "intent": "cancellation|technical_support|billing|general",
    "confidence": "high|medium|low",
    "customer_email": "{customer_email or 'not_provided'}",
    "customer_data": {customer_data is not None},
    "reasoning": "brief explanation",
    "next_agent": "retention|technical_support|billing|none"
}}"""

        response = self.llm.invoke(full_prompt)
        response_text = response.content

        # Try to extract JSON - handle nested braces
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
                # Validate required fields exist
                if "intent" not in result or "next_agent" not in result:
                    result = self._parse_fallback(customer_message, customer_email, customer_data)
            except Exception:
                result = self._parse_fallback(customer_message, customer_email, customer_data)
        else:
            result = self._parse_fallback(customer_message, customer_email, customer_data)

        return {
            "agent": "greeter",
            "intent": result.get("intent", "general"),
            "customer_email": result.get("customer_email") or customer_email,
            "customer_data": customer_data,
            "next_agent": result.get("next_agent", "none"),
            "reasoning": result.get("reasoning", response_text),
            "raw_response": response_text,
        }

    def _parse_fallback(self, text: str, email: str, customer_data: dict) -> dict:
        text_lower = text.lower()
        intent = "general"
        
        # Check for cancellation FIRST (includes financial hardship and payment term changes)
        if any(phrase in text_lower for phrase in [
            "cancel", "cancellation", "can't afford", "can't pay", 
            "too expensive", "get rid of", "get rid", "remove", "discount",
            "custom billing", "billing arrangements", "payment plan", 
            "special payment", "flexible payment", "change payment"
        ]):
            intent = "cancellation"
        # Technical support (only if NO cancellation mentioned)
        elif any(word in text_lower for word in ["overheat", "charging", "won't charge", "phone won't", "not working", "technical", "troubleshoot"]) and "cancel" not in text_lower:
            intent = "technical_support"
        # Billing (only if NO cancellation/affordability/payment changes mentioned)
        # Check for billing phrases more thoroughly
        elif any(phrase in text_lower for phrase in [
            "got charged", "charged", "what's the extra", "what is the extra", 
            "billing", "statement", "bill", "unexpected charge"
        ]) and "can't afford" not in text_lower and "cancel" not in text_lower and "custom" not in text_lower and "arrangements" not in text_lower and "get rid" not in text_lower:
            intent = "billing"
        
        next_agent = "none"
        if intent == "cancellation":
            next_agent = "retention"
        elif intent == "technical_support":
            next_agent = "technical_support"
        elif intent == "billing":
            next_agent = "billing"
        return {"intent": intent, "customer_email": email or "not_provided", "next_agent": next_agent, "reasoning": text[:200]}
