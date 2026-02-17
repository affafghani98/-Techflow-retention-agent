"""
Customer Tools - Required tools for processing customer data
"""
import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from langchain_core.tools import tool


@tool
def get_customer_data(email: str) -> dict:
    """Load customer profile from customers.csv by email address.
    
    Args:
        email: Customer email address
        
    Returns:
        dict: Customer profile data or error message
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, '..', 'customers.csv')
        
        # Read CSV file
        df = pd.read_csv(csv_path)
        
        # Find customer by email
        customer = df[df['email'].str.lower() == email.lower()]
        
        if customer.empty:
            return {
                "error": "Customer not found",
                "email": email
            }
        
        # Convert to dict
        customer_dict = customer.iloc[0].to_dict()
        
        return {
            "success": True,
            "customer": customer_dict
        }
    except Exception as e:
        return {
            "error": f"Error loading customer data: {str(e)}",
            "email": email
        }


@tool
def calculate_retention_offer(customer_tier: str, reason: str) -> dict:
    """Generate retention offers using retention_rules.json based on customer tier and cancellation reason.
    
    Args:
        customer_tier: Customer tier (premium, regular, new)
        reason: Cancellation reason (financial_hardship, product_issues, service_value)
        
    Returns:
        dict: Available retention offers
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        rules_path = os.path.join(current_dir, '..', 'retention_rules.json')
        
        # Load retention rules
        with open(rules_path, 'r') as f:
            rules = json.load(f)
        
        # Map customer tier to rules structure (for financial_hardship only)
        tier_mapping = {
            'premium': 'premium_customers',
            'regular': 'regular_customers',
            'new': 'new_customers'
        }
        
        if reason not in rules:
            return {
                "error": f"Unknown reason: {reason}",
                "available_reasons": list(rules.keys())
            }
        
        reason_block = rules[reason]
        
        # financial_hardship: use tier (premium_customers, regular_customers, new_customers)
        if reason == "financial_hardship":
            tier_key = tier_mapping.get(customer_tier.lower())
            if not tier_key or tier_key not in reason_block:
                return {
                    "error": f"No offers for tier {customer_tier}",
                    "available_tiers": list(tier_mapping.keys())
                }
            offers = reason_block[tier_key]
        # product_issues: structure is overheating, battery_issues (no tier)
        elif reason == "product_issues":
            offers = []
            if "overheating" in reason_block:
                offers.extend(reason_block["overheating"])
            if "battery_issues" in reason_block:
                offers.extend(reason_block["battery_issues"])
        # service_value: structure is care_plus_premium (no tier)
        elif reason == "service_value":
            offers = reason_block.get("care_plus_premium", [])
        else:
            return {"error": f"No offers for reason: {reason}"}
        
        return {
            "success": True,
            "customer_tier": customer_tier,
            "reason": reason,
            "offers": offers
        }
    except Exception as e:
        return {
            "error": f"Error calculating retention offer: {str(e)}",
            "customer_tier": customer_tier,
            "reason": reason
        }


@tool
def update_customer_status(customer_id: str, action: str) -> dict:
    """Process cancellations/changes and log to file.
    
    Args:
        customer_id: Customer ID (e.g., CUST_001)
        action: Action to perform (cancel, pause, downgrade, etc.)
        
    Returns:
        dict: Confirmation of action
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(current_dir, '..', 'customer_updates.log')
        
        # Create log entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] Customer: {customer_id}, Action: {action}\n"
        
        # Append to log file
        with open(log_path, 'a') as f:
            f.write(log_entry)
        
        return {
            "success": True,
            "customer_id": customer_id,
            "action": action,
            "timestamp": timestamp,
            "message": f"Action '{action}' logged for customer {customer_id}"
        }
    except Exception as e:
        return {
            "error": f"Error updating customer status: {str(e)}",
            "customer_id": customer_id,
            "action": action
        }
