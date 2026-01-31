from __future__ import annotations

import os
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional

import reflex as rx
from reflex.event import EventSpec
from pydantic import BaseModel
from dagster import DagsterInstance, AssetKey, Output, AssetMaterialization, AssetRecordsFilter, DagsterRunStatus, RunsFilter
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS


# Module metadata with titles, descriptions, and icons
# This maps module names to human-readable information
MODULE_METADATA: Dict[str, Dict[str, str]] = {
    "longevitymap": {
        "title": "Longevity Map",
        "description": "Longevity-associated genetic variants from LongevityMap database",
        "icon": "heart-pulse",
        "color": "success",
    },
    "lipidmetabolism": {
        "title": "Lipid Metabolism",
        "description": "Lipid metabolism and cardiovascular risk variants",
        "icon": "droplets",
        "color": "warning",
    },
    "vo2max": {
        "title": "VO2 Max",
        "description": "Athletic performance and oxygen uptake capacity variants",
        "icon": "activity",
        "color": "info",
    },
    "superhuman": {
        "title": "Superhuman",
        "description": "Elite performance and rare beneficial variants",
        "icon": "zap",
        "color": "primary",
    },
    "coronary": {
        "title": "Coronary",
        "description": "Coronary artery disease risk associations",
        "icon": "heart",
        "color": "error",
    },
    "drugs": {
        "title": "Pharmacogenomics",
        "description": "Drug response and metabolism (PharmGKB)",
        "icon": "pill",
        "color": "secondary",
    },
}


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


