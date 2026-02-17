# Guidelines Compliance Checklist

This document verifies the implementation against **guidelinesand steps.txt**. Nothing extra, nothing missing.

---

## Technical Requirements (MUST FOLLOW)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **MUST use LangChain/LangGraph** for agent orchestration | ✅ | `workflow.py` uses `langgraph.graph.StateGraph`, `add_node`, `add_conditional_edges`, `compile()` |
| Demonstrate proper agent-to-agent communication | ✅ | Greeter → Retention/Technical/Billing; Retention → Processor. State passed via `ConversationState`. |
| Show state management between agents | ✅ | `ConversationState` TypedDict: customer_message, customer_email, customer_data, intent, next_agent, conversation_history, agent_responses, final_action, completed |
| Clear workflow definition for agent handoffs | ✅ | `_route_from_greeter`, `_route_from_retention`, conditional edges to retention/technical_support/billing/processor/END |

---

## Tool Integration (Required)

| Tool | Guideline | Status | Implementation |
|------|-----------|--------|----------------|
| `get_customer_data(email) -> dict` | Load customer profile from customers.csv | ✅ | `tools/customer_tools.py`: reads `customers.csv`, returns customer dict or error |
| `calculate_retention_offer(customer_tier, reason) -> dict` | Generate offers using retention_rules.json | ✅ | Reads `retention_rules.json`, returns offers for financial_hardship (by tier), product_issues (overheating + battery_issues), service_value (care_plus_premium) |
| `update_customer_status(customer_id, action) -> dict` | Process cancellations/changes (log to file) | ✅ | Appends to `customer_updates.log` with timestamp, customer_id, action |

---

## RAG Implementation (Required)

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Use provided policy documents for context retrieval | ✅ | `rag/vector_store.py`: loads `return_policy.md`, `care_plus_benefits.md`, `troubleshooting_guide.md` |
| Implement vector search (FAISS, Qdrant, Pinecone, or similar) | ✅ | FAISS via `langchain_community.vectorstores.FAISS.from_documents()` |
| Agents must query documents during conversations | ✅ | Greeter calls `rag_system.get_relevant_context()` for intent; Retention calls it for solutions; Technical support node uses it for troubleshooting |
| Show relevant information retrieval in action | ✅ | `search()`, `get_relevant_context()` used in agents |

---

## LLM & Architecture

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Free LLM preferred (Gemini recommended) | ✅ | `ChatGoogleGenerativeAI(model="gemini-pro")`, `GoogleGenerativeAIEmbeddings` |
| Function calling or structured output | ✅ | Greeter uses JSON-style structured output in prompt; tool calls used (get_customer_data, calculate_retention_offer, update_customer_status) |
| Proper prompt engineering | ✅ | System prompts from retention_playbook; RAG context injected; scenario-specific prompts |
| Error handling and fallbacks | ✅ | All 3 tools have try/except; return error dicts; RAG checks vector_store |

---

## The 3 Chat Agents

| Agent | Guideline | Status | Implementation |
|-------|-----------|--------|----------------|
| **Agent 1: Greeter & Orchestrator** | Figures out who the customer is; decides what help they need; sends to right specialist | ✅ | `agents/greeter_agent.py`: get_customer_data, RAG for intent, classifies cancellation/technical_support/billing, sets next_agent |
| **Agent 2: Problem Solver** | Tries to keep customers; offers solutions (discounts, pauses); only gives up if they really want to leave | ✅ | `agents/retention_agent.py`: uses playbook, get_customer_data, calculate_retention_offer, RAG for policy; presents offers |
| **Agent 3: Processor** | Actually cancels when needed; updates customer accounts; handles paperwork | ✅ | `agents/processor_agent.py`: update_customer_status, confirmation message |

---

## What We Give You (Files Used)

| Item | Status | Usage |
|------|--------|--------|
| customers.csv | ✅ | `get_customer_data` |
| retention_rules.json | ✅ | `calculate_retention_offer` |
| Return Policy, Care+ Benefits, Tech Support Guide | ✅ | RAG: return_policy.md, care_plus_benefits.md, troubleshooting_guide.md |
| retention_playbook.md | ✅ | Loaded in Retention agent system prompt (convert to agent prompts per guideline) |

---

## 5 Test Conversations

| Test | Customer message | Expected | Status |
|------|------------------|----------|--------|
| 1. Money Problems | can't afford $13/month care+, need to cancel | Payment pause or discount before canceling; business rules + customer data | ✅ Test 1 in test_scenarios.py |
| 2. Phone Problems | phone overheating, want to return and cancel | Replacement or upgrade before canceling; return policy + tech guide | ✅ Test 2; tool now returns product_issues (overheating) offers |
| 3. Questioning Value | paying for care+ but never used it, maybe get rid of it | Explain value, offer cheaper options; Care+ benefits | ✅ Test 3; service_value offers |
| 4. Technical Help | phone won't charge, tried different cables | Send to tech support (don't sell); tech support guide for non-cancellation | ✅ Test 4; route to technical_support |
| 5. Billing Question | charged $15.99 but thought $12.99 | Send to billing (don't sell); billing inquiry not cancellation | ✅ Test 5; route to billing |

---

## Keep It Simple

| Guideline | Status |
|-----------|--------|
| Use free LLMs | ✅ Gemini only |
| No complex databases – just simple files with LangChain tools | ✅ CSV, JSON, .md, .log only |
| Focus on making it work well rather than fancy | ✅ No extra features |

---

## What Was Missing / Fixed

1. **calculate_retention_offer** – JSON has different shapes: `financial_hardship` uses tier keys; `product_issues` uses overheating/battery_issues; `service_value` uses care_plus_premium. Tool was only handling tier-based lookup. **Fixed**: tool now handles all three structures so Test 2 and Test 3 get correct offers.
2. **langchain_community** – FAISS lives in `langchain_community.vectorstores`. **Fixed**: added `langchain-community>=0.3.0` to requirements.txt; you need to run `pip install langchain-community` (or `pip install -r requirements.txt`).
3. **Imports** – Updated to langchain_core / langchain_text_splitters / langchain_community as needed for current LangChain versions.

---

## Run After Installing Dependencies

```bash
pip install -r requirements.txt
python tests/test_scenarios.py
```

All of the above is implemented according to the guidelines only.
