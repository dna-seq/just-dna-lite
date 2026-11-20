"""Fetch a prediction model's files from HuggingFace into the pipelines cache, file by file.

Never ``snapshot_download`` (it duplicates every file into the HF blob store). Each file is fetched
with ``HfFileSystem.get`` at the model's pinned revision into
``<JUST_DNA_PIPELINES_CACHE_DIR>/models/<repo_id>/<revision>/``, and a file already there with the
size the repository reports is kept.
"""

from pathlib import Path

from eliot import log_message, start_action
from huggingface_hub import HfFileSystem, get_token

from just_dna_pipelines.annotation.resources import get_cache_dir
from just_dna_pipelines.predictions.models import PredictionModel


def model_dir(model: PredictionModel, cache_dir: Path | None = None) -> Path:
    """Where this model's files live for its pinned revision (may not exist yet)."""
    base = cache_dir if cache_dir is not None else get_cache_dir()
    return base / "models" / model.repo_id / model.revision


def model_files_present(model: PredictionModel, cache_dir: Path | None = None) -> bool:
    """True when every file the model needs is on disk (sizes are checked by ``ensure_model_files``)."""
    directory = model_dir(model, cache_dir)
    return all((directory / name).is_file() for name in model.files)


def ensure_model_files(model: PredictionModel, cache_dir: Path | None = None) -> Path:
    """Download whatever of the model's files is missing or the wrong size; return the directory."""
    directory = model_dir(model, cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    fs = HfFileSystem(token=get_token())
    with start_action(
        action_type="prediction_model_download", model=model.id, revision=model.revision, dest=str(directory)
    ):
        for name in model.files:
            remote = f"{model.repo_id}@{model.revision}/{name}"
            local = directory / name
            expected = int(fs.info(remote)["size"])
            if local.is_file() and local.stat().st_size == expected:
                continue
            partial = local.with_name(local.name + ".downloading")
            partial.unlink(missing_ok=True)
            fs.get(remote, str(partial))
            partial.replace(local)
            log_message(message_type="prediction_model_file_fetched", file=name, bytes=expected)
    return directory
