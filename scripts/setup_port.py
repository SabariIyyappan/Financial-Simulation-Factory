"""
Setup Port Workspace

This script:
1. Uploads all blueprints to Port
2. Seeds initial entities (service, external APIs)
3. Verifies the setup
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.credentials import Credentials
from integrations.port.client import PortClient


def load_blueprint(blueprint_name: str) -> dict:
    """Load blueprint JSON file"""
    blueprint_path = Path(__file__).parent.parent / "port" / "blueprints" / f"{blueprint_name}.json"
    with open(blueprint_path, 'r') as f:
        return json.load(f)


def upload_blueprints(client: PortClient):
    """Upload all blueprints to Port"""
    print("\n" + "="*60)
    print("Uploading Blueprints to Port")
    print("="*60)
    
    blueprints = [
        "external_api",  # Must be first (no dependencies)
        "service",       # Depends on external_api
        "factory_run",   # Depends on service
        "candidate_version",  # Depends on factory_run
        "evaluation",    # Depends on candidate_version
        "release"        # Depends on service and candidate_version
    ]
    
    for blueprint_name in blueprints:
        try:
            print(f"\nUploading: {blueprint_name}")
            blueprint_data = load_blueprint(blueprint_name)
            identifier = blueprint_data["identifier"]
            
            # Check if blueprint already exists
            try:
                existing = client.get_blueprint(identifier)
                print(f"  Blueprint '{identifier}' already exists - updating...")
                client.update_blueprint(identifier, blueprint_data)
                print(f"  [OK] Updated blueprint: {identifier}")
            except Exception as check_error:
                # Blueprint doesn't exist, create it
                try:
                    client.create_blueprint(blueprint_data)
                    print(f"  [OK] Created blueprint: {identifier}")
                except Exception as create_error:
                    print(f"  [ERROR] Failed to create blueprint: {create_error}")
                    # Try to get more details
                    import requests
                    if hasattr(create_error, 'response') and hasattr(create_error.response, 'text'):
                        print(f"  Response: {create_error.response.text}")
                    raise
                
        except Exception as e:
            print(f"  [FAIL] Failed to upload {blueprint_name}: {e}")
            raise


def seed_entities(client: PortClient):
    """Seed initial entities"""
    print("\n" + "="*60)
    print("Seeding Initial Entities")
    print("="*60)
    
    # Create External APIs
    print("\nCreating External API entities...")
    
    external_apis = [
        {
            "identifier": "catalog-api",
            "name": "Catalog API",
            "base_url": "http://localhost:8000/api/catalog",
            "version": "v1",
            "docs_url": "http://localhost:8000/docs/catalog",
            "provider": "Internal Mock"
        },
        {
            "identifier": "pricing-api",
            "name": "Pricing API",
            "base_url": "http://localhost:8000/api/pricing",
            "version": "v1",
            "docs_url": "http://localhost:8001/api/docs/pricing",
            "provider": "Internal Mock"
        },
        {
            "identifier": "availability-api",
            "name": "Availability API",
            "base_url": "http://localhost:8000/api/availability",
            "version": "v1",
            "docs_url": "http://localhost:8000/docs/availability",
            "provider": "Internal Mock"
        }
    ]
    
    for api in external_apis:
        try:
            client.create_external_api(
                identifier=api["identifier"],
                name=api["name"],
                base_url=api["base_url"],
                version=api["version"],
                docs_url=api["docs_url"],
                provider=api["provider"]
            )
            print(f"  [OK] Created: {api['name']}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  [SKIP] {api['name']} already exists")
            else:
                print(f"  [FAIL] Failed to create {api['name']}: {e}")
    
    # Create Service
    print("\nCreating Service entity...")
    
    try:
        client.create_service(
            identifier="api-guardian",
            name="API Guardian",
            owner="Person C",
            repository="https://github.com/SabariIyyappan/Financial-Simulation-Factory",
            dependencies=["catalog-api", "pricing-api", "availability-api"]
        )
        print("  [OK] Created: API Guardian service")
    except Exception as e:
        if "already exists" in str(e).lower():
            print("  [SKIP] API Guardian service already exists")
        else:
            print(f"  [FAIL] Failed to create service: {e}")


def verify_setup(client: PortClient):
    """Verify the setup"""
    print("\n" + "="*60)
    print("Verifying Setup")
    print("="*60)
    
    # Check blueprints
    print("\nChecking blueprints...")
    blueprints = client.list_blueprints()
    required_blueprints = [
        "service", "externalApi", "factoryRun",
        "candidateVersion", "evaluation", "release"
    ]
    
    found_blueprints = [bp["identifier"] for bp in blueprints]
    
    for required in required_blueprints:
        if required in found_blueprints:
            print(f"  [OK] Blueprint exists: {required}")
        else:
            print(f"  [FAIL] Blueprint missing: {required}")
    
    # Check entities
    print("\nChecking entities...")
    
    try:
        service = client.get_entity("service", "api-guardian")
        print("  [OK] Service entity exists: api-guardian")
    except:
        print("  [FAIL] Service entity missing: api-guardian")
    
    for api_id in ["catalog-api", "pricing-api", "availability-api"]:
        try:
            api = client.get_entity("externalApi", api_id)
            print(f"  [OK] External API exists: {api_id}")
        except:
            print(f"  [FAIL] External API missing: {api_id}")


def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("Port Workspace Setup")
    print("="*60)
    
    try:
        # Initialize Port client
        creds = Credentials.get_port_credentials()
        client = PortClient(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            api_url=creds["api_url"]
        )
        
        print("[OK] Connected to Port")
        
        # Upload blueprints
        upload_blueprints(client)
        
        # Seed entities
        seed_entities(client)
        
        # Verify setup
        verify_setup(client)
        
        print("\n" + "="*60)
        print("Setup Complete!")
        print("="*60)
        print("\nNext steps:")
        print("1. Visit your Port dashboard: https://app.getport.io")
        print("2. Navigate to the 'Catalog' section")
        print("3. You should see:")
        print("   - API Guardian service")
        print("   - Three external API dependencies")
        print("\n")
        
        return 0
        
    except Exception as e:
        print(f"\n[FAIL] Setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
