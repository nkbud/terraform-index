"""Kubernetes collector for terraform state files stored as secrets."""

import json
import asyncio
import base64
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Set, List
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .base import BaseCollector


class KubernetesCollector(BaseCollector):
    """Collects terraform state files from Kubernetes secrets across multiple clusters and namespaces."""

    def __init__(
        self,
        clusters: List[Dict[str, Any]] = None,
        poll_interval: int = 60,
        secret_label_selector: str = "app.terraform.io/component=backend-state",
        secret_name_pattern: str = "tfstate-",
    ):
        """
        Initialize Kubernetes collector.
        
        Args:
            clusters: List of cluster configurations, each containing:
                - name: cluster name
                - kubeconfig: path to kubeconfig file (optional, uses default if not provided)
                - context: kubectl context name (optional)
                - namespaces: list of namespaces to search (optional, searches all if not provided)
            poll_interval: How often to poll for new secrets (seconds)
            secret_label_selector: Label selector to identify terraform state secrets
            secret_name_pattern: Pattern to match secret names containing terraform state
        """
        self.clusters = clusters or []
        self.poll_interval = poll_interval
        self.secret_label_selector = secret_label_selector
        self.secret_name_pattern = secret_name_pattern
        self.seen_secrets: Set[str] = set()
        self._running = False
        self._kubernetes_clients: Dict[str, client.CoreV1Api] = {}

    async def start(self) -> None:
        """Initialize the collector and Kubernetes clients."""
        self._running = True
        
        # Initialize Kubernetes clients for each cluster
        for cluster_config in self.clusters:
            cluster_name = cluster_config['name']
            
            try:
                # Load kubeconfig
                if 'kubeconfig' in cluster_config:
                    config.load_kube_config(
                        config_file=cluster_config['kubeconfig'],
                        context=cluster_config.get('context')
                    )
                else:
                    # Try in-cluster config first, then default kubeconfig
                    try:
                        config.load_incluster_config()
                    except config.ConfigException:
                        config.load_kube_config(context=cluster_config.get('context'))
                
                # Create API client
                k8s_client = client.CoreV1Api()
                
                # Test connection
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: k8s_client.get_api_version()
                )
                
                self._kubernetes_clients[cluster_name] = k8s_client
                print(f"Connected to Kubernetes cluster: {cluster_name}")
                
            except Exception as e:
                print(f"Failed to connect to Kubernetes cluster {cluster_name}: {e}")
                # Continue with other clusters even if one fails
                continue
    
    async def stop(self) -> None:
        """Clean up the collector."""
        self._running = False
        self._kubernetes_clients.clear()

    async def collect(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Poll Kubernetes clusters for terraform state secrets.
        
        Yields:
            Dict with 'content' (parsed tfstate JSON) and 'metadata'
        """
        while self._running:
            try:
                # Process all clusters
                for cluster_name, k8s_client in self._kubernetes_clients.items():
                    cluster_config = next(
                        (c for c in self.clusters if c['name'] == cluster_name), 
                        {}
                    )
                    
                    # Get list of namespaces to search
                    namespaces = cluster_config.get('namespaces', [])
                    if not namespaces:
                        # If no specific namespaces configured, get all namespaces
                        try:
                            ns_response = await asyncio.get_event_loop().run_in_executor(
                                None, lambda: k8s_client.list_namespace()
                            )
                            namespaces = [ns.metadata.name for ns in ns_response.items]
                        except ApiException as e:
                            print(f"Failed to list namespaces in cluster {cluster_name}: {e}")
                            continue
                    
                    # Search each namespace for terraform state secrets
                    for namespace in namespaces:
                        try:
                            await self._process_namespace(k8s_client, cluster_name, namespace)
                        except ApiException as e:
                            if e.status == 403:
                                print(f"No access to namespace {namespace} in cluster {cluster_name}")
                            else:
                                print(f"Error processing namespace {namespace} in cluster {cluster_name}: {e}")
                            continue
                            
            except Exception as e:
                print(f"Error during Kubernetes collection: {e}")
            
            # Wait before next poll
            await asyncio.sleep(self.poll_interval)

    async def _process_namespace(self, k8s_client: client.CoreV1Api, cluster_name: str, namespace: str):
        """Process a single namespace for terraform state secrets."""
        try:
            # List secrets in namespace with label selector
            secrets_response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: k8s_client.list_namespaced_secret(
                    namespace=namespace,
                    label_selector=self.secret_label_selector
                )
            )
            
            for secret in secrets_response.items:
                await self._process_secret(k8s_client, cluster_name, namespace, secret)
                        
        except ApiException as e:
            # Also try searching by name pattern if label selector fails
            if e.status == 400:  # Bad request might mean label selector not supported
                try:
                    all_secrets_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: k8s_client.list_namespaced_secret(namespace=namespace)
                    )
                    
                    for secret in all_secrets_response.items:
                        if self.secret_name_pattern in secret.metadata.name:
                            await self._process_secret(k8s_client, cluster_name, namespace, secret)
                            
                except ApiException as inner_e:
                    print(f"Failed to list secrets in {namespace}: {inner_e}")
            else:
                raise

    async def _process_secret(self, k8s_client: client.CoreV1Api, cluster_name: str, namespace: str, secret):
        """Process a single secret that might contain terraform state."""
        secret_name = secret.metadata.name
        secret_uid = secret.metadata.uid
        
        # Create unique identifier for this secret
        secret_id = f"{cluster_name}:{namespace}:{secret_name}:{secret_uid}"
        
        # Skip if already processed
        if secret_id in self.seen_secrets:
            return
        
        try:
            # Look for terraform state in secret data
            # Common keys used by terraform kubernetes backend: "tfstate", "state", "terraform.tfstate"
            state_keys = ['tfstate', 'state', 'terraform.tfstate', 'default.tfstate']
            
            tfstate_data = None
            state_key_used = None
            
            for key in state_keys:
                if key in secret.data:
                    # Decode base64 data
                    encoded_data = secret.data[key]
                    decoded_data = base64.b64decode(encoded_data).decode('utf-8')
                    
                    try:
                        tfstate_data = json.loads(decoded_data)
                        state_key_used = key
                        break
                    except json.JSONDecodeError:
                        # Not valid JSON, try next key
                        continue
            
            if tfstate_data is None:
                print(f"No valid terraform state found in secret {cluster_name}:{namespace}:{secret_name}")
                return
            
            # Mark as processed
            self.seen_secrets.add(secret_id)
            
            # Extract metadata
            labels = secret.metadata.labels or {}
            annotations = secret.metadata.annotations or {}
            
            # Yield the terraform state with metadata
            async for item in self._yield_terraform_state(tfstate_data, {
                'source': 'kubernetes',
                'cluster': cluster_name,
                'namespace': namespace,
                'secret_name': secret_name,
                'secret_uid': secret_uid,
                'state_key': state_key_used,
                'labels': labels,
                'annotations': annotations,
                'created_at': secret.metadata.creation_timestamp.isoformat() if secret.metadata.creation_timestamp else None,
                'collected_at': datetime.utcnow().isoformat(),
            }):
                yield item
                
        except Exception as e:
            print(f"Error processing secret {cluster_name}:{namespace}:{secret_name}: {e}")

    async def _yield_terraform_state(self, tfstate_data: Dict[str, Any], base_metadata: Dict[str, Any]):
        """
        Yield terraform state data with appropriate metadata.
        
        This method handles the terraform state format and yields individual resources
        or the entire state depending on the structure.
        """
        # Simple approach: yield the entire terraform state
        # The parser will handle extracting individual resources
        yield {
            'content': tfstate_data,
            'metadata': base_metadata
        }