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
from dagster import DagsterInstance, AssetKey, AssetMaterialization, AssetRecordsFilter, DagsterRunStatus, RunsFilter, MetadataValue
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS, HF_DEFAULT_REPOS


# Module metadata with titles, descriptions, and icons
# This maps module names to human-readable information
# Species options for VCF metadata (Latin/scientific names)
SPECIES_OPTIONS: List[str] = [
    "Homo sapiens",       # Human
    "Mus musculus",       # Mouse
    "Rattus norvegicus",  # Rat
    "Canis lupus familiaris",  # Dog
    "Felis catus",        # Cat
    "Danio rerio",        # Zebrafish
    "Other",
]

# Reference genome options by species (Latin names)
# For humans: GRCh38 and T2T-CHM13 are the main modern assemblies
REFERENCE_GENOMES: Dict[str, List[str]] = {
    "Homo sapiens": ["GRCh38", "T2T-CHM13v2.0", "GRCh37"],
    "Mus musculus": ["GRCm39", "GRCm38"],
    "Rattus norvegicus": ["mRatBN7.2", "Rnor_6.0"],
    "Canis lupus familiaris": ["ROS_Cfam_1.0", "CanFam3.1"],
    "Felis catus": ["Felis_catus_9.0", "Felis_catus_8.0"],
    "Danio rerio": ["GRCz11", "GRCz10"],
    "Other": ["custom"],
}

# Sex options (biological sex for genomic analysis)
SEX_OPTIONS: List[str] = [
    "N/A",      # Not specified/applicable
    "Male",
    "Female",
    "Other",
]

# Tissue source options (common sample sources)
TISSUE_OPTIONS: List[str] = [
    "Not specified",
    "Saliva",
    "Blood",
    "Buccal swab",
    "Skin",
    "Hair follicle",
    "Muscle",
    "Liver",
    "Brain",
    "Tumor",
    "Cell line",
    "Other",
]


