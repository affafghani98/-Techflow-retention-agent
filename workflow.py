"""
LangGraph Workflow - Multi-Agent Orchestration
Demonstrates agent-to-agent communication and state management
"""
from typing import TypedDict, List, Literal
from langgraph.graph import StateGraph, END
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.greeter_agent import GreeterAgent
from agents.retention_agent import RetentionAgent
from agents.processor_agent import ProcessorAgent
from rag.vector_store import RAGSystem
import os
from dotenv import load_dotenv

load_dotenv()


class ConversationState(TypedDict):
    """State management for conversation flow"""
    customer_message: str
    customer_email: str
    customer_data: dict
    intent: str
    next_agent: str
    conversation_history: List[str]
    agent_responses: List[dict]
    final_action: str
    completed: bool
    should_process_cancellation: bool


class MultiAgentWorkflow:
    """LangGraph workflow orchestrating 3 agents"""
    
    def __init__(self, api_key: str):
        """Initialize workflow with all agents"""
        self.api_key = api_key
        
        # Initialize RAG system
        self.rag_system = RAGSystem(api_key)
        
        # Initialize agents
        self.greeter = GreeterAgent(api_key, self.rag_system)
        self.retention = RetentionAgent(api_key, self.rag_system)
        self.processor = ProcessorAgent(api_key)
        
        # Build workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(ConversationState)
        
        # Add nodes
        workflow.add_node("greeter", self._greeter_node)
        workflow.add_node("retention", self._retention_node)
        workflow.add_node("processor", self._processor_node)
        workflow.add_node("technical_support", self._technical_support_node)
        workflow.add_node("billing", self._billing_node)
        
        # Set entry point
        workflow.set_entry_point("greeter")
        
        # Add conditional edges from greeter
        workflow.add_conditional_edges(
            "greeter",
            self._route_from_greeter,
            {
                "retention": "retention",
                "technical_support": "technical_support",
                "billing": "billing",
                "end": END
            }
        )
        
        # Add edges from retention
        workflow.add_conditional_edges(
            "retention",
            self._route_from_retention,
            {
                "processor": "processor",
                "end": END
            }
        )
        
        # Processor always ends
        workflow.add_edge("processor", END)
        
        # Technical support and billing end
        workflow.add_edge("technical_support", END)
        workflow.add_edge("billing", END)
        
        return workflow.compile()
    
    def _greeter_node(self, state: ConversationState) -> ConversationState:
        """Greeter agent node"""
        result = self.greeter.process(
            state["customer_message"],
            state.get("customer_email")
        )
        
        state["intent"] = result["intent"]
        state["next_agent"] = result["next_agent"]
        state["customer_email"] = result.get("customer_email") or state.get("customer_email", "")
        state["customer_data"] = result.get("customer_data") or {}
        
        # If general intent and no routing, use RAG to answer the question
        if result["intent"] == "general" and result["next_agent"] == "none":
            # Query RAG with ONLY the current customer's question (no conversation history)
            rag_query = state["customer_message"]
            context = self.rag_system.get_relevant_context(rag_query, k=5)
            
            # Use LLM to generate answer from RAG context (no previous conversation)
            from langchain_groq import ChatGroq
            from langchain_core.messages import SystemMessage, HumanMessage
            
            llm = ChatGroq(
                model="llama-3.1-8b-instant",
                groq_api_key=self.api_key,
                temperature=0.3,
            )
            
            system_prompt = """You are a helpful customer service representative for TechFlow Electronics.
Use the provided policy documents to answer customer questions accurately.
If the information is in the documents, provide a clear, helpful answer.
If the information is not available, politely say you'll need to connect them with a specialist."""
            
            user_prompt = f"""Customer Question: {state['customer_message']}

Relevant Information from Policy Documents:
{context}

Answer the customer's question using the information above. Be helpful and concise."""
            
            response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
            
            state["agent_responses"].append({
                "agent": "greeter",
                "response": response.content,
                "reasoning": "Answered using RAG from policy documents"
            })
            state["completed"] = True
        else:
            state["agent_responses"].append({
                "agent": "greeter",
                "response": f"Intent classified: {result['intent']}. Routing to {result['next_agent']}.",
                "reasoning": result.get("reasoning", "")
            })
        
        return state
    
    def _retention_node(self, state: ConversationState) -> ConversationState:
        """Retention agent node"""
        if not state.get("customer_data"):
            # Try to get customer data
            if state.get("customer_email"):
                from tools.customer_tools import get_customer_data
                result = get_customer_data.invoke({"email": state["customer_email"]})
                if result.get("success"):
                    state["customer_data"] = result["customer"]
        
        # Build conversation history - include previous customer messages and agent responses
        conversation_history = state.get("conversation_history", [])
        # If history is empty but we have previous responses, build it
        if not conversation_history and state.get("agent_responses"):
            # Extract previous customer messages and agent responses
            prev_messages = []
            for resp in state.get("agent_responses", []):
                if resp.get("agent") == "retention":
                    prev_messages.append(resp.get("response", ""))
            conversation_history = prev_messages
        
        result = self.retention.process(
            state["customer_message"],
            state.get("customer_email", ""),
            state.get("customer_data", {}),
            conversation_history
        )
        
        state["agent_responses"].append({
            "agent": "retention",
            "response": result["response"],
            "offers": result.get("offers", []),
            "should_process_cancellation": result.get("should_process_cancellation", False)
        })
        
        # Store flag indicating if customer still wants to cancel
        state["should_process_cancellation"] = result.get("should_process_cancellation", False)
        
        # Add to conversation history
        if "conversation_history" not in state:
            state["conversation_history"] = []
        state["conversation_history"].append(state["customer_message"])
        state["conversation_history"].append(result["response"])
        
        return state
    
    def _processor_node(self, state: ConversationState) -> ConversationState:
        """Processor agent node"""
        customer_data = state.get("customer_data", {})
        customer_id = customer_data.get("customer_id", "UNKNOWN")
        
        result = self.processor.process_cancellation(
            customer_id,
            state.get("customer_email", ""),
            state.get("intent", "general")
        )
        
        state["agent_responses"].append({
            "agent": "processor",
            "response": result["response"],
            "action": "cancellation_processed"
        })
        
        state["final_action"] = "cancellation_processed"
        state["completed"] = True
        
        return state
    
    def _technical_support_node(self, state: ConversationState) -> ConversationState:
        """Technical support routing node"""
        # Get relevant troubleshooting info
        context = self.rag_system.get_relevant_context(
            state["customer_message"],
            k=3
        )
        
        response = f"""I understand you're experiencing technical issues. Let me connect you with our technical support team.

Based on your issue, here's some helpful information:
{context[:500]}

Our technical specialist will be able to help you resolve this. Would you like me to schedule a callback, or would you prefer to speak with someone right now?"""
        
        state["agent_responses"].append({
            "agent": "technical_support",
            "response": response
        })
        
        state["final_action"] = "routed_to_technical_support"
        state["completed"] = True
        
        return state
    
    def _billing_node(self, state: ConversationState) -> ConversationState:
        """Billing routing node"""
        response = """I understand you have a billing question. Let me connect you with our billing department who can help clarify your charges.

For billing inquiries, our team can:
- Explain charges on your account
- Review payment history
- Adjust billing if there are errors
- Set up payment plans if needed

Would you like me to transfer you to billing now?"""
        
        state["agent_responses"].append({
            "agent": "billing",
            "response": response
        })
        
        state["final_action"] = "routed_to_billing"
        state["completed"] = True
        
        return state
    
    def _route_from_greeter(self, state: ConversationState) -> str:
        """Route from greeter based on intent"""
        next_agent = state.get("next_agent", "end")
        
        if next_agent == "retention":
            return "retention"
        elif next_agent == "technical_support":
            return "technical_support"
        elif next_agent == "billing":
            return "billing"
        else:
            return "end"
    
    def _route_from_retention(self, state: ConversationState) -> str:
        """Route from retention - only process cancellation if customer explicitly insists"""
        # Check if retention agent determined customer still wants to cancel after hearing offers
        # In a real system, this would check customer's next message after seeing the retention offer
        # For demo: retention agent presents offers first, workflow ends
        # Only route to processor if retention agent explicitly accepted cancellation
        
        should_process = state.get("should_process_cancellation", False)
        last_response = state["agent_responses"][-1] if state["agent_responses"] else {}
        
        # Only process cancellation if:
        # 1. Retention agent explicitly said to process cancellation (customer insisted)
        # 2. AND retention agent didn't just present an offer
        if should_process and last_response.get("agent") == "retention":
            retention_response = last_response.get("response", "").lower()
            # Check if agent is accepting cancellation vs presenting offers
            if any(phrase in retention_response for phrase in [
                "process the cancellation", "proceed with cancellation", 
                "i understand your decision", "respect your choice to cancel"
            ]):
                # Customer insisted → process cancellation
                return "processor"
        
        # Default: Retention agent presented offers → end workflow
        # In real system, would wait for customer's response to the offer
        return "end"
    
    def run(self, customer_message: str, customer_email: str = None, previous_state: dict = None) -> dict:
        """Run the workflow with conversation state management
        
        Args:
            customer_message: Customer's message
            customer_email: Optional customer email
            previous_state: Previous conversation state (for multi-turn conversations)
            
        Returns:
            Final state with all agent responses
        """
        # If continuing a conversation, route to appropriate agent
        if previous_state:
            # Continue conversation - maintain state
            state = previous_state.copy()
            state["customer_message"] = customer_message
            if customer_email:
                state["customer_email"] = customer_email
            
            # Reset completed flag to allow continuation
            state["completed"] = False
            
            # Add customer message to conversation history
            if "conversation_history" not in state:
                state["conversation_history"] = []
            state["conversation_history"].append(customer_message)
            
            # Determine which agent should handle this follow-up based on last agent
            last_responses = state.get("agent_responses", [])
            if last_responses:
                last_agent_type = last_responses[-1].get("agent", "")
                
                if last_agent_type == "retention":
                    # Customer responding to retention offer - continue with retention
                    # Check if customer is insisting on cancellation
                    message_lower = customer_message.lower()
                    insists_on_cancel = any(phrase in message_lower for phrase in [
                        "still want to cancel", "just cancel", "cancel anyway", 
                        "no i want to cancel", "proceed with cancellation"
                    ])
                    
                    state["next_agent"] = "retention"
                    state = self._retention_node(state)
                    
                    # If customer insists, route to processor
                    if insists_on_cancel or state.get("should_process_cancellation", False):
                        state = self._processor_node(state)
                    return state
                
                elif last_agent_type == "billing":
                    # Customer responding to billing agent - handle in context
                    # "yes" means they want transfer, "no" or questions = more info needed
                    message_lower = customer_message.lower()
                    if any(word in message_lower for word in ["yes", "sure", "ok", "transfer", "connect"]):
                        # Customer wants transfer - confirm
                        state["agent_responses"].append({
                            "agent": "billing",
                            "response": "Perfect! I'm connecting you with our billing department now. They'll be able to review your account and explain the $17.99 charge. You should hear from them shortly. Is there anything else I can help you with?"
                        })
                    else:
                        # Customer has more questions - provide additional billing info
                        context = self.rag_system.get_relevant_context(
                            "billing charges, pricing, fees, account charges", k=2
                        )
                        state["agent_responses"].append({
                            "agent": "billing",
                            "response": f"I understand you'd like more information. Here's what I can tell you:\n\n{context[:300]}\n\nOur billing team can provide the exact breakdown. Would you like me to connect you now?"
                        })
                    state["final_action"] = "billing_followup"
                    state["completed"] = True
                    return state
                
                elif last_agent_type == "technical_support":
                    # Customer responding to technical support - handle in context
                    message_lower = customer_message.lower()
                    if any(word in message_lower for word in ["yes", "sure", "ok", "schedule", "callback"]):
                        # Customer wants callback/support
                        state["agent_responses"].append({
                            "agent": "technical_support",
                            "response": "Great! I'm scheduling a callback with our technical specialist for you. They'll call you within the next hour to help resolve your charging issue. Is there anything else I can help you with?"
                        })
                    else:
                        # More technical questions - provide troubleshooting info
                        context = self.rag_system.get_relevant_context(customer_message, k=2)
                        state["agent_responses"].append({
                            "agent": "technical_support",
                            "response": f"Let me provide some additional troubleshooting steps:\n\n{context[:300]}\n\nWould you like me to schedule a callback with our technical specialist?"
                        })
                    state["final_action"] = "technical_support_followup"
                    state["completed"] = True
                    return state
            
            # If unclear, route through greeter again (but with conversation history)
            state["intent"] = ""  # Reset to re-classify
            state["next_agent"] = ""
            final_state = self.workflow.invoke(state)
            return final_state
        else:
            # New conversation - start fresh
            initial_state: ConversationState = {
                "customer_message": customer_message,
                "customer_email": customer_email or "",
                "customer_data": {},
                "intent": "",
                "next_agent": "",
                "conversation_history": [],
                "agent_responses": [],
                "final_action": "",
                "completed": False,
                "should_process_cancellation": False
            }
            
            # Run workflow
            final_state = self.workflow.invoke(initial_state)
            
            return final_state


def create_workflow(api_key: str = None) -> MultiAgentWorkflow:
    """Factory function to create workflow. Uses GROQ_API_KEY (free tier, e.g. llama-3.1-8b-instant)."""
    if not api_key:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables. Set it in .env")
    
    return MultiAgentWorkflow(api_key)
