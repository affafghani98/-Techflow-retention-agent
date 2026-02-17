"""
Agent 2: Problem Solver & Retention Specialist
- Tries to retain customers who want to cancel
- Offers solutions (discounts, pauses, replacements)
- Uses retention_playbook.md scripts
"""
from typing import Dict, Any, List
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
import sys
import os
import json
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.customer_tools import get_customer_data, calculate_retention_offer, update_customer_status


class RetentionAgent:
    """Retention specialist agent"""

    def __init__(self, api_key: str, rag_system):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            temperature=0.7,
        )
        self.rag_system = rag_system
        self._load_playbook()

    def _load_playbook(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        playbook_path = os.path.join(current_dir, "..", "retention_playbook.md")
        try:
            with open(playbook_path, "r", encoding="utf-8") as f:
                self.playbook = f.read()
        except Exception:
            self.playbook = "Use empathy and problem-solving approach."

    def process(
        self,
        customer_message: str,
        customer_email: str,
        customer_data: dict,
        conversation_history: List[str] = None,
    ) -> Dict[str, Any]:
        reason = self._classify_reason(customer_message, customer_data)
        customer_tier = customer_data.get("tier", "regular")

        # Get all offers
        offers_result = calculate_retention_offer.invoke(
            {"customer_tier": customer_tier, "reason": reason}
        )

        # Load authorization levels from retention_rules.json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rules_path = os.path.join(current_dir, "..", "retention_rules.json")
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = json.load(f)
        agent_limits = rules.get("authorization_levels", {}).get("agent", {})
        max_agent_discount = agent_limits.get("max_discount_percentage", 25)

        # FILTER: Only show agent-level offers (not manager-required)
        agent_offers = []
        manager_required_offers = []
        if offers_result.get("success"):
            all_offers = offers_result.get("offers", [])
            for offer in all_offers:
                # Check authorization level
                if offer.get("authorization") == "agent":
                    agent_offers.append(offer)
                elif offer.get("authorization") == "manager":
                    manager_required_offers.append(offer)
                # Also include offers without authorization field (like explain_benefits)
                elif "authorization" not in offer:
                    agent_offers.append(offer)
        
        # Check if customer is asking for discount > agent limit
        message_lower = customer_message.lower()
        discount_request = None
        discount_warning = None
        requested_discount = None
        if "discount" in message_lower or "%" in message_lower:
            # Match "30%" or "30 %" (with or without space)
            discount_match = re.search(r"(\d+)\s*%", customer_message)
            if discount_match:
                requested_discount = int(discount_match.group(1))
                if requested_discount > max_agent_discount:
                    discount_request = f"⚠️ CUSTOMER REQUESTED {requested_discount}% DISCOUNT - AGENT LIMIT IS {max_agent_discount}% - REQUIRES MANAGER APPROVAL"
                    # Build warning message outside f-string to avoid backslash issues
                    discount_warning = (
                        f"⚠️ CRITICAL: {discount_request}\n\n"
                        f"You MUST acknowledge this request FIRST before offering alternatives. "
                        f'Say: "I understand you are looking for a {requested_discount}% discount. '
                        f'I can offer up to {max_agent_discount}% discount as an agent. '
                        f'For higher discounts like {requested_discount}%, I will need to escalate to a manager '
                        f'who can review your account. However, I can offer you these options right now..."\n\n'
                    )

        # Get scenario-specific playbook script
        playbook_script = self._get_playbook_script(reason, customer_data)

        # Query RAG for customer's specific request to find authorization rules and available solutions
        # First, query for the specific customer request
        customer_request_query = f"{customer_message} authorization requirements manager approval agent limits"
        customer_request_context = self.rag_system.get_relevant_context(customer_request_query, k=5)
        
        # Also get general context based on reason
        if reason == "financial_hardship":
            rag_query = "payment pause, discount offers, downgrade options, refund procedures, financial hardship solutions"
        elif reason == "product_issues":
            rag_query = "device replacement, return policy, warranty coverage, overheating issues, product problems"
        elif reason == "service_value":
            rag_query = "Care+ benefits, insurance value, coverage details, what's included, service value"
        else:
            rag_query = f"{customer_message} cancellation solutions offers"

        general_context = self.rag_system.get_relevant_context(rag_query, k=5)
        
        # Combine both contexts
        context = f"CUSTOMER REQUEST ANALYSIS:\n{customer_request_context}\n\nGENERAL POLICY CONTEXT:\n{general_context}"

        history_text = ""
        if conversation_history:
            history_text = "\n".join([f"Customer: {msg}" for msg in conversation_history[-3:]])
        recent_conv = f"Recent Conversation:\n{history_text}\n" if history_text else ""

        # Build system prompt with proper playbook integration
        system_prompt = f"""You are a customer retention specialist for TechFlow Electronics.
Your goal is to genuinely help customers solve their problems, not just prevent cancellations.

CUSTOMER PROFILE:
- Name: {customer_data.get('name', 'Unknown')}
- Tier: {customer_tier}
- Plan: {customer_data.get('plan_type', 'Unknown')}
- Monthly Charge: ${customer_data.get('monthly_charge', 0)}
- Tenure: {customer_data.get('tenure_months', 0)} months

CANCELLATION REASON: {reason.upper().replace('_', ' ')}

SCENARIO-SPECIFIC PLAYBOOK SCRIPT:
{playbook_script}

AGENT AUTHORIZATION LIMITS (from retention_rules.json):
- Maximum discount you can offer: {max_agent_discount}%
- Can pause subscriptions: {agent_limits.get('can_pause', False)}
- Can downgrade plans: {agent_limits.get('can_downgrade', False)}

{discount_warning if discount_warning else ''}

AGENT-APPROVED OFFERS (You can offer these without manager approval):
{self._format_offers(agent_offers) if agent_offers else 'No agent-level offers available.'}

COMPANY POLICY CONTEXT (from policy documents):
{context}

CRITICAL RULES (from retention_playbook.md and retention_rules.json):
1. CHECK THE "CUSTOMER REQUEST ANALYSIS" SECTION ABOVE - it contains authorization requirements from retention_playbook.md
2. If the customer request (like "custom billing arrangements") requires manager approval per the policy documents, you MUST say: "I understand you're looking for [specific request]. That requires manager approval. However, I can offer you these options right now: [list agent-approved offers]"
3. You are an AGENT - you can ONLY offer the agent-approved offers listed above
4. Maximum discount you can approve: {max_agent_discount}% - anything higher requires manager
5. If customer asks for discount > {max_agent_discount}%, you MUST acknowledge it FIRST, then explain your limit, then offer alternatives
6. Follow the playbook script EXACTLY for this scenario
7. Present ONE offer at a time using the playbook wording
8. Use the policy context to explain value accurately and check authorization requirements
9. Only accept cancellation if customer insists after all agent-approved options
10. OUTPUT ONLY THE CUSTOMER-FACING MESSAGE - NO explanations, NO reasoning, NO "In this response" statements, NO meta-commentary"""

        full_prompt = f"""Customer Message: {customer_message}

{recent_conv}

INSTRUCTIONS:
1. First, check the "CUSTOMER REQUEST ANALYSIS" section in the policy context above
2. If the customer's request requires manager approval (like "custom billing arrangements"), acknowledge this FIRST
3. Then offer agent-approved alternatives from the list above
4. Use the playbook script and policy context to craft your response
5. For service_value scenarios: Present trial extension FIRST, then mention downgrade option ($6.99 basic plan) as alternative
6. Present ONE specific offer at a time with exact details (costs, duration, savings)

IMPORTANT: Output ONLY the message to the customer. Do NOT include any explanations, reasoning, or meta-commentary. Just speak directly to the customer."""

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=full_prompt)]
        response = self.llm.invoke(messages)
        response_text = response.content
        
        # Clean up: Remove any reasoning text that might have been output
        # Look for patterns like "In this response", "I'm empathizing", etc.
        lines = response_text.split('\n')
        cleaned_lines = []
        reasoning_started = False
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            
            # Detect start of reasoning section
            if any(phrase in line_lower for phrase in [
                "in this response", "i'm empathizing", "i'm offering", 
                "this option provides", "i'm presenting", "in this response i'm"
            ]):
                reasoning_started = True
                continue
            
            # If reasoning started, skip all subsequent lines
            if reasoning_started:
                continue
            
            cleaned_lines.append(line)
        
        response_text = '\n'.join(cleaned_lines).strip()
        
        # If we removed everything, fall back to original
        if not response_text:
            response_text = response.content
        
        response_lower = response_text.lower()
        
        # Check if agent's response indicates customer still wants to cancel after hearing offers
        # This happens when agent says things like "I understand you want to proceed with cancellation"
        # vs when agent presents offers (which means customer hasn't insisted yet)
        should_process_cancellation = any(
            phrase in response_lower
            for phrase in [
                "process the cancellation",
                "proceed with cancellation",
                "process your cancellation",
                "i understand your decision to cancel",
                "respect your choice to cancel",
                "proceed with canceling",
            ]
        ) and not any(
            phrase in response_lower
            for phrase in [
                "before we",
                "let me offer",
                "i can arrange",
                "we can",
                "how about",
            ]
        )

        return {
            "agent": "retention",
            "response": response_text,  # Use cleaned response without reasoning
            "reason": reason,
            "offers_available": len(agent_offers) > 0,
            "offers": agent_offers,  # Return only agent-approved offers
            "should_process_cancellation": should_process_cancellation,
            "customer_tier": customer_tier,
        }

    def _get_playbook_script(self, reason: str, customer_data: dict) -> str:
        """Extract scenario-specific script from playbook"""
        playbook_lower = self.playbook.lower()
        
        if reason == "financial_hardship":
            # Extract Financial Hardship section
            start = self.playbook.find("### Financial Hardship Cancellation")
            if start != -1:
                end = self.playbook.find("### Product Issue Retention", start)
                if end == -1:
                    end = self.playbook.find("### Service Value Questioning", start)
                if end != -1:
                    return self.playbook[start:end].strip()
            return "Lead with empathy. Acknowledge financial stress. Offer payment pause or downgrade options."
        
        elif reason == "product_issues":
            # Extract Product Issue section
            start = self.playbook.find("### Product Issue Retention")
            if start != -1:
                end = self.playbook.find("### Service Value Questioning", start)
                if end != -1:
                    return self.playbook[start:end].strip()
            return "Acknowledge the product issue. Offer replacement or technical support."
        
        elif reason == "service_value":
            # Extract Service Value section
            start = self.playbook.find("### Service Value Questioning")
            if start != -1:
                end = self.playbook.find("## Special Situations", start)
                if end != -1:
                    return self.playbook[start:end].strip()
            return "Explain value. Offer trial extension or downgrade option."
        
        return self.playbook[:500]  # Fallback to general principles

    def _format_offers(self, offers: List[dict]) -> str:
        """Format offers for prompt"""
        if not offers:
            return "No offers available"
        
        formatted = []
        for i, offer in enumerate(offers, 1):
            offer_type = offer.get("type", "unknown")
            desc = offer.get("description", "")
            
            details = []
            if "duration_months" in offer:
                details.append(f"Duration: {offer['duration_months']} months")
            if "cost" in offer:
                details.append(f"Cost: ${offer['cost']}")
            if "new_cost" in offer:
                details.append(f"New monthly cost: ${offer['new_cost']}")
            if "percentage" in offer:
                details.append(f"Discount: {offer['percentage']}%")
            if "savings" in offer:
                details.append(f"Savings: ${offer['savings']}")
            
            formatted.append(f"{i}. {offer_type.upper()}: {desc}")
            if details:
                formatted.append(f"   Details: {', '.join(details)}")
        
        return "\n".join(formatted)

    def _classify_reason(self, message: str, customer_data: dict) -> str:
        message_lower = message.lower()
        if any(word in message_lower for word in ["afford", "money", "cost", "expensive", "can't pay", "financial"]):
            return "financial_hardship"
        if any(word in message_lower for word in ["overheat", "broken", "defect", "not working", "issue", "problem", "return"]):
            return "product_issues"
        if any(word in message_lower for word in ["never used", "don't need", "value", "worth", "useless", "waste"]):
            return "service_value"
        return "financial_hardship"
