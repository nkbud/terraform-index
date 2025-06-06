"""Terraform state parser for indexing."""

from typing import Dict, Any, List, Iterator
from datetime import datetime


class TfStateParser:
    """Parses Terraform state files into indexed documents."""

    def parse(self, tfstate: Dict[str, Any], metadata: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """
        Parse a terraform state file into individual resource documents.
        
        Args:
            tfstate: Parsed terraform state JSON
            metadata: Source metadata (bucket, key, etc.)
            
        Yields:
            Individual resource documents ready for indexing
        """
        # Extract basic state metadata
        state_version = tfstate.get('version', 0)
        terraform_version = tfstate.get('terraform_version', 'unknown')
        
        # Process resources
        resources = tfstate.get('resources', [])
        
        for resource in resources:
            # Extract resource metadata
            resource_type = resource.get('type', 'unknown')
            resource_name = resource.get('name', 'unknown')
            resource_mode = resource.get('mode', 'unknown')
            provider = resource.get('provider', 'unknown')
            
            # Process each instance of the resource
            instances = resource.get('instances', [{}])
            
            for idx, instance in enumerate(instances):
                attributes = instance.get('attributes', {})
                
                # Create flat document for indexing
                doc = {
                    # Unique document ID
                    'id': f"{metadata['bucket']}/{metadata['key']}/{resource_type}.{resource_name}.{idx}",
                    
                    # State metadata
                    'state_version': state_version,
                    'terraform_version': terraform_version,
                    
                    # Resource metadata
                    'resource_type': resource_type,
                    'resource_name': resource_name,
                    'resource_mode': resource_mode,
                    'provider': provider,
                    'instance_index': idx,
                    
                    # Source metadata
                    'source_bucket': metadata['bucket'],
                    'source_key': metadata['key'],
                    'source_last_modified': metadata['last_modified'],
                    'indexed_at': datetime.utcnow().isoformat(),
                    
                    # Flatten attributes for searchability
                    **self._flatten_attributes(attributes, prefix='attr_'),
                    
                    # Keep original attributes as nested object
                    'attributes': attributes,
                }
                
                yield doc

    def _flatten_attributes(self, obj: Any, prefix: str = '', max_depth: int = 3) -> Dict[str, Any]:
        """
        Flatten nested attributes for easier searching.
        
        Args:
            obj: Object to flatten (dict, list, or primitive)
            prefix: Current key prefix
            max_depth: Maximum nesting depth to prevent infinite recursion
            
        Returns:
            Flattened key-value pairs
        """
        if max_depth <= 0:
            return {}
        
        flattened = {}
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_key = f"{prefix}{key}"
                if isinstance(value, (dict, list)):
                    flattened.update(
                        self._flatten_attributes(value, f"{new_key}_", max_depth - 1)
                    )
                else:
                    # Store primitive values
                    flattened[new_key] = value
                    
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_key = f"{prefix}{idx}"
                if isinstance(item, (dict, list)):
                    flattened.update(
                        self._flatten_attributes(item, f"{new_key}_", max_depth - 1)
                    )
                else:
                    flattened[new_key] = item
        
        return flattened