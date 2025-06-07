#!/usr/bin/env python3
"""
Demo script for Kubernetes collector.

This script demonstrates how to set up and run the Kubernetes collector
to collect Terraform state files from Kubernetes secrets.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from indexer.collector.kubernetes import KubernetesCollector


async def main():
    print("🔧 Terraform Kubernetes Collector Demo")
    print("=" * 50)
    
    # Example cluster configurations
    clusters = [
        {
            "name": "local-k8s",
            "context": "docker-desktop",  # Common context for Docker Desktop
            "namespaces": ["default", "terraform", "kube-system"]
        },
        # Add more clusters as needed
        # {
        #     "name": "production",
        #     "kubeconfig": "/path/to/prod-kubeconfig",
        #     "context": "prod-context",
        #     "namespaces": ["terraform", "infrastructure"]
        # }
    ]
    
    print(f"Configured to search {len(clusters)} cluster(s):")
    for cluster in clusters:
        print(f"  - {cluster['name']} (context: {cluster.get('context', 'default')})")
        if 'namespaces' in cluster:
            print(f"    Namespaces: {', '.join(cluster['namespaces'])}")
    
    print("\n🚀 Initializing Kubernetes collector...")
    
    # Create collector
    collector = KubernetesCollector(
        clusters=clusters,
        poll_interval=30,  # Poll every 30 seconds for demo
        secret_label_selector="app.terraform.io/component=backend-state",
        secret_name_pattern="tfstate-"
    )
    
    try:
        # Start the collector
        await collector.start()
        print("✅ Kubernetes collector started successfully")
        
        print("\n🔍 Searching for Terraform state secrets...")
        print("Press Ctrl+C to stop\n")
        
        # Collect terraform states
        collected_count = 0
        async for terraform_state in collector.collect():
            collected_count += 1
            metadata = terraform_state['metadata']
            content = terraform_state['content']
            
            print(f"📦 Found Terraform state #{collected_count}")
            print(f"   Cluster: {metadata['cluster']}")
            print(f"   Namespace: {metadata['namespace']}")
            print(f"   Secret: {metadata['secret_name']}")
            print(f"   State Key: {metadata['state_key']}")
            print(f"   Terraform Version: {content.get('terraform_version', 'unknown')}")
            
            # Show resource summary
            resources = content.get('resources', [])
            if resources:
                resource_types = {}
                for resource in resources:
                    res_type = resource.get('type', 'unknown')
                    resource_types[res_type] = resource_types.get(res_type, 0) + 1
                
                print(f"   Resources: {len(resources)} total")
                for res_type, count in list(resource_types.items())[:3]:  # Show top 3
                    print(f"     - {res_type}: {count}")
                if len(resource_types) > 3:
                    print(f"     - ... and {len(resource_types) - 3} more types")
            else:
                print("   Resources: No resources found")
            
            print(f"   Collected: {metadata['collected_at']}")
            print()
            
            # For demo purposes, stop after finding a few states
            if collected_count >= 5:
                print("🎯 Demo complete - found sample Terraform states")
                break
                
        if collected_count == 0:
            print("ℹ️  No Terraform state secrets found.")
            print("\nTo test this collector, create a Kubernetes secret with Terraform state:")
            print("kubectl create secret generic tfstate-demo \\")
            print("  --from-file=tfstate=/path/to/your/terraform.tfstate \\")
            print("  --annotation='app.terraform.io/component=backend-state'")
    
    except KeyboardInterrupt:
        print("\n⏹️  Stopping collector...")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    finally:
        await collector.stop()
        print("✅ Collector stopped")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())