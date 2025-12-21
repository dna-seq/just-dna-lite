"""
Pipeline Serving - Run Prefect server with registered pipelines.

This module provides functionality to serve all registered pipelines
via Prefect's deployment system.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Optional

import httpx
from prefect import serve as prefect_serve

from genobear.runtime import load_env
from genobear.pipelines.registry import store


def is_server_available(url: str) -> bool:
    """Check if a Prefect server is responding at the given URL."""
    try:
        with httpx.Client(timeout=1.0) as client:
            response = client.get(f"{url}/health")
            return response.status_code == 200
    except Exception:
        return False


def start_prefect_server() -> bool:
    """Attempt to start the Prefect server in the background."""
    print("📡 Prefect server not detected. Starting it for you...")
    try:
        # Start prefect server in a new process group so it persists
        subprocess.Popen(
            ["prefect", "server", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
        )
        return True
    except Exception as e:
        print(f"❌ Failed to start Prefect server: {e}")
        return False


def serve_pipelines(
    host: str = "127.0.0.1",
    port: int = 4200,
    log_level: str = "INFO",
    limit: Optional[int] = None,
) -> None:
    """Serve all registered pipelines using Prefect.
    
    This starts a long-running process that serves all registered
    flows, making them available for execution.
    
    Args:
        host: Host for the Prefect server check
        port: Port for the Prefect server check
        log_level: Logging level
        limit: Optional limit on concurrent flow runs
    """
    load_env()
    
    # Disable annoying UI popups and telemetry
    os.environ.setdefault("PREFECT_UI_ANALYTICS_ENABLED", "false")
    os.environ.setdefault("PREFECT_API_ANALYTICS_ENABLED", "false")
    os.environ.setdefault("PREFECT_UI_ONBOARDING_ENABLED", "false")
    os.environ.setdefault("PREFECT_LOGGING_LEVEL", log_level)
    
    # Connection logic
    api_url = os.getenv("PREFECT_API_URL")
    local_ui = f"http://{host}:{port}"
    local_api = f"{local_ui}/api"
    
    if not api_url:
        if not is_server_available(local_api):
            if start_prefect_server():
                # Wait for server to come online
                for i in range(15):
                    time.sleep(1)
                    if is_server_available(local_api):
                        os.environ["PREFECT_API_URL"] = local_api
                        print(f"✅ Prefect server is UP. View dashboard at: {local_ui}/flows")
                        break
                    if i == 14:
                        print("⚠️  Server taking too long to start. Falling back to EPHEMERAL mode.")
            else:
                print("⚠️  Starting in EPHEMERAL mode (NO UI).")
        else:
            os.environ["PREFECT_API_URL"] = local_api
            print(f"✅ Connected to running Prefect server. View dashboard at: {local_ui}/flows")
    else:
        print(f"🚀 Using configured Prefect API at: {api_url}")
    
    # Get all registered flows
    flows = store.get_flows()
    
    if not flows:
        print("No pipelines registered. Nothing to serve.")
        return
    
    print(f"Serving {len(flows)} pipeline(s):")
    for info in store.list_pipelines():
        print(f"  - {info.name} ({info.category.value}): {info.description}")
    
    # Create deployments for each flow
    deployments = []
    deployment_links = []
    
    for info in store.list_pipelines():
        deployment_name = f"{info.name}-deployment"
        deployment = info.flow.to_deployment(
            name=deployment_name,
            tags=info.tags + [info.category.value, "genobear"],
            description=info.description,
        )
        deployments.append(deployment)
        
        # Construct link for local UI if available
        if not api_url or "127.0.0.1" in api_url or "localhost" in api_url:
            # Prefect 3.x deployment URL structure
            link = f"{local_ui}/deployments/deployment/{info.flow.name}/{deployment_name}"
            # For humans, spaces in URL are fine in modern terminals, but better to be safe
            link = link.replace(" ", "%20")
            deployment_links.append(f"  - {info.name}: {link}")
    
    # Serve all deployments
    if deployment_links:
        print("\n🚀 Clickable Deployment Links:")
        for link in deployment_links:
            print(link)
            
    print(f"\n📡 Serving {len(deployments)} deployments. Polling for runs...")
    prefect_serve(*deployments, limit=limit)

