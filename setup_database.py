#!/usr/bin/env python3
"""
Database setup script for Phase 1 Orchestrator

This script executes the SQL schema updates for the orchestrator functionality.
"""

import os
import sys
from dotenv import load_dotenv
from supabase import create_client

def setup_database():
    """Execute the Phase 1 database schema"""
    
    # Load environment variables
    load_dotenv()
    
    # Get Supabase credentials
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Error: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env file")
        sys.exit(1)
    
    # Create Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    print("🗄️  Setting up Phase 1 Orchestrator Database Schema")
    print("=" * 60)
    
    # Read the SQL file
    try:
        with open('sql/phase1_orchestrator.sql', 'r') as file:
            sql_content = file.read()
        
        print("📄 SQL file loaded successfully")
        
    except FileNotFoundError:
        print("❌ Error: sql/phase1_orchestrator.sql not found")
        sys.exit(1)
    
    # Split SQL into individual statements and execute them
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
    
    print(f"📝 Found {len(statements)} SQL statements to execute")
    print()
    
    success_count = 0
    
    for i, statement in enumerate(statements, 1):
        try:
            # Skip comments and empty statements
            if statement.startswith('--') or not statement:
                continue
                
            print(f"⏳ Executing statement {i}/{len(statements)}...")
            
            # Execute the SQL statement
            result = supabase.rpc('exec_sql', {'sql': statement}).execute()
            
            print(f"✅ Statement {i} executed successfully")
            success_count += 1
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's an "already exists" error (which we can ignore)
            if any(keyword in error_msg.lower() for keyword in ['already exists', 'relation already exists', 'column already exists']):
                print(f"ℹ️  Statement {i} skipped (already exists)")
                success_count += 1
            else:
                print(f"❌ Error in statement {i}: {error_msg}")
                # Show the problematic statement
                print(f"   SQL: {statement[:100]}...")
    
    print()
    print(f"📊 Database setup completed: {success_count}/{len(statements)} statements processed")
    
    # Verify the setup
    print("\n🔍 Verifying database setup...")
    
    try:
        # Check if new columns exist
        result = supabase.rpc('exec_sql', {
            'sql': "SELECT column_name FROM information_schema.columns WHERE table_name = 'items' AND column_name IN ('ai_request', 'orchestration_status', 'orchestration_result')"
        }).execute()
        
        columns = result.data if result.data else []
        expected_columns = ['ai_request', 'orchestration_status', 'orchestration_result']
        
        print(f"✅ Found {len(columns)} orchestrator columns in items table")
        
        # Check if new tables exist
        result = supabase.rpc('exec_sql', {
            'sql': "SELECT table_name FROM information_schema.tables WHERE table_name IN ('agent_messages', 'orchestrations') AND table_schema = 'public'"
        }).execute()
        
        tables = result.data if result.data else []
        expected_tables = ['agent_messages', 'orchestrations']
        
        print(f"✅ Found {len(tables)} orchestrator tables")
        
        if len(columns) >= 2 and len(tables) >= 2:  # At least the main columns and tables
            print("\n🎉 Database setup successful! Ready to run orchestrator tests.")
        else:
            print(f"\n⚠️  Setup incomplete. Expected 3 columns and 2 tables, found {len(columns)} columns and {len(tables)} tables.")
            
    except Exception as e:
        print(f"\n⚠️  Could not verify setup: {e}")
        print("The setup may have succeeded, but verification failed.")

if __name__ == "__main__":
    try:
        setup_database()
    except KeyboardInterrupt:
        print("\n🛑 Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Setup failed: {e}")
        sys.exit(1)