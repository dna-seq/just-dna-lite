"""The By-Trait selector's grouping axis, and the page build that a missing var breaks.

prs-ui 0.3.17 added `trait_group_by_control` to `trait_selector` and bound it to a
`trait_group_by` var. `PRSTraitState` is hand-rolled here rather than inherited from
`PRSComputeStateMixin` — compute stays on `PRSState`, this state only selects traits and
syncs PGS IDs — so nothing gave it that var, and the whole app failed to compile with
`AttributeError: type object 'PRSTraitState' has no attribute 'trait_group_by'`. A page that
cannot be built is not a degraded page; it is no app at all, and neither the type checker nor
any existing test looked at it.
"""

from __future__ import annotations

import inspect
import re

import polars as pl
import pytest
from prs_ui.components.prs_section import trait_group_by_control
from prs_ui.mixin import TRAIT_GROUP_BY_ONTOLOGY, TRAIT_GROUP_BY_REPORTED
from prs_ui.pages.traits import trait_selector

from webui.pages.faq import faq_page
from webui.pages.index import index_page
from webui.pages.modules import modules_page
from webui.state import PRSState, PRSTraitState


def _state_attrs_read_by(*functions) -> set[str]:
    """Every `state.<attr>` the given prs-ui component functions read.

    Derived from the installed library at run time rather than listed here, so the next
    control prs-ui adds to the trait selector is checked against our state on the first run
    after the upgrade instead of at the user's next `uv run start`.
    """
    source = "".join(inspect.getsource(fn) for fn in functions)
    return set(re.findall(r"\bstate\.([a-z_][a-z0-9_]*)", source))


@pytest.mark.parametrize("page", [index_page, modules_page, faq_page], ids=lambda p: p.__name__)
def test_every_page_builds_the_way_the_compiler_builds_it(page) -> None:
    """Reflex's compiler builds a page by calling its function (`compiler.into_component`).

    So does this. Anything a component reads off a state class is resolved here, which is the
    whole class of failure that reaches a user as a traceback instead of a rendered page.
    """
    assert page() is not None


def test_the_trait_selector_reads_only_vars_our_trait_state_carries() -> None:
    required = _state_attrs_read_by(trait_selector, trait_group_by_control)

    # Not vacuous: the var whose absence broke the app is in the derived set, and a class
    # without it is flagged. A regex that matched nothing would pass the assertion below.
    assert "trait_group_by" in required

    class _StateWithoutIt:
        pass

    assert [a for a in sorted(required) if not hasattr(_StateWithoutIt, a)] == sorted(required)
    assert [a for a in sorted(required) if not hasattr(PRSTraitState, a)] == []


def test_both_states_start_on_the_same_grouping_axis() -> None:
    """`PRSState` takes its copy from `PRSComputeStateMixin` and groups *results* with it;
    `PRSTraitState` carries ours and groups the *selector*. One visible toggle drives both, so
    disagreeing defaults would mean the two halves of the tab group differently before anyone
    touches it."""
    assert PRSTraitState.__fields__["trait_group_by"].default == TRAIT_GROUP_BY_ONTOLOGY
    assert PRSState.__fields__["trait_group_by"].default == TRAIT_GROUP_BY_ONTOLOGY


def _record_builds(monkeypatch) -> list[tuple[str, bool, str]]:
    """Stand in for the catalog read, recording what each rebuild was asked for.

    `load_traits` is patched *through* rather than replaced: Reflex resolves a public method
    off the class's event-handler registry, so `monkeypatch.setattr(State, "load_traits", …)`
    is silently ignored and the real loader runs (measured — it read 1,550 traits out of the
    live PGS catalog). `_build_trait_df` is private, so it is an ordinary attribute and the
    patch holds; everything between it and the grid still runs for real.
    """
    builds: list[tuple[str, bool, str]] = []

    def fake_build(self, genome_build, include_harmonized=True):
        builds.append((genome_build, include_harmonized, self.trait_group_by))
        return pl.DataFrame({"trait": ["t"], "n_models": [1], "pgs_ids": ["PGS000001"]})

    monkeypatch.setattr(PRSTraitState, "_build_trait_df", fake_build)
    return builds


