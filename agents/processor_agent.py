"""
Agent 3: Processor
- Handles actual cancellations
- Updates customer status
- Processes final actions
"""
from typing import Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.customer_tools import update_customer_status


class ProcessorAgent:
    """Processor agent for finalizing cancellations and updates"""

    def __init__(self, api_key: str):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            groq_api_key=api_key,
            temperature=0.3,
        )
        self.system_prompt = """You are a customer service processor for TechFlow Electronics.
Your job is to: process cancellations professionally, confirm next steps, update customer records, provide billing information.
Be clear, professional, and helpful. Always confirm what happens next."""

    def process_cancellation(self, customer_id: str, customer_email: str, reason: str) -> Dict[str, Any]:
        update_result = update_customer_status.invoke(
            {"customer_id": customer_id, "action": f"cancel_{reason}"}
        )
        prompt = f"""Customer {customer_email} is canceling their Care+ service. Reason: {reason}
Generate a professional, empathetic confirmation message (2-3 sentences) that: 1) Confirms the cancellation 2) Explains what happens next (billing, service end date) 3) Thanks them for being a customer 4) Leaves door open for return. Be warm but professional."""
        response = self.llm.invoke([SystemMessage(content=self.system_prompt), HumanMessage(content=prompt)])
        return {
            "agent": "processor",
            "response": response.content,
            "customer_id": customer_id,
            "action": "cancellation_processed",
            "update_logged": update_result.get("success", False),
            "timestamp": update_result.get("timestamp"),
        }

    def process_action(self, customer_id: str, action: str, details: str = "") -> Dict[str, Any]:
        update_result = update_customer_status.invoke({"customer_id": customer_id, "action": action})
        prompt = f"""Process action: {action} for customer {customer_id}. Details: {details}
Generate a clear confirmation message explaining what was done and next steps."""
        response = self.llm.invoke([SystemMessage(content=self.system_prompt), HumanMessage(content=prompt)])
        return {
            "agent": "processor",
            "response": response.content,
            "customer_id": customer_id,
            "action": action,
            "update_logged": update_result.get("success", False),
            "timestamp": update_result.get("timestamp"),
        }
