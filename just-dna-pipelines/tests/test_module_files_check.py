"""Whether a module's files match its own manifest, and what the report says when they do not (RM7).

The modules are real compiled artifacts (the vendored phenotype specs, compiled at test time), so the
hashes and the digest are the compiler's own. Desk #92's default is built: a mismatch is a warning on
the module, at the top of its section and in "Modules in this report", and its results still show.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from just_dna_format.manifest import MARKETPLACE_COMPILED_BY

from phenotype_fixtures import compile_fixture, probe_local
from test_phenotype_report import _card, _run

from just_dna_pipelines.annotation.hf_modules import ModuleInfo, check_module_files, module_source
from just_dna_pipelines.annotation.report_logic import report_environment
from just_dna_pipelines.annotation.report_logic import TABLE_PREVIEW_ROWS

MODULE = "hfe_compound_het"
# The two sites test_phenotype_report reads as a phased C282Y / H63D pair.
HFE_RECORDS = [("6", 26092913, "G", "A", "0|1", 26090951), ("6", 26090951, "C", "G", "1|0", 26090951)]


@pytest.fixture(scope="module")
def compiled(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return compile_fixture(MODULE, tmp_path_factory.mktemp("compiled") / MODULE)


def _copy(compiled: Path, tmp_path: Path) -> Path:
    target = tmp_path / MODULE
    shutil.copytree(compiled, target)
    return target


def _manifest(module_dir: Path) -> dict:
    return json.loads((module_dir / "manifest.json").read_text(encoding="utf-8"))


def _write_manifest(module_dir: Path, manifest: dict) -> None:
    (module_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _artifact_names(module_dir: Path) -> list[str]:
    return [entry["name"] for entry in _manifest(module_dir)["artifact"]["files"]]


def _as_catalog_install(module_dir: Path, compiled_by: str | None) -> None:
    """What a registry download carries: the server's `published_at`, and its `compiled_by` stamp."""
    manifest = _manifest(module_dir)
    manifest["published_at"] = "2026-11-26T00:00:00Z"
    manifest.setdefault("compilation", {})["compiled_by"] = compiled_by
    _write_manifest(module_dir, manifest)


class TestCheckModuleFiles:
    def test_a_fresh_local_compile_matches(self, compiled: Path) -> None:
        info = probe_local(compiled, MODULE)
        assert module_source(info) == "local"
        assert check_module_files(info) == (True, "")

    @pytest.mark.parametrize("damage", ["appended", "truncated", "missing"])
    def test_every_artifact_file_is_checked(self, compiled: Path, tmp_path: Path, damage: str) -> None:
        names = _artifact_names(compiled)
        assert len(names) > 1
        for index, name in enumerate(names):
            module_dir = _copy(compiled, tmp_path / f"{damage}{index}")
            path = module_dir / name
            if damage == "appended":
                path.write_bytes(path.read_bytes() + b"\x00")
            elif damage == "truncated":
                path.write_bytes(path.read_bytes()[:-1])
            else:
                path.unlink()
            ok, reason = check_module_files(probe_local(module_dir, MODULE))
            assert ok is False, name
            assert name in reason

    def test_a_manifest_whose_digest_was_edited_does_not_match(self, compiled: Path, tmp_path: Path) -> None:
        module_dir = _copy(compiled, tmp_path)
        manifest = _manifest(module_dir)
        digest = manifest["artifact"]["digest"]
        manifest["artifact"]["digest"] = digest[:-1] + ("0" if digest[-1] != "0" else "1")
        _write_manifest(module_dir, manifest)
        ok, reason = check_module_files(probe_local(module_dir, MODULE))
        assert ok is False and "digest" in reason

    def test_a_catalog_install_must_say_the_registry_compiled_it(self, compiled: Path, tmp_path: Path) -> None:
        unstamped = _copy(compiled, tmp_path / "unstamped")
        _as_catalog_install(unstamped, None)
        info = probe_local(unstamped, MODULE)
        assert module_source(info) == "catalog"
        ok, reason = check_module_files(info)
        assert ok is False and "compiled_by" in reason

        stamped = _copy(compiled, tmp_path / "stamped")
        _as_catalog_install(stamped, MARKETPLACE_COMPILED_BY)
        info = probe_local(stamped, MODULE)
        assert module_source(info) == "catalog"
        assert check_module_files(info) == (True, "")

    def test_a_remote_module_is_not_checked(self) -> None:
        info = ModuleInfo(name="m", repo_id="org/repo", path="data/m",
                          lead_url="hf://datasets/org/repo/data/m/weights.parquet")
        ok, reason = check_module_files(info)
        assert ok is None and reason
        assert check_module_files(None)[0] is None

    def test_no_manifest_or_an_unreadable_one_is_not_checked(self, compiled: Path, tmp_path: Path) -> None:
        module_dir = _copy(compiled, tmp_path / "unreadable")
        info = probe_local(module_dir, MODULE)
        (module_dir / "manifest.json").write_text("{not json", encoding="utf-8")
        ok, reason = check_module_files(info)
        assert ok is None and "could not be read" in reason
        (module_dir / "manifest.json").unlink()
        ok, reason = check_module_files(info)
        assert ok is None and "no manifest.json" in reason


