"""
Test Script for 5 Required Scenarios
Tests all agent routing and tool usage
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow import create_workflow
from dotenv import load_dotenv

load_dotenv()


def print_test_header(test_name: str, customer_message: str):
    """Print test header"""
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)
    print(f"Customer Message: {customer_message}")
    print("-"*80)


def print_agent_response(agent_name: str, response: dict):
    """Print agent response"""
    print(f"\n[{agent_name.upper()}]")
    print(f"Response: {response.get('response', 'N/A')}")
    if 'offers' in response:
        print(f"Offers Available: {len(response.get('offers', []))}")
    if 'reasoning' in response:
        print(f"Reasoning: {response.get('reasoning', '')[:200]}")


def run_test_scenarios():
    """Run all 5 test scenarios"""
    
    # Initialize workflow
    try:
        workflow = create_workflow()
        print("✓ Workflow initialized successfully")
    except Exception as e:
        print(f"✗ Error initializing workflow: {e}")
        print("\nMake sure you have:")
        print("1. Created .env file with GOOGLE_API_KEY")
        print("2. Installed all dependencies: pip install -r requirements.txt")
        return
    
    # Test 1: Money Problems
    print_test_header(
        "Test 1: Money Problems",
        "hey can't afford the $13/month care+ anymore, need to cancel"
    )
    
    result1 = workflow.run(
        "hey can't afford the $13/month care+ anymore, need to cancel",
        "sarah.chen@email.com"
    )
    
    print(f"\nIntent: {result1.get('intent')}")
    print(f"Next Agent: {result1.get('next_agent')}")
    print(f"Final Action: {result1.get('final_action')}")
    
    for response in result1.get('agent_responses', []):
        print_agent_response(response.get('agent', 'unknown'), response)
    
    # Test 2: Phone Problems
    print_test_header(
        "Test 2: Phone Problems",
        "this phone keeps overheating, want to return it and cancel everything"
    )
    
    result2 = workflow.run(
        "this phone keeps overheating, want to return it and cancel everything",
        "mike.rodriguez@email.com"
    )
    
    print(f"\nIntent: {result2.get('intent')}")
    print(f"Next Agent: {result2.get('next_agent')}")
    print(f"Final Action: {result2.get('final_action')}")
    
    for response in result2.get('agent_responses', []):
        print_agent_response(response.get('agent', 'unknown'), response)
    
    # Test 3: Questioning Value
    print_test_header(
        "Test 3: Questioning Value",
        "paying for care+ but never used it, maybe just get rid of it?"
    )
    
    result3 = workflow.run(
        "paying for care+ but never used it, maybe just get rid of it?",
        "lisa.kim@email.com"
    )
    
    print(f"\nIntent: {result3.get('intent')}")
    print(f"Next Agent: {result3.get('next_agent')}")
    print(f"Final Action: {result3.get('final_action')}")
    
    for response in result3.get('agent_responses', []):
        print_agent_response(response.get('agent', 'unknown'), response)
    
    # Test 4: Technical Help Needed
    print_test_header(
        "Test 4: Technical Help Needed",
        "my phone won't charge anymore, tried different cables"
    )
    
    result4 = workflow.run(
        "my phone won't charge anymore, tried different cables",
        "james.wilson@email.com"
    )
    
    print(f"\nIntent: {result4.get('intent')}")
    print(f"Next Agent: {result4.get('next_agent')}")
    print(f"Final Action: {result4.get('final_action')}")
    
    # Should route to technical support, NOT retention
    if result4.get('intent') == 'technical_support' or result4.get('next_agent') == 'technical_support':
        print("✓ CORRECTLY ROUTED TO TECHNICAL SUPPORT (not cancellation)")
    else:
        print("✗ INCORRECT ROUTING - Should go to technical support")
    
    for response in result4.get('agent_responses', []):
        print_agent_response(response.get('agent', 'unknown'), response)
    
    # Test 5: Billing Question
    print_test_header(
        "Test 5: Billing Question",
        "got charged $15.99 but thought care+ was $12.99, what's the extra?"
    )
    
    result5 = workflow.run(
        "got charged $15.99 but thought care+ was $12.99, what's the extra?",
        "maria.garcia@email.com"
    )
    
    print(f"\nIntent: {result5.get('intent')}")
    print(f"Next Agent: {result5.get('next_agent')}")
    print(f"Final Action: {result5.get('final_action')}")
    
    # Should route to billing, NOT retention
    if result5.get('intent') == 'billing' or result5.get('next_agent') == 'billing':
        print("✓ CORRECTLY ROUTED TO BILLING (not cancellation)")
    else:
        print("✗ INCORRECT ROUTING - Should go to billing")
    
    for response in result5.get('agent_responses', []):
        print_agent_response(response.get('agent', 'unknown'), response)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("All 5 test scenarios completed!")
    print("\nCheck the output above to verify:")
    print("1. Test 1: Retention offers shown for financial hardship")
    print("2. Test 2: Device replacement/upgrade offers for product issues")
    print("3. Test 3: Value explanation and offers for service value questioning")
    print("4. Test 4: Routed to technical support (NOT retention)")
    print("5. Test 5: Routed to billing (NOT retention)")
    print("\nCheck customer_updates.log for logged actions")


if __name__ == "__main__":
    run_test_scenarios()
