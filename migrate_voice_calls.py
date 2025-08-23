#!/usr/bin/env python3
"""
Migration script for Voice Calls functionality
Adds necessary database tables and indexes for VAPI integration
"""

import asyncio
import logging
from pathlib import Path
from supabase import create_client, Client

from app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_voice_calls_migration():
    """Run the voice calls database migration"""
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment")
    
    # Create Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    
    # Read migration SQL file
    migration_file = Path(__file__).parent / "sql" / "voice_calls_migration.sql"
    
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")
    
    migration_sql = migration_file.read_text()
    
    try:
        logger.info("🚀 Starting voice calls migration...")
        
        # Execute the migration
        # Note: Supabase Python client doesn't directly support raw SQL execution
        # For production, you should run this SQL directly in your Supabase SQL editor
        # or use a proper migration tool like Alembic
        
        logger.info("📄 Migration SQL prepared:")
        print("=" * 60)
        print("Please execute the following SQL in your Supabase SQL Editor:")
        print("=" * 60)
        print(migration_sql)
        print("=" * 60)
        
        # Check if tables exist by trying to query them
        try:
            # Test if voice_calls table exists
            result = supabase.table('voice_calls').select('id').limit(1).execute()
            logger.info("✅ voice_calls table exists")
        except Exception as e:
            logger.warning(f"⚠️ voice_calls table may not exist yet: {e}")
        
        try:
            # Test if vapi_webhook_events table exists
            result = supabase.table('vapi_webhook_events').select('id').limit(1).execute()
            logger.info("✅ vapi_webhook_events table exists")
        except Exception as e:
            logger.warning(f"⚠️ vapi_webhook_events table may not exist yet: {e}")
            
        logger.info("✅ Voice calls migration preparation completed!")
        logger.info("📝 Next steps:")
        logger.info("   1. Copy the SQL above")
        logger.info("   2. Go to your Supabase dashboard > SQL Editor")
        logger.info("   3. Paste and execute the SQL")
        logger.info("   4. Run this script again to verify the migration")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    print("🗄️ Voice Calls Database Migration")
    print("=" * 40)
    
    try:
        asyncio.run(run_voice_calls_migration())
    except KeyboardInterrupt:
        logger.info("🛑 Migration interrupted by user")
    except Exception as e:
        logger.error(f"💥 Migration failed with error: {e}")
        exit(1)