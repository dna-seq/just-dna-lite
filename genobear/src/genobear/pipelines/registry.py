"""
Pipeline Store - Central registration system for Prefect flows.

This module implements an extensible store pattern for managing Prefect pipelines.
Pipelines can be registered:
- Programmatically via store.register_flow()
- Automatically via entry points (genobear.pipelines)
- By discovery from the built-in genobear flows
"""

from __future__ import annotations

import importlib.metadata
import sys
from enum import Enum
from typing import Any, Callable, Optional

from prefect import Flow
from pydantic import BaseModel, Field, ConfigDict


class PipelineCategory(str, Enum):
    """Categories for organizing pipelines."""
    
    ANNOTATION = "annotation"
    PREPARATION = "preparation"
    ANALYSIS = "analysis"
    UPLOAD = "upload"
    UTILITY = "utility"
    CUSTOM = "custom"


class PipelineInfo(BaseModel):
    """Metadata about a registered pipeline."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    flow: Flow
    description: str = ""
    category: PipelineCategory = PipelineCategory.CUSTOM
    version: str = "0.1.0"
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "custom"


class PipelineStore:
    """Central store for Prefect pipelines.
    
    Provides an extensible system for registering and managing pipelines.
    Supports automatic discovery via Python entry points.
    """
    
    ENTRY_POINT_GROUP = "genobear.pipelines"
    
    def __init__(self) -> None:
        self._pipelines: dict[str, PipelineInfo] = {}
        self._loaded_entry_points = False
        self._loaded_builtins = False
    
    def register(
        self,
        name: Optional[str] = None,
        description: str = "",
        category: PipelineCategory = PipelineCategory.CUSTOM,
        version: str = "0.1.0",
        author: str = "",
        tags: Optional[list[str]] = None,
        source: str = "custom",
    ) -> Callable[[Flow], Flow]:
        """Decorator to register a Prefect flow as a pipeline."""
        def decorator(flow_fn: Flow) -> Flow:
            pipeline_name = name or flow_fn.name or flow_fn.__name__
            
            info = PipelineInfo(
                name=pipeline_name,
                flow=flow_fn,
                description=description or flow_fn.__doc__ or "",
                category=category,
                version=version,
                author=author,
                tags=tags or [],
                source=source,
            )
            
            self._pipelines[pipeline_name] = info
            return flow_fn
        
        return decorator
    
    def register_flow(
        self,
        flow: Flow,
        name: Optional[str] = None,
        description: str = "",
        category: PipelineCategory = PipelineCategory.CUSTOM,
        version: str = "0.1.0",
        author: str = "",
        tags: Optional[list[str]] = None,
        source: str = "custom",
    ) -> PipelineInfo:
        """Register a Prefect flow directly."""
        pipeline_name = name or flow.name or flow.__name__
        
        info = PipelineInfo(
            name=pipeline_name,
            flow=flow,
            description=description or flow.__doc__ or "",
            category=category,
            version=version,
            author=author,
            tags=tags or [],
            source=source,
        )
        
        self._pipelines[pipeline_name] = info
        return info
    
    def unregister(self, name: str) -> bool:
        """Unregister a pipeline by name."""
        if name in self._pipelines:
            del self._pipelines[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[PipelineInfo]:
        """Get pipeline info by name."""
        self._ensure_loaded()
        return self._pipelines.get(name)
    
    def list_pipelines(
        self,
        category: Optional[PipelineCategory] = None,
        source: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[PipelineInfo]:
        """List all registered pipelines with optional filtering."""
        self._ensure_loaded()
        
        pipelines = list(self._pipelines.values())
        
        if category is not None:
            pipelines = [p for p in pipelines if p.category == category]
        
        if source is not None:
            pipelines = [p for p in pipelines if p.source == source]
        
        if tags:
            pipelines = [p for p in pipelines if any(t in p.tags for t in tags)]
        
        return sorted(pipelines, key=lambda p: (p.category.value, p.name))
    
    def get_flows(self) -> list[Flow]:
        """Get all registered Prefect Flow objects."""
        self._ensure_loaded()
        return [info.flow for info in self._pipelines.values()]
    
    def _ensure_loaded(self) -> None:
        """Ensure all pipelines are loaded."""
        if not self._loaded_builtins:
            self._load_builtin_pipelines()
        if not self._loaded_entry_points:
            self._load_entry_points()
    
    def _load_builtin_pipelines(self) -> None:
        """Load built-in genobear pipelines.
        
        This triggers registration of built-in flows via their decorators.
        """
        self._loaded_builtins = True
        
        # Import annotation pipelines - decorators will trigger registration
        import genobear.annotation.ensembl_annotations_prefect
        
        # Import preparation pipelines - decorators will trigger registration
        import genobear.preparation.runners_prefect
    
    def _load_entry_points(self) -> None:
        """Load pipelines from Python entry points.
        
        Entry point format in pyproject.toml:
            [project.entry-points."genobear.pipelines"]
            my_pipeline = "my_package.flows:register"
        """
        self._loaded_entry_points = True
        
        if sys.version_info >= (3, 10):
            entry_points = importlib.metadata.entry_points(group=self.ENTRY_POINT_GROUP)
        else:
            eps = importlib.metadata.entry_points()
            entry_points = eps.get(self.ENTRY_POINT_GROUP, [])
        
        for ep in entry_points:
            register_func = ep.load()
            if callable(register_func):
                register_func(self)
    
    def reload(self) -> None:
        """Reload all pipelines (clears and re-discovers)."""
        self._pipelines.clear()
        self._loaded_entry_points = False
        self._loaded_builtins = False
        self._ensure_loaded()


# Global store instance
store = PipelineStore()
