"""
Dagster IO Managers for annotation pipelines.

IO Managers handle the persistence and loading of asset data.
"""

from pathlib import Path

from dagster import IOManager, io_manager, InputContext, OutputContext

from just_dna_pipelines.annotation.resources import (
    get_cache_dir,
    get_user_output_dir,
    get_default_ensembl_cache_dir,
)


class SourceMetadataIOManager(IOManager):
    """
    Lightweight IO Manager for source metadata assets.
    
    This manager doesn't persist data to disk - it just passes metadata through.
    Use for assets that only provide metadata for lineage tracking.
    """
    
    def handle_output(self, context: OutputContext, obj: dict) -> None:
        """Source metadata was materialized - just log it."""
        context.log.info(f"Source metadata materialized: {obj.get('partition_key', 'unknown')}")
    
    def load_input(self, context: InputContext) -> dict:
        """
        For source metadata, we can't really load it from disk.
        Return an empty dict as a placeholder since downstream assets 
        will get the real VCF path from their config.
        """
        partition_key = context.partition_key or "unknown"
        context.log.info(f"Loading source metadata for partition: {partition_key}")
        return {"partition_key": partition_key}


class AnnotationCacheIOManager(IOManager):
    """
    Generic IO Manager for annotation/reference assets stored in the cache folder.
    
    All reference data (Ensembl, ClinVar, dbSNP, etc.) lives in:
    ~/.cache/just-dna-pipelines/{asset_name}/
    
    This allows:
    - Data persistence across Dagster restarts
    - Sharing cache across projects
    - Lazy materialization (skip if exists)
    """
    
    def _get_asset_path(self, asset_key: str) -> Path:
        """Get the cache path for a given asset."""
        if asset_key == "ensembl_annotations":
            return get_default_ensembl_cache_dir()
        if asset_key == "ensembl_duckdb":
            return get_default_ensembl_cache_dir() / "ensembl_variations.duckdb"
        return get_cache_dir() / asset_key
    
    def handle_output(self, context: OutputContext, obj: Path) -> None:
        """Asset was materialized - data already on disk, just log."""
        context.log.info(f"Annotation asset stored at: {obj}")
    
    def load_input(self, context: InputContext) -> Path:
        """Load asset by returning its cache path."""
        asset_key = context.upstream_output.asset_key.to_user_string() if context.upstream_output else "unknown"
        cache_path = self._get_asset_path(asset_key)
        
        if not cache_path.exists():
            raise FileNotFoundError(
                f"Annotation cache not found at {cache_path}. "
                f"Materialize the {asset_key} asset first."
            )
        
        context.log.info(f"Loading annotation from cache: {cache_path}")
        return cache_path


class UserAssetIOManager(IOManager):
    """
    IO Manager for user-specific assets stored in the output folder.
    
    User data is organized as:
    data/output/users/{partition_key}/{asset_name}.parquet
    
    This allows:
    - Clear separation of user data from reference data
    - Partitioning by username
    - Easy backup/export of user results
    """
    
    def _get_user_path(self, partition_key: str, asset_name: str) -> Path:
        """Get the output path for a user's asset."""
        user_dir = get_user_output_dir() / partition_key
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / f"{asset_name}.parquet"
    
    def handle_output(self, context: OutputContext, obj: Path) -> None:
        """User asset was materialized - log the path."""
        context.log.info(f"User asset stored at: {obj}")
    
    def load_input(self, context: InputContext) -> Path:
        """Load user asset by returning its path."""
        partition_key = context.partition_key or "unknown"
        asset_name = context.upstream_output.asset_key.to_user_string() if context.upstream_output else "output"
        
        user_path = self._get_user_path(partition_key, asset_name)
        
        if not user_path.exists():
            raise FileNotFoundError(f"User asset not found at {user_path}")
        
        context.log.info(f"Loading user asset: {user_path}")
        return user_path


@io_manager
def source_metadata_io_manager() -> SourceMetadataIOManager:
    """IO manager for lightweight source metadata assets."""
    return SourceMetadataIOManager()


@io_manager
def annotation_cache_io_manager() -> AnnotationCacheIOManager:
    """IO manager for annotation/reference assets in cache folder."""
    return AnnotationCacheIOManager()


@io_manager  
def user_asset_io_manager() -> UserAssetIOManager:
    """IO manager for user-specific assets in output folder."""
    return UserAssetIOManager()

