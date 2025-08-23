#!/usr/bin/env python3
"""Test Supabase connection and basic functionality"""

import os
from dotenv import load_dotenv
from supabase import create_client

def test_connection():
    """Test connection to Supabase"""
    
    load_dotenv()
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Missing Supabase credentials in .env file")
        return False
    
    try:
        # Create client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        
        # Test basic functionality
        result = supabase.table("items").select("*").limit(1).execute()
        
        print("✅ Supabase connection successful")
        print(f"   URL: {SUPABASE_URL}")
        print(f"   Items table accessible: {len(result.data) >= 0}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()