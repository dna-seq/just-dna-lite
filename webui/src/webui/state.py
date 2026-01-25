from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Dict, Optional

import reflex as rx
from reflex.event import EventSpec
from pydantic import BaseModel
from dagster import DagsterInstance, AssetKey, Output, AssetMaterialization, EventRecordsFilter, DagsterEventType
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS


def _ensure_dagster_config(dagster_home: Path) -> None:
    """
    Ensure dagster.yaml exists with proper configuration.
    
    Creates the config file if missing, enabling auto-materialization
    and other important features.
    """
    config_file = dagster_home / "dagster.yaml"
    
    if config_file.exists():
        return
    
    dagster_home.mkdir(parents=True, exist_ok=True)
    
    config_content = """# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
"""
    
    config_file.write_text(config_content, encoding="utf-8")


def get_dagster_instance() -> DagsterInstance:
    """Get the Dagster instance, ensuring DAGSTER_HOME is set."""
    # Find workspace root
    root = Path(__file__).resolve().parents[3]
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    _ensure_dagster_config(dagster_home_path)
    os.environ["DAGSTER_HOME"] = dagster_home
    return DagsterInstance.get()


class AuthState(rx.State):
    """Session-based authentication state."""

    is_authenticated: bool = False
    user_email: str = ""

    @rx.var
    def login_disabled(self) -> bool:
        """Check if login is disabled via env var."""
        return os.getenv("JUST_DNA_PIPELINES_LOGIN", "false").lower() == "none"

    def login(self, form_data: dict[str, Any]) -> EventSpec:
        """Set the session auth flag."""
        login_config = os.getenv("JUST_DNA_PIPELINES_LOGIN", "false").lower()
        
        email_raw = form_data.get("email")
        password_raw = form_data.get("password")
        email = (str(email_raw) if email_raw is not None else "").strip()
        password = (str(password_raw) if password_raw is not None else "").strip()

        if not email:
            return rx.toast.error("Email is required")

        # Handle restricted login if JUST_DNA_PIPELINES_LOGIN=user:pass
        if login_config != "false" and ":" in login_config:
            valid_user, valid_pass = login_config.split(":", 1)
            if email != valid_user or password != valid_pass:
                return rx.toast.error("Invalid credentials")

        self.is_authenticated = True
        self.user_email = email
        return rx.toast.success(f"Welcome, {email}!")

    def logout(self) -> EventSpec:
        self.is_authenticated = False
        self.user_email = ""
        return rx.toast.info("Logged out")


