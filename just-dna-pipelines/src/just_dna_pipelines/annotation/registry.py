"""
Dynamic Dagster Registry for Just DNA Pipelines Modules.

This module handles the discovery and loading of Dagster definitions
from external modules located in the data/modules directory.
"""

import importlib.util
import os
from pathlib import Path
from typing import List

from dagster import Definitions
import yaml

from just_dna_pipelines.models import ModuleManifest


def load_module_definitions(modules_dir: Path) -> List[Definitions]:
    """
    Search for modules in the given directory and load their Dagster definitions.
    
    Each module should have a module.yaml manifest and an entrypoint file
    that exports a 'defs' Definitions object.
    """
    all_defs = []
    
    if not modules_dir.exists():
        return all_defs
    
    for module_path in modules_dir.iterdir():
        if not module_path.is_dir():
            continue
            
        manifest_path = module_path / "module.yaml"
        if not manifest_path.exists():
            continue
            
        try:
            with open(manifest_path, "r") as f:
                data = yaml.safe_load(f)
                manifest = ModuleManifest(**data)
                
            entrypoint_path = module_path / manifest.entrypoint
            if not entrypoint_path.exists():
                print(f"⚠️ Entrypoint {entrypoint_path} not found for module {manifest.name}")
                continue
                
            # Dynamic import
            module_name = f"just_dna_pipelines_module_{manifest.name.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(module_name, entrypoint_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                if hasattr(module, "defs"):
                    module_defs = getattr(module, "defs")
                    if isinstance(module_defs, Definitions):
                        all_defs.append(module_defs)
                        print(f"✅ Loaded definitions from module: {manifest.name}")
                    else:
                        print(f"⚠️ 'defs' in {entrypoint_path} is not a dagster.Definitions object")
                else:
                    print(f"⚠️ No 'defs' object found in {entrypoint_path}")
                    
        except Exception as e:
            print(f"❌ Error loading module at {module_path}: {e}")
            
    return all_defs