def test_switching_the_axis_reloads_the_grid_and_carries_the_choice_to_prsstate(monkeypatch) -> None:
    """The `trait` column *is* the group label, so both the grid's rows and `_trait_to_pgs` are
    keyed on names that do not exist after a switch. The selection is cleared by the reload and
    PRSState is told, or Compute would still hold the PGS IDs resolved under the old grouping —
    the one piece of stale state nothing on screen would show."""
    builds = _record_builds(monkeypatch)

    state = PRSTraitState(_reflex_internal_init=True)
    state.traits_loaded = True
    state._traits_genome_build = "GRCh37"
    state.prs_genotypes_path = "/data/sample/user_vcf_normalized.parquet"
    state._traits_include_harmonized = False

    emitted = list(state.set_trait_group_by(TRAIT_GROUP_BY_REPORTED))

    assert state.trait_group_by == TRAIT_GROUP_BY_REPORTED
    # rebuilt once, against the genome the grid was loaded for rather than a default, and with
    # the new axis already in place — a reload that read the old one would relabel nothing
    assert builds == [("GRCh37", False, TRAIT_GROUP_BY_REPORTED)]
    assert state.prs_genotypes_path == "/data/sample/user_vcf_normalized.parquet"
    # the selection is dropped, because those trait names no longer exist
    assert state.selected_traits == [] and state.selected_pgs_ids == []

    handlers = [e.handler.fn.__name__ for e in emitted if hasattr(e, "handler")]
    assert "set_trait_group_by" in handlers, "PRSState was not told, so results keep the old axis"
    assert "sync_trait_pgs_ids" in handlers, "Compute keeps PGS IDs resolved under the old axis"


def test_reselecting_the_same_axis_does_not_reload(monkeypatch) -> None:
    """A segmented control re-emits its current value; reloading on that would throw away a
    selection the user never asked to clear."""
    builds = _record_builds(monkeypatch)

    state = PRSTraitState(_reflex_internal_init=True)
    state.traits_loaded = True

    assert list(state.set_trait_group_by(TRAIT_GROUP_BY_ONTOLOGY)) == []
    assert builds == []


def test_the_axis_is_remembered_before_the_grid_has_ever_loaded(monkeypatch) -> None:
    """Flipping the toggle while the traits are still loading must still be honoured — the
    value is what the next build groups on — but must not start a second build."""
    builds = _record_builds(monkeypatch)

    state = PRSTraitState(_reflex_internal_init=True)
    state.traits_loaded = False

    list(state.set_trait_group_by(TRAIT_GROUP_BY_REPORTED))

    assert state.trait_group_by == TRAIT_GROUP_BY_REPORTED
    assert builds == []


@pytest.mark.parametrize(
    "value, expected",
    [
        ("nonsense", TRAIT_GROUP_BY_ONTOLOGY),
        ("", TRAIT_GROUP_BY_ONTOLOGY),
        ([], TRAIT_GROUP_BY_ONTOLOGY),
        (["reported"], TRAIT_GROUP_BY_REPORTED),
        (TRAIT_GROUP_BY_REPORTED, TRAIT_GROUP_BY_REPORTED),
    ],
)
def test_an_unusable_value_falls_back_to_the_mapped_ontology(value, expected) -> None:
    """The control is a segmented control today and a radio group's `list[str]` tomorrow;
    `normalize_trait_group_by` is prs-ui's own leaf and decides, so the axis is always a member
    of the vocabulary rather than whatever the widget sent."""
    state = PRSTraitState(_reflex_internal_init=True)
    list(state.set_trait_group_by(value))
    assert state.trait_group_by == expected
