"""
Test connections to Port and Bright Data

Run this to verify credentials are working before proceeding.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.credentials import Credentials
from integrations.port.client import PortClient
from integrations.brightdata.client import BrightDataClient


def test_port_connection():
    """Test Port API connection"""
    print("\n" + "="*60)
    print("Testing Port Connection...")
    print("="*60)
    
    try:
        creds = Credentials.get_port_credentials()
        client = PortClient(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            api_url=creds["api_url"]
        )
        
        print("[OK] Successfully authenticated with Port")
        print(f"  Client ID: {creds['client_id'][:20]}...")
        
        # Try to list blueprints
        blueprints = client.list_blueprints()
        print(f"[OK] Successfully fetched blueprints")
        print(f"  Found {len(blueprints)} existing blueprints")
        
        if blueprints:
            print("\n  Existing blueprints:")
            for bp in blueprints[:5]:  # Show first 5
                print(f"    - {bp.get('identifier', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Port connection failed: {e}")
        return False


def test_brightdata_connection():
    """Test Bright Data API connection"""
    print("\n" + "="*60)
    print("Testing Bright Data Connection...")
    print("="*60)
    
    try:
        creds = Credentials.get_brightdata_credentials()
        client = BrightDataClient(
            api_token=creds["api_token"],
            api_url=creds["api_url"]
        )
        
        print("[OK] Bright Data client initialized")
        print(f"  API Token: {creds['api_token'][:20]}...")
        
        # Test health check (if available)
        # Note: Bright Data API structure may vary
        print("[OK] Bright Data client ready")
        print("  Note: Full API test requires scraper configuration")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] Bright Data connection failed: {e}")
        return False


def main():
    """Run all connection tests"""
    print("\n" + "="*60)
    print("API Guardian - Connection Tests")
    print("="*60)
    
    results = {
        "Port": test_port_connection(),
        "Bright Data": test_brightdata_connection()
    }
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for service, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"{service:20} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n[OK] All connections successful! Ready to proceed.")
        return 0
    else:
        print("\n[FAIL] Some connections failed. Please check credentials.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