class TestTheReport:
    def test_an_intact_module_says_its_files_match_and_shows_no_warning(self, tmp_path, monkeypatch) -> None:
        html = _run(tmp_path, monkeypatch, [MODULE], HFE_RECORDS)
        assert "Files match" in html
        assert 'class="files-mismatch"' not in html

    def test_a_mismatch_warns_at_the_top_of_the_section_and_the_results_still_show(
        self, tmp_path, monkeypatch, compiled: Path
    ) -> None:
        # `_run` compiles into tmp_path/compiled/<module> unless the directory is already there; a
        # declared hash that no longer fits its file stands in for an edited file, and keeps the
        # parquet readable so the run can go on.
        module_dir = tmp_path / "compiled" / MODULE
        shutil.copytree(compiled, module_dir)
        manifest = _manifest(module_dir)
        manifest["artifact"]["files"][-1]["sha256"] = "sha256:" + "0" * 64
        _write_manifest(module_dir, manifest)
        monkeypatch.setattr("test_phenotype_report.compile_fixture", lambda name, out: out)

        html = _run(tmp_path, monkeypatch, [MODULE], HFE_RECORDS)

        section = html[html.index(f'id="module-{MODULE}"'):]
        warning = section.index('class="files-mismatch"')
        assert warning < section.index("<article", 1), "the warning comes before the results"
        assert "This module's files do not match its own fingerprint." in section
        assert manifest["artifact"]["files"][-1]["name"] in section[warning:]
        assert "Files do not match the module's fingerprint" in html
        # Warn and go on: the call is still made and shown.
        assert "One C282Y and one H63D change, on different copies" in _card(html, "HFE")


def _render(**context) -> str:
    ctx = {
        "report_title": "t", "report_description": "d", "preview_row_limit": TABLE_PREVIEW_ROWS,
        "user_name": "t", "sample_name": "s", "longevity": None, "other_modules": [],
        "pgx_modules": [], "phenotype_modules": [], "credits": [], "module_provenance": [],
        "module_exclusions": [], "module_display_names": {}, "umami_script_tag": "",
    }
    ctx.update(context)
    return report_environment().get_template("longevity_report.html.j2").render(**ctx)


def _provenance_row(name: str, files_match: bool | None, files_check: str = "") -> dict:
    return {"name": name, "display_name": name.title(), "version": "1.0.0", "digest": "sha256:ab",
            "digest_short": "ab", "lead_table": "weights", "weighting": "", "source_url": "",
            "files_match": files_match, "files_check": files_check}


@pytest.mark.parametrize(
    ("files_match", "label"),
    [(True, "Files match"), (False, "Files do not match the module's fingerprint"), (None, "Files not checked")],
)
def test_the_module_table_keeps_the_three_answers_apart(files_match: bool | None, label: str) -> None:
    html = _render(module_provenance=[_provenance_row("ünïcode_mod", files_match, "why")])
    assert label in html
    others = {"Files match", "Files do not match the module's fingerprint", "Files not checked"} - {label}
    assert not any(other in html for other in others)


@pytest.mark.parametrize("section", ["other_modules", "pgx_modules"])
def test_the_variant_and_drug_sections_carry_the_warning(section: str) -> None:
    mod = {"module_name": "m", "display_name": "M", "variants": [], "drugs": [],
           "summary": {"total_variants": 0, "directional": False, "weighted": False,
                       "total_positive": 0, "total_negative": 0, "total_weight": 0.0}}
    reason = "artifact hash mismatch for weights.parquet"
    html = _render(**{section: [mod]}, files_mismatch={"m": reason})
    start = html.index('id="module-m"')
    assert reason in html[start:html.index("</section>", start)]
    # No entry for the module, or no dict at all (a template caller from before RM7), means no warning.
    assert 'class="files-mismatch"' not in _render(**{section: [mod]}, files_mismatch={"other": reason})
    assert 'class="files-mismatch"' not in _render(**{section: [mod]})
