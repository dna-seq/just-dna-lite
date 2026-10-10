"""`manuscript s4 snapshot`: record the registry's answers for one namespace at one moment.

Read-only: it lists the namespace, reads each module's versions and manifest, downloads the latest
non-yanked version (artifact, build logs, logo) into a work directory and verifies it, and reads the
legacy HuggingFace mirror's manifests for comparison. It never publishes, yanks or writes to the
registry, and it sends no token: every call it makes is a public read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from huggingface_hub import HfFileSystem

from just_dna_lite.manuscript.s4 import MANIFEST, Snapshot, SnapshotModule
from just_dna_pipelines.module_config import MODULES_CONFIG, RegistryStore
from just_dna_pipelines.runtime import environ_guard, load_env

load_env()  # REGISTRY_URL from this checkout's .env decides the default store
# just-dna-registry calls a bare load_dotenv() at import; the guard keeps only our own configuration.
with environ_guard():
    from just_dna_registry import RegistryClient

PER_PAGE = 100


def _all_pages(fetch) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        result = fetch(page)
        items += result["items"]
        if page * result["per_page"] >= result["total"]:
            return items
        page += 1


def mirror_manifests() -> tuple[Optional[str], dict[str, dict]]:
    """`(repo_id, {module: manifest dict})` for the first HuggingFace source in modules.yaml."""
    repo_id = next((source.hf_repo_id for source in MODULES_CONFIG.sources if source.is_hf and source.hf_repo_id), None)
    if repo_id is None:
        return None, {}
    fs = HfFileSystem(token=False)  # a public dataset: send no credential, as for the registry
    found: dict[str, dict] = {}
    for path in fs.glob(f"datasets/{repo_id}/data/*/{MANIFEST}"):
        found[Path(path).parent.name] = json.loads(fs.read_text(path))
    return repo_id, found


def take_snapshot(store: RegistryStore, namespace: str, work_dir: Path, *, mirror: bool) -> Snapshot:
    """List `namespace` on `store`, download each latest version into `work_dir/<name>`, record it all."""
    with RegistryClient(store.base_url, None) as client:
        server = client.server_version()
        as_of = datetime.now(timezone.utc)
        cards = _all_pages(lambda page: client.list_modules(namespace=namespace, per_page=PER_PAGE, page=page))
        modules: list[SnapshotModule] = []
        for card in sorted(cards, key=lambda c: c["name"]):
            name = card["name"]
            versions = _all_pages(lambda page: client.versions(namespace, name, page=page, per_page=PER_PAGE))
            live = [v for v in versions if not v["yanked"]]
            latest = card["latest_version"]
            entry = next(v for v in live if v["version"] == latest)
            manifest = client.download(namespace, name, latest, work_dir / name, include_logs=True)
            modules.append(
                SnapshotModule(
                    name=name,
                    latest_version=latest,
                    published_at=manifest.published_at,
                    artifact_digest=entry["artifact_digest"],
                    content_signature=entry.get("content_signature"),
                    versions=[v["version"] for v in versions],
                    yanked_versions=[v["version"] for v in versions if v["yanked"]],
                )
            )
    repo_id, mirrored = mirror_manifests() if mirror else (None, {})
    modules = [
        m.model_copy(update={
            "mirror_version": mirrored[m.name]["identity"]["version"],
            "mirror_digest": mirrored[m.name]["artifact"]["digest"],
        }) if m.name in mirrored else m
        for m in modules
    ]
    return Snapshot(
        as_of=as_of,
        registry_key=store.key,
        registry_url=store.base_url,
        registry_version=server.registry if server else None,
        format_version=server.format if server else None,
        namespace=namespace,
        mirror_repo=repo_id,
        modules=modules,
    )
