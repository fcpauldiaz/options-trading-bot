#!/usr/bin/env python3
"""
Script to verify Supabase connection and permissions.
Run this to diagnose connection issues.
"""
import os
import sys
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def verify_connection():
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    
    print("=" * 60)
    print("Supabase Connection Verification")
    print("=" * 60)
    
    if not supabase_url:
        print("❌ ERROR: SUPABASE_URL is not set")
        return False
    else:
        print(f"✓ SUPABASE_URL is set: {supabase_url[:30]}...")
    
    if not supabase_key:
        print("❌ ERROR: SUPABASE_SERVICE_ROLE_KEY is not set")
        return False
    else:
        key_preview = supabase_key[:20] + "..." if len(supabase_key) > 20 else supabase_key
        print(f"✓ SUPABASE_SERVICE_ROLE_KEY is set: {key_preview}")
        
        # Check if it looks like a service role key (starts with eyJ)
        if not supabase_key.startswith("eyJ"):
            print("⚠️  WARNING: Service role key should start with 'eyJ'")
        elif "anon" in supabase_key.lower() or "public" in supabase_key.lower():
            print("⚠️  WARNING: This might be an anon key, not a service_role key!")
            print("   Service role keys are longer and should be from Settings > API > service_role key")
    
    print("\n" + "=" * 60)
    print("Testing Connection...")
    print("=" * 60)
    
    try:
        client: Client = create_client(supabase_url, supabase_key)
        print("✓ Successfully created Supabase client")
        
        # Test SELECT (should work even without full permissions)
        print("\nTesting SELECT permission...")
        try:
            result = client.table('trades').select('id').limit(1).execute()
            print("✓ SELECT permission: OK")
        except Exception as e:
            print(f"❌ SELECT permission failed: {e}")
            return False
        
        # Test INSERT (this is what's failing)
        print("\nTesting INSERT permission...")
        try:
            test_data = {
                "timestamp": "2025-01-01T00:00:00Z",
                "message_id": "test_verification",
                "ticker": "TEST",
                "strike": 100.0,
                "option_type": "C",
                "action": "BOUGHT",
                "contracts": 1,
                "option_symbol": "TEST_VERIFICATION",
                "order_id": "test",
                "status": "test",
                "account_id": "test",
                "order_type": "market"
            }
            result = client.table('trades').insert(test_data).execute()
            print("✓ INSERT permission: OK")
            
            # Clean up test record
            if result.data and len(result.data) > 0:
                trade_id = result.data[0].get('id')
                if trade_id:
                    client.table('trades').delete().eq('id', trade_id).execute()
                    print("✓ Test record cleaned up")
        except Exception as e:
            error_msg = str(e)
            if "permission denied" in error_msg.lower() or "42501" in error_msg:
                print("❌ INSERT permission: DENIED")
                print("\n" + "=" * 60)
                print("SOLUTION:")
                print("=" * 60)
                print("Run this SQL in your Supabase SQL Editor:")
                print("\nGRANT INSERT, UPDATE, DELETE, SELECT ON TABLE public.trades TO service_role;")
                print("GRANT INSERT, UPDATE, DELETE, SELECT ON TABLE public.positions TO service_role;")
                print("\nOr use the fix_supabase_permissions.sql file in this directory.")
            else:
                print(f"❌ INSERT failed with error: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✓ All checks passed! Your connection is working correctly.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_connection()
    sys.exit(0 if success else 1)