def get_dagster_web_url() -> str:
    """Get the URL for the Dagster web UI from environment or default."""
    return os.getenv("DAGSTER_WEB_URL", "http://localhost:3005").rstrip("/")


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
    running: bool = False
    console_output: str = ""
    files: list[str] = []
    
    # Track asset status for the UI
    asset_statuses: Dict[str, Dict[str, str]] = {}
    
    # Cache user info to avoid async get_state in computed vars
    safe_user_id: str = ""
    
    # HF Module selection - all modules selected by default
    available_modules: list[str] = DISCOVERED_MODULES.copy()
    selected_modules: list[str] = DISCOVERED_MODULES.copy()

    @rx.var
    def dagster_web_url(self) -> str:
        """Get the Dagster web UI URL."""
        return get_dagster_web_url()

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
                "annotated": "ready"
            }
        
        self.uploading = False
        if new_files:
            # Automatically select the last uploaded file
            self.selected_file = new_files[-1]
            yield rx.toast.success(f"Uploaded and registered {len(new_files)} files.")
        else:
            yield rx.toast.warning("No files were uploaded")

    def _execute_job_in_process(self, instance: DagsterInstance, job_name: str, run_config: dict, partition_key: str):
        """
        Execute a Dagster job in-process (like prepare-annotations does).
        
        This avoids all the daemon/workspace mismatch issues that submit_run has.
        The job runs synchronously in the current process.
        """
        job_def = defs.resolve_job_def(job_name)
        
        # Ensure the partition exists before running
        from just_dna_pipelines.annotation.assets import user_vcf_partitions
        existing_partitions = instance.get_dynamic_partitions(user_vcf_partitions.name)
        if partition_key not in existing_partitions:
            instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
        
        result = job_def.execute_in_process(
            run_config=run_config,
            instance=instance,
            tags={"dagster/partition": partition_key},
        )
        return result

    async def run_annotation(self, filename: str = ""):
        """Trigger materialization of user_annotated_vcf_duckdb for a file."""
        if not filename:
            filename = self.selected_file
        if not filename:
            return

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

        # Execute job in-process (like prepare-annotations does)
        # This avoids daemon/workspace mismatch issues
        result = self._execute_job_in_process(instance, job_name, run_config, partition_key)
        
        if result.success:
            self.asset_statuses[partition_key]["annotated"] = "completed"
            yield rx.toast.success(f"Annotation completed for {sample_name}")
        else:
            self.asset_statuses[partition_key]["annotated"] = "failed"
            yield rx.toast.error(f"Annotation failed for {sample_name}")

    def toggle_module(self, module: str):
        """Toggle a module on/off in the selection."""
        self.last_run_success = False
        if module in self.selected_modules:
            self.selected_modules = [m for m in self.selected_modules if m != module]
        else:
            self.selected_modules = self.selected_modules + [module]

    def select_all_modules(self):
        """Select all available modules."""
        self.last_run_success = False
        self.selected_modules = self.available_modules.copy()

    def deselect_all_modules(self):
        """Deselect all modules."""
        self.last_run_success = False
        self.selected_modules = []

    async def run_hf_annotation(self, filename: str = ""):
        """
        Trigger HF module annotation for a file.
        
        Uses the selected_modules list to determine which modules to use.
        If no modules are selected, uses all available modules.
        """
        if not filename:
            filename = self.selected_file
        if not filename:
            return

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
        
        # Use "ops" config key for asset jobs
        run_config = {
            "ops": {
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

        # Execute job in-process (like prepare-annotations does)
        modules_info = ", ".join(modules_to_use) if modules_to_use else "all modules"
        result = self._execute_job_in_process(instance, job_name, run_config, partition_key)
        
        if result.success:
            self.asset_statuses[partition_key]["hf_annotated"] = "completed"
            yield rx.toast.success(f"HF annotation completed for {sample_name} with {modules_info}")
        else:
            self.asset_statuses[partition_key]["hf_annotated"] = "failed"
            yield rx.toast.error(f"HF annotation failed for {sample_name}")

    @rx.var
    def file_statuses(self) -> Dict[str, str]:
        """Map filenames to their annotation status for the UI."""
        res = {}
        for f in self.files:
            sample_name = f.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            status = self.asset_statuses.get(pk, {}).get("annotated", "ready")
            res[f] = status
        return res

    # Currently selected file for annotation
    selected_file: str = ""
    
    # Run history tracking
    runs: List[Dict[str, Any]] = []
    active_run_id: str = ""
    run_logs: List[str] = []
    polling_active: bool = False
    
    # Tracking for the UI button state
    last_run_success: bool = False

    def select_file(self, filename: str):
        """Select a file and pre-select modules from its latest run if available."""
        self.selected_file = filename
        # Reset success state on selection change
        self.last_run_success = False
        
        # Find the latest run for this file to pre-select modules
        file_runs = [r for r in self.runs if r.get("filename") == filename]
        if file_runs:
            # Sort by started_at (ISO format strings) descending
            file_runs.sort(key=lambda x: x.get("started_at", ""), reverse=True)
            latest_run = file_runs[0]
            if latest_run.get("modules"):
                self.selected_modules = latest_run["modules"].copy()

    async def delete_file(self, filename: str):
        """Delete an uploaded file from the filesystem and state."""
        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
            
        root = Path(__file__).resolve().parents[3]
        file_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
        if file_path.exists():
            try:
                file_path.unlink()
                self.files = [f for f in self.files if f != filename]
                if self.selected_file == filename:
                    self.selected_file = ""
                yield rx.toast.success(f"Deleted {filename}")
            except Exception as e:
                yield rx.toast.error(f"Failed to delete {filename}: {str(e)}")
        else:
            yield rx.toast.error(f"File {filename} not found on disk")

    @rx.var
    def filtered_runs(self) -> List[Dict[str, Any]]:
        """Filter runs for the currently selected file."""
        if not self.selected_file:
            return []
        
        # Match by filename
        return [r for r in self.runs if r.get("filename") == self.selected_file]

    @rx.var
    def has_filtered_runs(self) -> bool:
        """Check if there are any runs for the selected file."""
        return len(self.filtered_runs) > 0

    @rx.var
    def has_selected_file(self) -> bool:
        """Check if a file is selected."""
        return bool(self.selected_file)

    @rx.var
    def has_selected_modules(self) -> bool:
        """Check if any modules are selected."""
        return len(self.selected_modules) > 0

    @rx.var
    def can_run_annotation(self) -> bool:
        """Check if annotation can be run (file and modules selected)."""
        return bool(self.selected_file) and len(self.selected_modules) > 0

    @rx.var
    def analysis_button_text(self) -> str:
        """Get the text for the analysis button based on state."""
        if self.running:
            return "Analysis Running..."
        if self.last_run_success:
            return "Analysis Complete"
        return "Start Analysis"

    @rx.var
    def analysis_button_icon(self) -> str:
        """Get the icon for the analysis button based on state."""
        if self.running:
            return "loader-circle"
        if self.last_run_success:
            return "circle-check"
        return "play"

    @rx.var
    def analysis_button_color(self) -> str:
        """Get the color class for the analysis button (Fomantic UI right labeled icon)."""
        if self.running:
            return "ui blue right labeled icon large button fluid"
        if self.last_run_success:
            return "ui green right labeled icon large button fluid"
        return "ui primary right labeled icon large button fluid"

    @rx.var
    def module_metadata_list(self) -> List[Dict[str, Any]]:
        """Return module metadata for UI display."""
        result = []
        for module_name in self.available_modules:
            meta = MODULE_METADATA.get(module_name, {
                "title": module_name.replace("_", " ").title(),
                "description": f"Annotation module: {module_name}",
                "icon": "database",
                "color": "neutral",
            })
            info = MODULE_INFOS.get(module_name)
            result.append({
                "name": module_name,
                "title": meta.get("title", module_name),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "database"),
                "color": meta.get("color", "neutral"),
                "logo_url": info.logo_url if info else None,
                "selected": module_name in self.selected_modules,
            })
        return result

    def _get_run_status_str(self, status: DagsterRunStatus) -> str:
        """Convert Dagster run status to string."""
        status_map = {
            DagsterRunStatus.QUEUED: "QUEUED",
            DagsterRunStatus.NOT_STARTED: "QUEUED",
            DagsterRunStatus.STARTING: "STARTING",
            DagsterRunStatus.STARTED: "RUNNING",
            DagsterRunStatus.SUCCESS: "SUCCESS",
            DagsterRunStatus.FAILURE: "FAILURE",
            DagsterRunStatus.CANCELED: "CANCELED",
            DagsterRunStatus.CANCELING: "CANCELING",
        }
        return status_map.get(status, "UNKNOWN")

    async def start_annotation_run(self):
        """Start annotation for the selected file with selected modules."""
        if not self.selected_file or not self.selected_modules:
            yield rx.toast.error("Please select a file and at least one module")
            return

        self.running = True
        self.run_logs = []  # Clear previous logs
        self._add_log("Starting annotation job...")
        yield

        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"

        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / self.selected_file

        self._add_log(f"File: {self.selected_file}")
        self._add_log(f"Modules: {', '.join(self.selected_modules)}")
        self._add_log(f"User: {self.safe_user_id}")

        instance = get_dagster_instance()
        job_name = "annotate_with_hf_modules_job"
        modules_to_use = self.selected_modules.copy()

        run_config = {
            "ops": {
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

        # Create the run in Dagster immediately to get a REAL Run ID
        try:
            job_def = defs.resolve_job_def(job_name)
            run = instance.create_run_for_job(
                job_def=job_def,
                run_config=run_config,
                tags={"dagster/partition": partition_key},
            )
            run_id = run.run_id
            self._add_log(f"Created Dagster run: {run_id}")
        except Exception as e:
            self._add_log(f"Failed to create run: {str(e)}")
            self.running = False
            yield rx.toast.error(f"Failed to start job: {str(e)}")
            return

        # Add the real run to history immediately
        run_info = {
            "run_id": run_id,
            "filename": self.selected_file,
            "sample_name": sample_name,
            "modules": modules_to_use,
            "status": "RUNNING",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "output_path": None,
            "error": None,
            "dagster_url": f"{get_dagster_web_url()}/runs/{run_id}",
        }
        self.runs = [run_info] + self.runs
        self.active_run_id = run_id
        self.polling_active = True
        self._add_log("Submitting run to Dagster daemon...")
        yield

        # Execute the run. We use submit_run so it handled by the daemon and we have the ID immediately.
        # This requires the dagster-daemon to be running (which it is via `uv run start`)
        try:
            instance.submit_run(run_id, workspace_process_context=None)
            self._add_log(f"Run {run_id} submitted successfully.")
        except Exception as e:
            error_message = str(e)
            self._add_log(f"Submission failed: {error_message}")
            # Fallback to in-process execution if submission fails (e.g. no daemon)
            self._add_log("Attempting in-process execution fallback...")
            try:
                # We can't easily reuse the run_id with execute_in_process as it creates its own,
                # but we can try to run it anyway.
                await asyncio.to_thread(
                    self._execute_job_in_process, 
                    instance, job_name, run_config, partition_key
                )
            except Exception as fallback_err:
                self._add_log(f"Fallback failed: {str(fallback_err)}")

        # The actual status monitoring is handled by poll_run_status which is triggered by rx.moment
        # We don't block here anymore.
        yield rx.toast.info(f"Annotation started for {sample_name}")
    
    def _add_log(self, message: str):
        """Add a timestamped log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.run_logs = self.run_logs + [f"[{timestamp}] {message}"]

    async def poll_run_status(self):
        """Poll Dagster for run status updates."""
        if not self.active_run_id or not self.polling_active:
            return

        # Don't poll for temporary IDs
        if str(self.active_run_id).startswith("running-"):
            return

        instance = get_dagster_instance()
        run = instance.get_run_by_id(self.active_run_id)

        if not run:
            self.polling_active = False
            return

        status_str = self._get_run_status_str(run.status)

        # Update run in history
        updated_runs = []
        for r in self.runs:
            if r["run_id"] == self.active_run_id:
                r["status"] = status_str
                if run.status in (DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED):
                    r["ended_at"] = datetime.now().isoformat()
                    # Find output path
                    if run.status == DagsterRunStatus.SUCCESS:
                        sample_name = r.get("sample_name", "")
                        root = Path(__file__).resolve().parents[3]
                        output_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "modules"
                        if output_dir.exists():
                            r["output_path"] = str(output_dir)
            updated_runs.append(r)
        self.runs = updated_runs

        # Fetch recent logs
        await self.fetch_run_logs(self.active_run_id)

        # Stop polling if run is complete
        if run.status in (DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED):
            self.polling_active = False
            self.running = False
            self.last_run_success = (run.status == DagsterRunStatus.SUCCESS)
            if run.status == DagsterRunStatus.SUCCESS:
                yield rx.toast.success("Annotation completed successfully!")
            elif run.status == DagsterRunStatus.FAILURE:
                yield rx.toast.error("Annotation failed. Check logs for details.")

    async def fetch_run_logs(self, run_id: str):
        """Fetch log events from Dagster for a run."""
        instance = get_dagster_instance()

        # Use all_logs(run_id) to get run events
        events = instance.all_logs(run_id)
        
        log_lines = []
        # Get last 50 events
        for event in events[-50:]:
            timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
            msg = event.message or (event.dagster_event.event_type_value if event.dagster_event else "Event")
            log_lines.append(f"[{timestamp}] {msg}")

        self.run_logs = log_lines

    def view_run(self, run_id: str):
        """Set a run as the active run to view its logs."""
        self.active_run_id = run_id
        # Trigger log fetch
        return UploadState.fetch_run_logs(run_id)

    @rx.var
    def active_run_info(self) -> Dict[str, Any]:
        """Get the currently active run info."""
        for r in self.runs:
            if r.get("run_id") == self.active_run_id:
                return r
        return {}

    @rx.var
    def has_runs(self) -> bool:
        """Check if there are any runs."""
        return len(self.runs) > 0

    @rx.var
    def has_logs(self) -> bool:
        """Check if there are any log entries."""
        return len(self.run_logs) > 0

    @rx.var
    def log_count(self) -> int:
        """Get the number of log entries."""
        return len(self.run_logs)

    def do_nothing(self):
        """No-op event handler."""
        pass

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
            
            # Check if annotated asset exists using new fetch_materializations API
            asset_key = AssetKey("user_hf_module_annotations")
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=asset_key,
                    asset_partitions=[pk],
                ),
                limit=1,
            )
            records = result.records
            
            status = "ready"
            if records:
                status = "completed"
                
            if pk not in self.asset_statuses:
                self.asset_statuses[pk] = {}
            self.asset_statuses[pk]["hf_annotated"] = status
            # For backward compatibility with file_statuses computed var
            self.asset_statuses[pk]["annotated"] = status

        # Load recent runs from Dagster
        await self._load_recent_runs()

    async def _load_recent_runs(self):
        """Load recent annotation runs from Dagster."""
        instance = get_dagster_instance()
        
        # Get recent runs for the HF annotation job
        # Use get_run_records to get timestamps (start_time, end_time are on RunRecord, not DagsterRun)
        from dagster import RunsFilter
        run_records = instance.get_run_records(
            filters=RunsFilter(job_name="annotate_with_hf_modules_job"),
            limit=20,
        )
        
        run_list = []
        for record in run_records:
            run = record.dagster_run
            # Extract info from run config
            config = run.run_config or {}
            assets_config = config.get("assets", {}).get("user_hf_module_annotations", {}).get("config", {})
            
            vcf_path = assets_config.get("vcf_path", "")
            filename = Path(vcf_path).name if vcf_path else "unknown"
            sample_name = assets_config.get("sample_name", "")
            modules = assets_config.get("modules", [])
            
            # Timestamps are on RunRecord as Unix timestamps (floats) or create_timestamp as datetime
            started_at = None
            ended_at = None
            if record.start_time:
                started_at = datetime.fromtimestamp(record.start_time).isoformat()
            if record.end_time:
                ended_at = datetime.fromtimestamp(record.end_time).isoformat()
            
            run_info = {
                "run_id": run.run_id,
                "filename": filename,
                "sample_name": sample_name,
                "modules": modules or [],
                "status": self._get_run_status_str(run.status),
                "started_at": started_at,
                "ended_at": ended_at,
                "output_path": None,
            }
            
            # Check for output if successful
            if run.status == DagsterRunStatus.SUCCESS and sample_name:
                root = Path(__file__).resolve().parents[3]
                user_name = assets_config.get("user_name", self.safe_user_id)
                output_dir = root / "data" / "output" / "users" / user_name / sample_name / "modules"
                if output_dir.exists():
                    run_info["output_path"] = str(output_dir)
            
            run_list.append(run_info)
        
        self.runs = run_list