# Module colors map to Fomantic UI named colors derived from the DNA logo palette:
#   red (#db2828)    = heart/clinical urgency  (Coronary)
#   yellow (#fbbd08) = metabolic energy        (Lipid Metabolism)
#   green (#21ba45)  = life/longevity          (Longevity Map)
#   teal (#00b5ad)   = performance/vitality    (Sportshuman)
#   blue (#2185d0)   = oxygen/respiration      (VO2 Max)
#   purple (#a333c8) = drug/chemistry          (Pharmacogenomics)
MODULE_METADATA: Dict[str, Dict[str, str]] = {
    "longevitymap": {
        "title": "Longevity Map",
        "description": "Longevity-associated genetic variants from LongevityMap database",
        "icon": "heart-pulse",
        "color": "#21ba45",
    },
    "lipidmetabolism": {
        "title": "Lipid Metabolism",
        "description": "Lipid metabolism and cardiovascular risk variants",
        "icon": "droplets",
        "color": "#fbbd08",
    },
    "vo2max": {
        "title": "VO2 Max",
        "description": "Athletic performance and oxygen uptake capacity variants",
        "icon": "activity",
        "color": "#2185d0",
    },
    "superhuman": {
        "title": "Superhuman",
        "description": "Elite performance and rare beneficial variants",
        "icon": "zap",
        "color": "#00b5ad",
    },
    "coronary": {
        "title": "Coronary",
        "description": "Coronary artery disease risk associations",
        "icon": "heart",
        "color": "#db2828",
    },
    "drugs": {
        "title": "Pharmacogenomics",
        "description": "Drug response and metabolism (PharmGKB)",
        "icon": "pill",
        "color": "#a333c8",
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

    # ============================================================
    # NEW SAMPLE FORM STATE - for adding samples with metadata
    # ============================================================
    new_sample_subject_id: str = ""
    new_sample_sex: str = "N/A"
    new_sample_tissue: str = "Not specified"
    new_sample_species: str = "Homo sapiens"
    new_sample_reference_genome: str = "GRCh38"
    new_sample_study_name: str = ""
    new_sample_notes: str = ""

    @rx.var
    def dagster_web_url(self) -> str:
        """Get the Dagster web UI URL."""
        return get_dagster_web_url()

    @rx.var
    def module_details(self) -> Dict[str, Dict[str, Any]]:
        """Return details (logo, repo, etc.) for each available module."""
        return {name: info.model_dump() for name, info in MODULE_INFOS.items()}

    @rx.var
    def repo_info_list(self) -> List[Dict[str, Any]]:
        """
        Return info about each HF repository used as a module source.
        
        Groups modules by their repo_id and provides browsable HF URLs.
        """
        repos: Dict[str, Dict[str, Any]] = {}
        for name, info in MODULE_INFOS.items():
            repo_id = info.repo_id
            if repo_id not in repos:
                repos[repo_id] = {
                    "repo_id": repo_id,
                    "url": f"https://huggingface.co/datasets/{repo_id}",
                    "modules": [],
                    "module_count": 0,
                }
            repos[repo_id]["modules"].append(name)
            repos[repo_id]["module_count"] = len(repos[repo_id]["modules"])
        return list(repos.values())

    # ============================================================
    # NEW SAMPLE FORM: Computed properties for dropdowns
    # ============================================================
    @rx.var
    def new_sample_available_genomes(self) -> List[str]:
        """Get available reference genomes for the new sample's species."""
        return REFERENCE_GENOMES.get(self.new_sample_species, ["custom"])

    # Note: species_options, sex_options, tissue_options are defined below
    # (shared with file metadata editing)

    # ============================================================
    # NEW SAMPLE FORM: Setters
    # ============================================================
    def set_new_sample_subject_id(self, value: str):
        """Set subject ID for new sample."""
        self.new_sample_subject_id = value

    def set_new_sample_sex(self, value: str):
        """Set sex for new sample."""
        self.new_sample_sex = value

    def set_new_sample_tissue(self, value: str):
        """Set tissue for new sample."""
        self.new_sample_tissue = value

    def set_new_sample_species(self, value: str):
        """Set species for new sample and reset reference genome."""
        self.new_sample_species = value
        self.new_sample_reference_genome = REFERENCE_GENOMES.get(value, ["custom"])[0]

    def set_new_sample_reference_genome(self, value: str):
        """Set reference genome for new sample."""
        self.new_sample_reference_genome = value

    def set_new_sample_study_name(self, value: str):
        """Set study name for new sample."""
        self.new_sample_study_name = value

    def set_new_sample_notes(self, value: str):
        """Set notes for new sample."""
        self.new_sample_notes = value

    def _reset_new_sample_form(self):
        """Reset new sample form to defaults."""
        self.new_sample_subject_id = ""
        self.new_sample_sex = "N/A"
        self.new_sample_tissue = "Not specified"
        self.new_sample_species = "Homo sapiens"
        self.new_sample_reference_genome = "GRCh38"
        self.new_sample_study_name = ""
        self.new_sample_notes = ""

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
                "annotated": "uploaded"
            }
        
        self.uploading = False
        if new_files:
            # Automatically select the last uploaded file
            self.selected_file = new_files[-1]
            yield rx.toast.success(f"Uploaded and registered {len(new_files)} files.")
        else:
            yield rx.toast.warning("No files were uploaded")

    async def handle_upload_with_metadata(self, files: list[rx.UploadFile]):
        """
        Handle upload of VCF files with metadata from the new sample form.
        
        This combines file upload and metadata registration in a single operation.
        The metadata from the form (subject_id, sex, tissue, species, etc.) is 
        stored in the Dagster asset materialization.
        """
        if not files:
            yield rx.toast.warning("No files selected for upload")
            return
            
        self.uploading = True
        
        auth_state = await self.get_state(AuthState)
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        root = Path(__file__).resolve().parents[3]
        upload_dir = root / "data" / "input" / "users" / self.safe_user_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_files = []
        instance = get_dagster_instance()
        
        for file in files:
            if not file.filename:
                continue
                
            content = await file.read()
            if not content:
                continue
                
            file_path = upload_dir / file.filename
            file_path.write_bytes(content)
            
            sample_name = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
            partition_key = f"{self.safe_user_id}/{sample_name}"
            
            # Add partition if missing
            from just_dna_pipelines.annotation.assets import user_vcf_partitions
            existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
            if partition_key not in existing:
                instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
            
            # Build complete metadata dict with form values
            metadata: Dict[str, Any] = {
                "path": MetadataValue.path(str(file_path.absolute())),
                "size_bytes": MetadataValue.int(len(content)),
                "uploaded_via": MetadataValue.text("webui"),
                "species": MetadataValue.text(self.new_sample_species),
                "reference_genome": MetadataValue.text(self.new_sample_reference_genome),
                "sex": MetadataValue.text(self.new_sample_sex),
                "tissue": MetadataValue.text(self.new_sample_tissue),
            }
            
            # Add optional fields only if provided
            if self.new_sample_subject_id.strip():
                metadata["subject_id"] = MetadataValue.text(self.new_sample_subject_id.strip())
            if self.new_sample_study_name.strip():
                metadata["study_name"] = MetadataValue.text(self.new_sample_study_name.strip())
            if self.new_sample_notes.strip():
                metadata["notes"] = MetadataValue.text(self.new_sample_notes.strip())
            
            # Materialize user_vcf_source with all metadata
            instance.report_runless_asset_event(
                AssetMaterialization(
                    asset_key="user_vcf_source",
                    partition=partition_key,
                    metadata=metadata,
                )
            )
            
            if file.filename not in self.files:
                self.files.append(file.filename)
            new_files.append(file.filename)
            
            # Also store in local file_metadata for immediate UI access
            self.file_metadata[file.filename] = {
                "filename": file.filename,
                "sample_name": sample_name,
                "species": self.new_sample_species,
                "reference_genome": self.new_sample_reference_genome,
                "sex": self.new_sample_sex,
                "tissue": self.new_sample_tissue,
                "subject_id": self.new_sample_subject_id.strip() if self.new_sample_subject_id else "",
                "study_name": self.new_sample_study_name.strip() if self.new_sample_study_name else "",
                "notes": self.new_sample_notes.strip() if self.new_sample_notes else "",
                "size_mb": round(len(content) / (1024 * 1024), 2),
                "path": str(file_path),
                "custom_fields": {},
            }
            
            # Update status
            self.asset_statuses[partition_key] = {
                "source": "materialized",
                "annotated": "uploaded"
            }
        
        self.uploading = False
        
        if new_files:
            # Reset the form and select the new file
            self._reset_new_sample_form()
            self.selected_file = new_files[-1]
            yield rx.toast.success(f"Added {len(new_files)} sample(s) with metadata")
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
        
        # Get file metadata for the selected file
        file_info = self.file_metadata.get(filename, {})
        custom_metadata = file_info.get("custom_fields", {}) or {}
        
        # Use "ops" config key for asset jobs
        run_config = {
            "ops": {
                "user_hf_module_annotations": {
                    "config": {
                        "vcf_path": str(vcf_path.absolute()),
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name,
                        "modules": modules_to_use,
                        # Sample/subject metadata from file info
                        "species": file_info.get("species", "Homo sapiens"),
                        "reference_genome": file_info.get("reference_genome", "GRCh38"),
                        "subject_id": file_info.get("subject_id") or None,
                        "sex": file_info.get("sex") or None,
                        "tissue": file_info.get("tissue") or None,
                        "study_name": file_info.get("study_name") or None,
                        "description": file_info.get("notes") or None,
                        # Arbitrary user-defined fields
                        "custom_metadata": custom_metadata if custom_metadata else None,
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
            status = self.asset_statuses.get(pk, {}).get("annotated", "uploaded")
            res[f] = status
        return res

    # Currently selected file for annotation
    selected_file: str = ""
    
    # File metadata cache: filename -> {size_mb, upload_date, reference_genome, sample_name}
    file_metadata: Dict[str, Dict[str, Any]] = {}
    
    # Run history tracking
    runs: List[Dict[str, Any]] = []
    active_run_id: str = ""
    run_logs: List[str] = []
    polling_active: bool = False
    
    # Tracking for the UI button state
    last_run_success: bool = False
    
    # Tab management for two-panel layout (legacy, kept for backwards compatibility)
    active_tab: str = "params"  # "params", "history", "outputs"
    
    # Output files for the selected sample
    output_files: List[Dict[str, Any]] = []
    
    # Run-centric UI state
    outputs_expanded: bool = True  # Whether the outputs section is expanded
    run_history_expanded: bool = True  # Whether the run history section is expanded
    new_analysis_expanded: bool = True  # Whether the new analysis section is expanded
    expanded_run_id: str = ""  # Which run in the timeline is expanded to show logs
    show_outputs_modal: bool = False  # Whether to show the outputs modal (legacy, kept for compatibility)
    
    # Metadata editing mode - when False, shows read-only view
    metadata_edit_mode: bool = False

    def toggle_metadata_edit_mode(self):
        """Toggle between read-only and edit mode for metadata."""
        self.metadata_edit_mode = not self.metadata_edit_mode

    def enable_metadata_edit_mode(self):
        """Enable edit mode for metadata."""
        self.metadata_edit_mode = True

    def disable_metadata_edit_mode(self):
        """Disable edit mode (back to read-only)."""
        self.metadata_edit_mode = False

    @rx.var
    def sample_display_names(self) -> Dict[str, str]:
        """
        Map filenames to display names.
        Shows Subject ID if available, otherwise filename.
        """
        result = {}
        for filename in self.files:
            meta = self.file_metadata.get(filename, {})
            subject_id = meta.get("subject_id", "")
            if subject_id and subject_id.strip():
                result[filename] = subject_id.strip()
            else:
                # Use sample name (filename without extension)
                result[filename] = filename.replace(".vcf.gz", "").replace(".vcf", "")
        return result

    def _load_file_metadata(self, filename: str):
        """Load metadata for a single VCF file."""
        if not self.safe_user_id:
            return
            
        root = Path(__file__).resolve().parents[3]
        file_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
        if not file_path.exists():
            return
        
        # Get file stats
        stat = file_path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        upload_date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        
        # Derive sample name
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        
        # Default species and reference genome (Latin names)
        species = "Homo sapiens"
        reference_genome = "GRCh38"
        
        self.file_metadata[filename] = {
            "filename": filename,
            "sample_name": sample_name,
            "size_mb": size_mb,
            "upload_date": upload_date,
            "species": species,
            "reference_genome": reference_genome,
            "path": str(file_path),
            # User-editable fields (required fields have defaults)
            "subject_id": "",  # Required - subject/patient identifier
            "sex": "N/A",  # Required - biological sex
            "tissue": "Not specified",  # Required - sample tissue source
            # Optional fields
            "study_name": "",
            "notes": "",
            # Custom key-value fields (user can add their own)
            "custom_fields": {},  # Dict[str, str] for user-defined fields
        }

    def update_file_species(self, species: str):
        """Update species for the selected file and reset reference genome to default."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        
        # Get default reference genome for this species
        default_ref = REFERENCE_GENOMES.get(species, ["custom"])[0]
        
        # Update metadata - need to create new dict for reactivity
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["species"] = species
        updated[self.selected_file]["reference_genome"] = default_ref
        self.file_metadata = updated
        
        # Auto-save to Dagster
        self.save_metadata_to_dagster()

    def update_file_reference_genome(self, ref_genome: str):
        """Update reference genome for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        # Create new dict for reactivity
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["reference_genome"] = ref_genome
        self.file_metadata = updated
        
        # Auto-save to Dagster
        self.save_metadata_to_dagster()

    def update_file_subject_id(self, subject_id: str):
        """Update subject/patient ID for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["subject_id"] = subject_id
        self.file_metadata = updated

    def update_file_sex(self, sex: str):
        """Update biological sex for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["sex"] = sex
        self.file_metadata = updated

    def update_file_tissue(self, tissue: str):
        """Update tissue source for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["tissue"] = tissue
        self.file_metadata = updated

    def update_file_study_name(self, study_name: str):
        """Update study/project name for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["study_name"] = study_name
        self.file_metadata = updated

    def update_file_notes(self, notes: str):
        """Update notes for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["notes"] = notes
        self.file_metadata = updated

    def add_custom_field(self, field_name: str, field_value: str):
        """Add or update a custom field for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        custom_fields = dict(updated[self.selected_file].get("custom_fields", {}))
        custom_fields[field_name] = field_value
        updated[self.selected_file]["custom_fields"] = custom_fields
        self.file_metadata = updated
        
        # Auto-save to Dagster when custom fields change
        self.save_metadata_to_dagster()

    def remove_custom_field(self, field_name: str):
        """Remove a custom field from the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        custom_fields = dict(updated[self.selected_file].get("custom_fields", {}))
        if field_name in custom_fields:
            del custom_fields[field_name]
        updated[self.selected_file]["custom_fields"] = custom_fields
        self.file_metadata = updated
        
        # Auto-save to Dagster when custom fields change
        self.save_metadata_to_dagster()

    # State for adding new custom field
    new_custom_field_name: str = ""
    new_custom_field_value: str = ""

    def set_new_field_name(self, name: str):
        """Set the name for a new custom field."""
        self.new_custom_field_name = name

    def set_new_field_value(self, value: str):
        """Set the value for a new custom field."""
        self.new_custom_field_value = value

    def save_new_custom_field(self):
        """Save the new custom field to the file metadata."""
        if self.new_custom_field_name.strip():
            self.add_custom_field(self.new_custom_field_name.strip(), self.new_custom_field_value)
            self.new_custom_field_name = ""
            self.new_custom_field_value = ""

    def _build_dagster_metadata(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Dagster metadata dict from file_info.
        
        Returns a dict suitable for AssetMaterialization.metadata.
        All values are wrapped in MetadataValue types.
        """
        metadata: Dict[str, Any] = {}
        
        # Well-known fields
        if file_info.get("filename"):
            metadata["filename"] = MetadataValue.text(file_info["filename"])
        if file_info.get("sample_name"):
            metadata["sample_name"] = MetadataValue.text(file_info["sample_name"])
        if file_info.get("species"):
            metadata["species"] = MetadataValue.text(file_info["species"])
        if file_info.get("reference_genome"):
            metadata["reference_genome"] = MetadataValue.text(file_info["reference_genome"])
        if file_info.get("subject_id"):
            metadata["subject_id"] = MetadataValue.text(file_info["subject_id"])
        if file_info.get("sex"):
            metadata["sex"] = MetadataValue.text(file_info["sex"])
        if file_info.get("tissue"):
            metadata["tissue"] = MetadataValue.text(file_info["tissue"])
        if file_info.get("study_name"):
            metadata["study_name"] = MetadataValue.text(file_info["study_name"])
        if file_info.get("notes"):
            metadata["description"] = MetadataValue.text(file_info["notes"])
        if file_info.get("path"):
            metadata["path"] = MetadataValue.path(file_info["path"])
        if file_info.get("size_mb"):
            metadata["size_mb"] = MetadataValue.float(file_info["size_mb"])
        if file_info.get("upload_date"):
            metadata["upload_date"] = MetadataValue.text(file_info["upload_date"])
        
        # Custom fields - store as JSON and also individually
        custom_fields = file_info.get("custom_fields", {})
        if custom_fields:
            metadata["custom_metadata"] = MetadataValue.json(custom_fields)
            for key, value in custom_fields.items():
                safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in key)
                metadata[f"custom/{safe_key}"] = MetadataValue.text(str(value))
        
        # Mark as saved from UI
        metadata["saved_from"] = MetadataValue.text("webui")
        
        return metadata

    def _extract_metadata_from_materialization(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract file_info dict from Dagster materialization metadata.
        
        Converts MetadataValue objects back to plain Python values.
        """
        file_info: Dict[str, Any] = {}
        
        def get_value(mv: Any) -> Any:
            """Extract value from MetadataValue or return as-is."""
            if hasattr(mv, 'value'):
                return mv.value
            return mv
        
        # Well-known fields
        if "filename" in metadata:
            file_info["filename"] = get_value(metadata["filename"])
        if "sample_name" in metadata:
            file_info["sample_name"] = get_value(metadata["sample_name"])
        if "species" in metadata:
            file_info["species"] = get_value(metadata["species"])
        if "reference_genome" in metadata:
            file_info["reference_genome"] = get_value(metadata["reference_genome"])
        if "subject_id" in metadata:
            file_info["subject_id"] = get_value(metadata["subject_id"])
        if "sex" in metadata:
            file_info["sex"] = get_value(metadata["sex"])
        if "tissue" in metadata:
            file_info["tissue"] = get_value(metadata["tissue"])
        if "study_name" in metadata:
            file_info["study_name"] = get_value(metadata["study_name"])
        if "description" in metadata:
            file_info["notes"] = get_value(metadata["description"])
        if "path" in metadata:
            file_info["path"] = get_value(metadata["path"])
        if "size_mb" in metadata:
            file_info["size_mb"] = get_value(metadata["size_mb"])
        if "upload_date" in metadata:
            file_info["upload_date"] = get_value(metadata["upload_date"])
        
        # Custom fields - prefer the JSON blob if available
        if "custom_metadata" in metadata:
            custom = get_value(metadata["custom_metadata"])
            if isinstance(custom, dict):
                file_info["custom_fields"] = custom
        else:
            # Fallback: extract from individual custom/* keys
            custom_fields = {}
            for key, value in metadata.items():
                if key.startswith("custom/"):
                    field_name = key[7:]  # Remove "custom/" prefix
                    custom_fields[field_name] = get_value(value)
            if custom_fields:
                file_info["custom_fields"] = custom_fields
        
        return file_info

    def save_metadata_to_dagster(self):
        """
        Persist current file metadata to Dagster as an AssetMaterialization.
        
        This creates a new materialization event for user_vcf_source with the
        current metadata. The metadata is then visible in the Dagster UI and
        survives UI restarts.
        """
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        
        file_info = self.file_metadata[self.selected_file]
        sample_name = file_info.get("sample_name", self.selected_file.replace(".vcf.gz", "").replace(".vcf", ""))
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        instance = get_dagster_instance()
        metadata = self._build_dagster_metadata(file_info)
        
        instance.report_runless_asset_event(
            AssetMaterialization(
                asset_key="user_vcf_source",
                partition=partition_key,
                metadata=metadata,
            )
        )
        
        return rx.toast.success(f"Metadata saved for {sample_name}")

    def _load_metadata_from_dagster(self):
        """
        Load file metadata from Dagster materializations.
        
        Queries all user_vcf_source partitions for the current user and
        extracts metadata from the latest materialization of each.
        """
        if not self.safe_user_id:
            return
        
        instance = get_dagster_instance()
        
        # Get all partitions for this user
        from just_dna_pipelines.annotation.assets import user_vcf_partitions
        all_partitions = instance.get_dynamic_partitions(user_vcf_partitions.name)
        user_partitions = [p for p in all_partitions if p.startswith(f"{self.safe_user_id}/")]
        
        for partition_key in user_partitions:
            # Fetch latest materialization for this partition
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=AssetKey("user_vcf_source"),
                    asset_partitions=[partition_key],
                ),
                limit=1,
            )
            
            if not result.records:
                continue
            
            record = result.records[0]
            mat = record.asset_materialization
            if not mat or not mat.metadata:
                continue
            
            # Extract metadata
            dagster_info = self._extract_metadata_from_materialization(mat.metadata)
            
            # Get filename from partition key or metadata
            filename = dagster_info.get("filename")
            if not filename:
                # Derive from partition key
                sample_name = partition_key.split("/", 1)[1] if "/" in partition_key else partition_key
                # Try to find matching file
                for f in self.files:
                    if f.startswith(sample_name):
                        filename = f
                        break
            
            if filename and filename in self.files:
                # Merge Dagster metadata with existing file metadata
                existing = self.file_metadata.get(filename, {})
                # Dagster metadata takes precedence for fields it has
                merged = {**existing, **dagster_info}
                # Ensure custom_fields is properly merged
                if "custom_fields" in existing and "custom_fields" in dagster_info:
                    merged["custom_fields"] = {**existing.get("custom_fields", {}), **dagster_info.get("custom_fields", {})}
                self.file_metadata[filename] = merged

    @rx.var
    def current_custom_fields(self) -> Dict[str, str]:
        """Get custom fields for the currently selected file."""
        if not self.selected_file:
            return {}
        return self.file_metadata.get(self.selected_file, {}).get("custom_fields", {})

    @rx.var
    def custom_fields_list(self) -> List[Dict[str, str]]:
        """Get custom fields as a list for rx.foreach."""
        fields = self.current_custom_fields
        return [{"name": k, "value": v} for k, v in fields.items()]

    @rx.var
    def has_custom_fields(self) -> bool:
        """Check if there are any custom fields."""
        return len(self.current_custom_fields) > 0

    @rx.var
    def backend_api_url(self) -> str:
        """Get the backend API URL for downloads."""
        return os.getenv("API_URL", "http://localhost:8000")

    @rx.var
    def current_subject_id(self) -> str:
        """Get subject ID for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("subject_id", "")

    @rx.var
    def current_study_name(self) -> str:
        """Get study name for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("study_name", "")

    @rx.var
    def current_notes(self) -> str:
        """Get notes for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("notes", "")

    @rx.var
    def current_species(self) -> str:
        """Get species for the currently selected file."""
        if not self.selected_file:
            return "Homo sapiens"
        return self.file_metadata.get(self.selected_file, {}).get("species", "Homo sapiens")

    @rx.var
    def current_reference_genome(self) -> str:
        """Get reference genome for the currently selected file."""
        if not self.selected_file:
            return "GRCh38"
        return self.file_metadata.get(self.selected_file, {}).get("reference_genome", "GRCh38")

    @rx.var
    def current_sex(self) -> str:
        """Get sex for the currently selected file."""
        if not self.selected_file:
            return "N/A"
        return self.file_metadata.get(self.selected_file, {}).get("sex", "N/A")

    @rx.var
    def current_tissue(self) -> str:
        """Get tissue source for the currently selected file."""
        if not self.selected_file:
            return "Not specified"
        return self.file_metadata.get(self.selected_file, {}).get("tissue", "Not specified")

    @rx.var
    def species_options(self) -> List[str]:
        """Get available species options."""
        return SPECIES_OPTIONS

    @rx.var
    def sex_options(self) -> List[str]:
        """Get available sex options."""
        return SEX_OPTIONS

    @rx.var
    def tissue_options(self) -> List[str]:
        """Get available tissue options."""
        return TISSUE_OPTIONS

    @rx.var
    def available_reference_genomes(self) -> List[str]:
        """Get available reference genomes for the current species."""
        species = self.current_species
        return REFERENCE_GENOMES.get(species, ["custom"])

    def select_file(self, filename: str):
        """Select a file and pre-select modules from its latest run if available."""
        self.selected_file = filename
        # Reset success state on selection change
        self.last_run_success = False
        # Reset expanded run
        self.expanded_run_id = ""
        
        # Load file metadata if not already loaded
        if filename not in self.file_metadata:
            self._load_file_metadata(filename)
        
        # Find the latest run for this file to pre-select modules
        file_runs = [r for r in self.runs if r.get("filename") == filename]
        if file_runs:
            # Sort by started_at (ISO format strings) descending, handle None values
            file_runs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
            latest_run = file_runs[0]
            if latest_run.get("modules"):
                self.selected_modules = latest_run["modules"].copy()
        
        # Expand all sections by default when selecting a file
        self.outputs_expanded = True
        self.run_history_expanded = True
        self.new_analysis_expanded = True
        
        # Load output files for the selected sample
        self._load_output_files_sync()

    def switch_tab(self, tab_name: str):
        """Switch to a different tab in the right panel."""
        self.active_tab = tab_name
        # Reload output files when switching to outputs tab
        if tab_name == "outputs":
            self._load_output_files_sync()

    def _load_output_files_sync(self):
        """Load output files for the selected sample (synchronous version)."""
        if not self.selected_file or not self.safe_user_id:
            self.output_files = []
            return
        
        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        root = Path(__file__).resolve().parents[3]
        output_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "modules"
        
        if not output_dir.exists():
            self.output_files = []
            return
        
        files = []
        for f in output_dir.glob("*.parquet"):
            # Determine file type from name
            if "_weights" in f.name:
                file_type = "weights"
            elif "_annotations" in f.name:
                file_type = "annotations"
            elif "_studies" in f.name:
                file_type = "studies"
            else:
                file_type = "data"
            
            # Extract module name
            module = f.stem.replace("_weights", "").replace("_annotations", "").replace("_studies", "")
            
            files.append({
                "name": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "module": module,
                "type": file_type,
                "sample_name": sample_name,
            })
        
        # Sort by module name, then type
        files.sort(key=lambda x: (x["module"], x["type"]))
        self.output_files = files

    @rx.var
    def has_output_files(self) -> bool:
        """Check if there are any output files for the selected sample."""
        return len(self.output_files) > 0

    @rx.var
    def output_file_count(self) -> int:
        """Get the number of output files."""
        return len(self.output_files)

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
    def last_run_for_file(self) -> Dict[str, Any]:
        """Get the most recent run for the selected file."""
        runs = self.filtered_runs
        if not runs:
            return {}
        # Already sorted by started_at descending in filtered_runs
        return runs[0]

    @rx.var
    def has_last_run(self) -> bool:
        """Check if there's a previous run for the selected file."""
        return bool(self.last_run_for_file)

    @rx.var
    def other_runs_for_file(self) -> List[Dict[str, Any]]:
        """Get all runs except the most recent one for timeline display."""
        runs = self.filtered_runs
        if len(runs) <= 1:
            return []
        return runs[1:]

    @rx.var
    def has_other_runs(self) -> bool:
        """Check if there are other runs besides the last one."""
        return len(self.other_runs_for_file) > 0

    @rx.var
    def latest_run_id(self) -> str:
        """Get the run_id of the most recent run for the selected file."""
        runs = self.filtered_runs
        if runs:
            return runs[0].get("run_id", "")
        return ""

    @rx.var
    def has_selected_file(self) -> bool:
        """Check if a file is selected."""
        return bool(self.selected_file)

    @rx.var
    def selected_file_info(self) -> Dict[str, Any]:
        """Get metadata for the currently selected file."""
        if not self.selected_file:
            return {}
        return self.file_metadata.get(self.selected_file, {})

    @rx.var
    def has_file_metadata(self) -> bool:
        """Check if we have metadata for the selected file."""
        return bool(self.selected_file_info)

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
        """Get the color class for the analysis button (DNA palette: yellow=running, green=success, blue=default)."""
        if self.running:
            return "ui yellow right labeled icon large button fluid"
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
            # Convert hf:// logo URL to browsable HTTPS URL for display
            browsable_logo_url = ""
            if info and info.logo_url:
                # hf://datasets/just-dna-seq/annotators/data/module/logo.png
                # -> https://huggingface.co/datasets/just-dna-seq/annotators/resolve/main/data/module/logo.png
                hf_path = info.logo_url.replace("hf://", "")
                browsable_logo_url = f"https://huggingface.co/{hf_path.replace(info.repo_id, info.repo_id + '/resolve/main', 1)}"
            result.append({
                "name": module_name,
                "title": meta.get("title", module_name),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "database"),
                "color": meta.get("color", "neutral"),
                "logo_url": browsable_logo_url,
                "repo_id": info.repo_id if info else "",
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
        
        # Get file metadata for the selected file
        file_info = self.file_metadata.get(self.selected_file, {})
        custom_metadata = file_info.get("custom_fields", {}) or {}

        run_config = {
            "ops": {
                "user_hf_module_annotations": {
                    "config": {
                        "vcf_path": str(vcf_path.absolute()),
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name,
                        "modules": modules_to_use,
                        # Sample/subject metadata from file info
                        "species": file_info.get("species", "Homo sapiens"),
                        "reference_genome": file_info.get("reference_genome", "GRCh38"),
                        "subject_id": file_info.get("subject_id") or None,
                        "sex": file_info.get("sex") or None,
                        "tissue": file_info.get("tissue") or None,
                        "study_name": file_info.get("study_name") or None,
                        "description": file_info.get("notes") or None,
                        # Arbitrary user-defined fields
                        "custom_metadata": custom_metadata if custom_metadata else None,
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

    def toggle_outputs(self):
        """Toggle the outputs section expanded/collapsed."""
        self.outputs_expanded = not self.outputs_expanded

    def toggle_run_history(self):
        """Toggle the run history section expanded/collapsed."""
        self.run_history_expanded = not self.run_history_expanded

    def toggle_new_analysis(self):
        """Toggle the new analysis section expanded/collapsed."""
        self.new_analysis_expanded = not self.new_analysis_expanded

    def expand_new_analysis(self):
        """Expand the new analysis section."""
        self.new_analysis_expanded = True

    def collapse_new_analysis(self):
        """Collapse the new analysis section."""
        self.new_analysis_expanded = False

    def toggle_run_expansion(self, run_id: str):
        """Toggle a run's expanded state in the timeline."""
        if self.expanded_run_id == run_id:
            self.expanded_run_id = ""
        else:
            self.expanded_run_id = run_id
            # Fetch logs for this run
            return UploadState.fetch_run_logs(run_id)

    def open_outputs_modal(self):
        """Open the outputs modal."""
        self.show_outputs_modal = True
        self._load_output_files_sync()

    def close_outputs_modal(self):
        """Close the outputs modal."""
        self.show_outputs_modal = False

    def set_show_outputs_modal(self, value: bool):
        """Set the outputs modal visibility (explicit setter for Reflex 0.8.9+)."""
        self.show_outputs_modal = value
        if value:
            self._load_output_files_sync()

    async def rerun_with_same_modules(self):
        """Re-run annotation with the same modules as the last run."""
        last_run = self.last_run_for_file
        if last_run and last_run.get("modules"):
            self.selected_modules = last_run["modules"].copy()
        # Start the annotation
        async for event in self.start_annotation_run():
            yield event

    def modify_and_run(self):
        """Pre-select modules from last run and expand the analysis section."""
        last_run = self.last_run_for_file
        if last_run and last_run.get("modules"):
            self.selected_modules = last_run["modules"].copy()
        self.new_analysis_expanded = True

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
        
        # Load basic metadata for all files (from filesystem)
        for filename in self.files:
            self._load_file_metadata(filename)
        
        # Load persisted metadata from Dagster (overwrites/merges with filesystem metadata)
        self._load_metadata_from_dagster()
        
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
            
            status = "uploaded"
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
            # Extract info from run config - use "ops" key (not "assets")
            config = run.run_config or {}
            ops_config = config.get("ops", {}).get("user_hf_module_annotations", {}).get("config", {})
            
            vcf_path = ops_config.get("vcf_path", "")
            filename = Path(vcf_path).name if vcf_path else "unknown"
            sample_name = ops_config.get("sample_name", "")
            modules = ops_config.get("modules", [])
            
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
                user_name = ops_config.get("user_name", self.safe_user_id)
                output_dir = root / "data" / "output" / "users" / user_name / sample_name / "modules"
                if output_dir.exists():
                    run_info["output_path"] = str(output_dir)
            
            run_list.append(run_info)
        
        self.runs = run_list
