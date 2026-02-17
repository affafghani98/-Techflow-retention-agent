"""
Main entry point for the chat system
Run this to start an interactive chat session
"""
import os
from dotenv import load_dotenv
from workflow import create_workflow

load_dotenv()


def main():
    """Main interactive chat loop"""
    print("="*80)
    print("TechFlow Electronics - Customer Support Chat System")
    print("="*80)
    print("\nThis system helps customers with cancellation requests.")
    print("Type 'exit' to quit.\n")
    
    # Initialize workflow
    try:
        workflow = create_workflow()
        print("✓ System initialized successfully\n")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nMake sure you have:")
        print("1. Created .env file with GROQ_API_KEY (free at https://console.groq.com/keys)")
        print("2. Installed dependencies: pip install -r requirements.txt")
        return
    
    # Chat loop with conversation state management
    conversation_state = None
    customer_email = None
    
    while True:
        # Get customer message
        customer_message = input("Customer: ").strip()
        
        if customer_message.lower() in ['exit', 'quit', 'q']:
            print("\nGoodbye!")
            break
        
        if not customer_message:
            continue
        
        # Get email only on first message
        if not customer_email:
            email_input = input("Email (optional, press Enter to skip): ").strip()
            if email_input:
                customer_email = email_input
        
        # Run workflow with conversation state
        print("\nProcessing...")
        try:
            # Save OLD state BEFORE updating (needed for response comparison)
            old_state = conversation_state
            
            # If previous conversation was a standalone general question, reset state
            # This prevents showing old responses when asking new standalone questions
            if conversation_state:
                prev_intent = conversation_state.get('intent', '')
                prev_next_agent = conversation_state.get('next_agent', '')
                if prev_intent == 'general' and prev_next_agent == 'none':
                    # Previous was standalone question - start fresh for new question
                    conversation_state = None
            
            # Pass previous state to maintain conversation context (or None for fresh start)
            result = workflow.run(customer_message, customer_email, conversation_state)
            
            # Display results
            print("\n" + "-"*80)
            print(f"Intent: {result.get('intent', 'unknown')}")
            print(f"Routing: {result.get('next_agent', 'unknown')}")
            if result.get('completed'):
                print(f"Status: Conversation completed")
            print("-"*80)
            
            # Show only NEW agent responses (not entire history)
            all_responses = result.get('agent_responses', [])
            
            # Calculate how many responses we've seen BEFORE this turn
            prev_responses_count = 0
            if old_state:
                prev_responses = old_state.get('agent_responses', [])
                prev_responses_count = len(prev_responses)
            
            # Show only new responses from this turn
            new_responses = all_responses[prev_responses_count:]
            
            # Always show responses (new or all if something went wrong)
            responses_to_show = new_responses if new_responses else all_responses
            
            for response in responses_to_show:
                agent_name = response.get('agent', 'unknown').upper()
                print(f"\n[{agent_name}]")
                print(response.get('response', 'No response'))
            
            # Update conversation state for next turn (AFTER displaying)
            conversation_state = result
            
            print("\n" + "="*80 + "\n")
            
        except Exception as e:
            print(f"\n✗ Error processing request: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