class UploadState(rx.State):
    """Handle VCF uploads and Dagster lineage."""

    uploading: bool = False
    files: list[str] = []
    
    # Track asset status for the UI
    asset_statuses: Dict[str, Dict[str, str]] = {}
    
    # Cache user info to avoid async get_state in computed vars
    safe_user_id: str = ""
    
    # HF Module selection - all modules selected by default
    available_modules: list[str] = DISCOVERED_MODULES.copy()
    selected_modules: list[str] = DISCOVERED_MODULES.copy()

    @rx.var
    def module_details(self) -> Dict[str, Dict[str, Any]]:
        """Return details (logo, repo, etc.) for each available module."""
        return {name: info.model_dump() for name, info in MODULE_INFOS.items()}

    def _get_safe_user_id(self, auth_email: str) -> str:
        """Sanitize user_id for path and partition key."""
        user_id = auth_email or "anonymous"
        return "".join([c if c.isalnum() else "_" for c in user_id])

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of VCF files and register them in Dagster."""
        self.uploading = True
        yield
        
        auth_state = await self.get_state(AuthState)
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        root = Path(__file__).resolve().parents[3]
        # Align with Dagster's expected input directory
        upload_dir = root / "data" / "input" / "users" / self.safe_user_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_files = []
        instance = get_dagster_instance()
        
        for file in files:
            if not file.filename:
                continue
                
            # Save the file
            content = await file.read()
            if not content:
                continue
                
            file_path = upload_dir / file.filename
            file_path.write_bytes(content)
            
            # Register in Dagster
            sample_name = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
            partition_key = f"{self.safe_user_id}/{sample_name}"
            
            # 1. Add partition if missing
            from just_dna_pipelines.annotation.assets import user_vcf_partitions
            existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
            if partition_key not in existing:
                instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
            
            # 2. Materialize user_vcf_source (the source asset)
            instance.report_runless_asset_event(
                AssetMaterialization(
                    asset_key="user_vcf_source",
                    partition=partition_key,
                    metadata={
                        "path": str(file_path.absolute()),
                        "size_bytes": len(content),
                        "uploaded_via": "webui",
                    }
                )
            )
            
            if file.filename not in self.files:
                self.files.append(file.filename)
            new_files.append(file.filename)
            
            # Update status
            self.asset_statuses[partition_key] = {
                "source": "materialized",
                "annotated": "pending"
            }
        
        self.uploading = False
        if new_files:
            yield rx.toast.success(f"Uploaded and registered {len(new_files)} files.")
        else:
            yield rx.toast.warning("No files were uploaded")

    async def run_annotation(self, filename: str):
        """Trigger materialization of user_annotated_vcf_duckdb for a file."""
        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
        instance = get_dagster_instance()
        
        # Update status to running immediately
        if partition_key not in self.asset_statuses:
            self.asset_statuses[partition_key] = {}
        self.asset_statuses[partition_key]["annotated"] = "running"
        yield
        
        job_name = "annotate_vcf_duckdb_job"
        
        # Use Dagster API to submit run instead of execute_in_process
        run_config = {
            "ops": {
                "annotate_user_vcf_duckdb_op": {
                    "config": {
                        "vcf_path": str(vcf_path.absolute()),
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name
                    }
                }
            }
        }

        # Create the run
        job_def = defs.get_job_def(job_name)
        
        run = instance.create_run_for_job(
            job_def=job_def,
            partition_key=partition_key,
            run_config=run_config
        )
        
        # Submit the run
        instance.submit_run(run.run_id, workspace_snapshot=None)
        
        yield rx.toast.info(f"Started annotation for {sample_name} (Run ID: {run.run_id[:8]}...)")

    def toggle_module(self, module: str):
        """Toggle a module on/off in the selection."""
        if module in self.selected_modules:
            self.selected_modules = [m for m in self.selected_modules if m != module]
        else:
            self.selected_modules = self.selected_modules + [module]

    def select_all_modules(self):
        """Select all available modules."""
        self.selected_modules = self.available_modules.copy()

    def deselect_all_modules(self):
        """Deselect all modules."""
        self.selected_modules = []

    async def run_hf_annotation(self, filename: str):
        """
        Trigger HF module annotation for a file.
        
        Uses the selected_modules list to determine which modules to use.
        If no modules are selected, uses all available modules.
        """
        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
        instance = get_dagster_instance()
        
        # Update status to running immediately
        if partition_key not in self.asset_statuses:
            self.asset_statuses[partition_key] = {}
        self.asset_statuses[partition_key]["hf_annotated"] = "running"
        yield
        
        job_name = "annotate_with_hf_modules_job"
        
        # Use selected modules, or None for all if none selected
        modules_to_use = self.selected_modules if self.selected_modules else None
        
        # Asset jobs use "assets" config key, not "ops"
        run_config = {
            "assets": {
                "user_hf_module_annotations": {
                    "config": {
                        "vcf_path": str(vcf_path.absolute()),
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name,
                        "modules": modules_to_use,
                    }
                }
            }
        }

        # Create the run
        job_def = defs.get_job_def(job_name)
        
        run = instance.create_run_for_job(
            job_def=job_def,
            partition_key=partition_key,
            run_config=run_config
        )
        
        # Submit the run
        instance.submit_run(run.run_id, workspace_snapshot=None)
        
        modules_info = ", ".join(modules_to_use) if modules_to_use else "all modules"
        yield rx.toast.info(f"Started HF annotation for {sample_name} with {modules_info} (Run ID: {run.run_id[:8]}...)")

    @rx.var
    def file_statuses(self) -> Dict[str, str]:
        """Map filenames to their annotation status for the UI."""
        res = {}
        for f in self.files:
            sample_name = f.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            status = self.asset_statuses.get(pk, {}).get("annotated", "pending")
            res[f] = status
        return res

    async def on_load(self):
        """Discover existing files and their statuses when the dashboard loads."""
        auth_state = await self.get_state(AuthState)
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        root = Path(__file__).resolve().parents[3]
        user_dir = root / "data" / "input" / "users" / self.safe_user_id
        
        if not user_dir.exists():
            return

        # Find VCF files
        vcf_files = list(user_dir.glob("*.vcf")) + list(user_dir.glob("*.vcf.gz"))
        self.files = [f.name for f in vcf_files]
        
        # Sync statuses with Dagster
        instance = get_dagster_instance()
        for f in self.files:
            sample_name = f.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            
            # Check if annotated asset exists
            asset_key = AssetKey("user_annotated_vcf_duckdb")
            records = instance.get_event_records(
                EventRecordsFilter(
                    event_type=DagsterEventType.ASSET_MATERIALIZATION,
                    asset_key=asset_key,
                    asset_partitions=[pk],
                ),
                limit=1,
            )
            
            status = "pending"
            if records:
                status = "completed"
                
            if pk not in self.asset_statuses:
                self.asset_statuses[pk] = {}
            self.asset_statuses[pk]["annotated"] = status
