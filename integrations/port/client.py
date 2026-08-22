"""
Port API Client for API Guardian Factory

Handles all interactions with Port's Context Lake:
- Blueprint management
- Entity CRUD operations
- Workflow triggers
- Relationship management
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class PortClient:
    """Client for interacting with Port API"""
    
    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        api_url: Optional[str] = None
    ):
        self.client_id = client_id or os.getenv("PORT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("PORT_CLIENT_SECRET")
        self.api_url = api_url or os.getenv("PORT_API_URL", "https://api.getport.io/v1")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Port credentials not provided")
        
        self.session = self._create_session()
        self.access_token = None
        self._authenticate()
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def _authenticate(self):
        """Authenticate with Port and get access token"""
        auth_url = f"{self.api_url}/auth/access_token"
        response = self.session.post(
            auth_url,
            json={
                "clientId": self.client_id,
                "clientSecret": self.client_secret
            }
        )
        response.raise_for_status()
        self.access_token = response.json()["accessToken"]
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })
        logger.info("Successfully authenticated with Port")
    
    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make authenticated request to Port API"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        response = self.session.request(method, url, **kwargs)
        
        # Re-authenticate if token expired
        if response.status_code == 401:
            logger.info("Token expired, re-authenticating...")
            self._authenticate()
            response = self.session.request(method, url, **kwargs)
        
        # Log error details before raising
        if not response.ok:
            try:
                error_detail = response.json()
                logger.error(f"Port API error: {error_detail}")
            except:
                logger.error(f"Port API error: {response.text}")
        
        response.raise_for_status()
        return response.json() if response.content else {}
    
    # Blueprint Management
    
    def create_blueprint(self, blueprint: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new blueprint"""
        logger.info(f"Creating blueprint: {blueprint.get('identifier')}")
        return self._request("POST", "/blueprints", json=blueprint)
    
    def get_blueprint(self, identifier: str) -> Dict[str, Any]:
        """Get blueprint by identifier"""
        return self._request("GET", f"/blueprints/{identifier}")
    
    def update_blueprint(
        self,
        identifier: str,
        blueprint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update existing blueprint"""
        logger.info(f"Updating blueprint: {identifier}")
        return self._request("PUT", f"/blueprints/{identifier}", json=blueprint)
    
    def delete_blueprint(self, identifier: str):
        """Delete blueprint"""
        logger.info(f"Deleting blueprint: {identifier}")
        return self._request("DELETE", f"/blueprints/{identifier}")
    
    def list_blueprints(self) -> List[Dict[str, Any]]:
        """List all blueprints"""
        response = self._request("GET", "/blueprints")
        return response.get("blueprints", [])
    
    # Entity Management
    
    def create_entity(
        self,
        blueprint: str,
        identifier: str,
        properties: Dict[str, Any],
        relations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a new entity"""
        logger.info(f"Creating entity: {blueprint}/{identifier}")
        
        entity_data = {
            "identifier": identifier,
            "properties": properties
        }
        
        if relations:
            entity_data["relations"] = relations
        
        return self._request(
            "POST",
            f"/blueprints/{blueprint}/entities",
            json=entity_data
        )
    
    def get_entity(self, blueprint: str, identifier: str) -> Dict[str, Any]:
        """Get entity by identifier"""
        return self._request("GET", f"/blueprints/{blueprint}/entities/{identifier}")
    
    def update_entity(
        self,
        blueprint: str,
        identifier: str,
        properties: Optional[Dict[str, Any]] = None,
        relations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update existing entity"""
        logger.info(f"Updating entity: {blueprint}/{identifier}")
        
        entity_data = {}
        if properties:
            entity_data["properties"] = properties
        if relations:
            entity_data["relations"] = relations
        
        return self._request(
            "PATCH",
            f"/blueprints/{blueprint}/entities/{identifier}",
            json=entity_data
        )
    
    def delete_entity(self, blueprint: str, identifier: str):
        """Delete entity"""
        logger.info(f"Deleting entity: {blueprint}/{identifier}")
        return self._request(
            "DELETE",
            f"/blueprints/{blueprint}/entities/{identifier}"
        )
    
    def search_entities(
        self,
        blueprint: str,
        query: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search entities with optional query"""
        params = {}
        if query:
            params["query"] = json.dumps(query)
        
        response = self._request(
            "GET",
            f"/blueprints/{blueprint}/entities",
            params=params
        )
        return response.get("entities", [])
    
    # Workflow Management
    
    def trigger_workflow(
        self,
        workflow_id: str,
        entity_id: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger a workflow action"""
        logger.info(f"Triggering workflow: {workflow_id} for entity: {entity_id}")
        
        payload = {"entity": entity_id}
        if properties:
            payload["properties"] = properties
        
        return self._request(
            "POST",
            f"/actions/{workflow_id}/runs",
            json=payload
        )
    
    def get_workflow_run(self, run_id: str) -> Dict[str, Any]:
        """Get workflow run status"""
        return self._request("GET", f"/actions/runs/{run_id}")
    
    # Helper Methods for API Guardian
    
    def create_service(
        self,
        identifier: str,
        name: str,
        owner: str,
        repository: str,
        dependencies: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a service entity"""
        properties = {
            "name": name,
            "owner": owner,
            "repository": repository,
            "health": "healthy",
            "score": 0
        }
        
        relations = {}
        if dependencies:
            relations["dependsOn"] = dependencies
        
        return self.create_entity(
            blueprint="service",
            identifier=identifier,
            properties=properties,
            relations=relations
        )
    
    def create_external_api(
        self,
        identifier: str,
        name: str,
        base_url: str,
        version: str,
        docs_url: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an external API entity"""
        properties = {
            "name": name,
            "baseUrl": base_url,
            "currentVersion": version,
            "health": "healthy",
            "lastChecked": datetime.utcnow().isoformat() + "Z"
        }
        
        if docs_url:
            properties["docsUrl"] = docs_url
        if provider:
            properties["provider"] = provider
        
        return self.create_entity(
            blueprint="externalApi",
            identifier=identifier,
            properties=properties
        )
    
    def create_factory_run(
        self,
        run_id: str,
        service_id: str,
        scenario: str,
        trigger_reason: str,
        status: str = "DETECTED"
    ) -> Dict[str, Any]:
        """Create a factory run entity"""
        properties = {
            "runId": run_id,
            "scenario": scenario,
            "triggerReason": trigger_reason,
            "status": status,
            "startedAt": datetime.utcnow().isoformat()
        }
        
        relations = {"service": service_id}
        
        return self.create_entity(
            blueprint="factoryRun",
            identifier=run_id,
            properties=properties,
            relations=relations
        )
    
    def update_factory_run_status(
        self,
        run_id: str,
        status: str,
        current_candidate: Optional[str] = None,
        incident_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update factory run status"""
        properties = {"status": status}
        
        if current_candidate:
            properties["currentCandidate"] = current_candidate
        if incident_reason:
            properties["incidentReason"] = incident_reason
        if status in ["RELEASED", "REJECTED"]:
            properties["finishedAt"] = datetime.utcnow().isoformat()
        
        return self.update_entity(
            blueprint="factoryRun",
            identifier=run_id,
            properties=properties
        )
    
    def create_candidate(
        self,
        candidate_id: str,
        factory_run_id: str,
        hypothesis: str,
        parent_version: Optional[str] = None,
        status: str = "PLANNED"
    ) -> Dict[str, Any]:
        """Create a candidate version entity"""
        properties = {
            "candidateId": candidate_id,
            "hypothesis": hypothesis,
            "status": status,
            "decision": "PENDING",
            "createdAt": datetime.utcnow().isoformat()
        }
        
        if parent_version:
            properties["parentVersion"] = parent_version
        
        relations = {"factoryRun": factory_run_id}
        
        return self.create_entity(
            blueprint="candidateVersion",
            identifier=candidate_id,
            properties=properties,
            relations=relations
        )
    
    def update_candidate_status(
        self,
        candidate_id: str,
        status: str,
        score: Optional[float] = None,
        decision: Optional[str] = None,
        commit_ref: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update candidate status"""
        properties = {"status": status}
        
        if score is not None:
            properties["score"] = score
        if decision:
            properties["decision"] = decision
        if commit_ref:
            properties["commitRef"] = commit_ref
        if status in ["READY_FOR_APPROVAL", "REJECTED"]:
            properties["evaluatedAt"] = datetime.utcnow().isoformat()
        
        return self.update_entity(
            blueprint="candidateVersion",
            identifier=candidate_id,
            properties=properties
        )
    
    def create_evaluation(
        self,
        evaluation_id: str,
        candidate_id: str,
        score: float,
        decision: str,
        correctness: str,
        p95_latency: float,
        error_rate: float,
        trace_ids: List[str],
        failure_reason: Optional[str] = None,
        failed_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an evaluation entity"""
        properties = {
            "evaluationId": evaluation_id,
            "score": score,
            "decision": decision,
            "correctness": correctness,
            "p95Latency": p95_latency,
            "errorRate": error_rate,
            "traceIds": trace_ids,
            "evaluatedAt": datetime.utcnow().isoformat()
        }
        
        if failure_reason:
            properties["failureReason"] = failure_reason
        if failed_provider:
            properties["failedProvider"] = failed_provider
        
        relations = {"candidate": candidate_id}
        
        return self.create_entity(
            blueprint="evaluation",
            identifier=evaluation_id,
            properties=properties,
            relations=relations
        )
    
    def create_release(
        self,
        version: str,
        service_id: str,
        candidate_id: str,
        approved_by: str,
        score: float,
        improvements: List[str],
        release_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a release entity"""
        properties = {
            "version": version,
            "candidateId": candidate_id,
            "approvedBy": approved_by,
            "approvedAt": datetime.utcnow().isoformat(),
            "releasedAt": datetime.utcnow().isoformat(),
            "score": score,
            "status": "active",
            "improvements": improvements
        }
        
        if release_notes:
            properties["releaseNotes"] = release_notes
        
        relations = {
            "service": service_id,
            "candidate": candidate_id
        }
        
        return self.create_entity(
            blueprint="release",
            identifier=version,
            properties=properties,
            relations=relations
        )
