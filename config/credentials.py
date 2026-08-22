"""
Credentials management for API Guardian Factory

This file loads credentials from environment or uses provided values.
DO NOT commit actual credentials to git.
"""

import os
from typing import Optional

class Credentials:
    """Centralized credentials management"""
    
    # Port credentials
    PORT_CLIENT_ID = os.getenv("PORT_CLIENT_ID", "")
    PORT_CLIENT_SECRET = os.getenv("PORT_CLIENT_SECRET", "")
    PORT_API_URL = os.getenv("PORT_API_URL", "https://api.getport.io/v1")

    # Bright Data credentials
    BRIGHTDATA_API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN", "")
    BRIGHTDATA_API_URL = os.getenv("BRIGHTDATA_API_URL", "https://api.brightdata.com")
    
    # Anthropic Claude (optional for now)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Local service URLs
    DOCS_SITE_URL = "http://localhost:8001"
    API_GUARDIAN_URL = "http://localhost:8000"
    SIGNOZ_API_URL = "http://localhost:3301"
    
    @classmethod
    def get_port_credentials(cls) -> dict:
        """Get Port credentials"""
        return {
            "client_id": cls.PORT_CLIENT_ID,
            "client_secret": cls.PORT_CLIENT_SECRET,
            "api_url": cls.PORT_API_URL
        }
    
    @classmethod
    def get_brightdata_credentials(cls) -> dict:
        """Get Bright Data credentials"""
        return {
            "api_token": cls.BRIGHTDATA_API_TOKEN,
            "api_url": cls.BRIGHTDATA_API_URL
        }
    
    @classmethod
    def get_anthropic_credentials(cls) -> dict:
        """Get Anthropic credentials"""
        return {
            "api_key": cls.ANTHROPIC_API_KEY
        }
