"""Check a phenotype module's calls on a family for Mendelian consistency.

A family is ground truth that needs no outside source: a child inherits one allele from each parent,
so a mother O/O and a father B/O can only have B/O or O/O children. This reads each person's
``{module}_phenotypes.parquet`` (written by the phenotype caller) and checks two levels:

* **sites**: at every defining position read in the child and both parents (called, or restored as
  reference), the child's two alleles must be one from each parent;
* **results**: for every gene, some consistent diplotype of the child must be buildable from one
  haplotype of a consistent diplotype of the mother and one of the father.

A position or gene that could not be read in any of the three is reported **unchecked**, never as a
pass. A violation means a wrong call, a sample swap, or non-paternity; the report says which sites
and genes, and deciding which is the reader's job.

Usage::

    uv run python scripts/family_check.py blood_groups --mother anonymous/mom --father anonymous/dad \\
        --child anonymous/son1 --child anonymous/son2 --child anonymous/daughter3
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Annotated

import polars as pl
import typer
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.runtime import load_env

app = typer.Typer(add_completion=False)
console = Console()


def _calls(sample_id: str, module: str) -> dict[str, dict]:
    """The phenotype calls of one person, keyed by gene."""
    path = get_user_output_dir() / sample_id / "modules" / f"{module}_phenotypes.parquet"
    if not path.exists():
        raise typer.BadParameter(f"no phenotype calls for {sample_id}: {path} (run the module on this sample first)")
    return {row["gene"]: row for row in pl.read_parquet(path).iter_rows(named=True)}


def _site_genotypes(call: dict) -> dict[str, list[str] | None]:
    """Per defining site, the two alleles read (called or restored), or None when not read."""
    return {
        f"{s['rsid'] or ''}@{s['chrom']}:{s['start']}": (sorted(s["observed"]) if s["observed"] else None)
        for s in call["sites"]
    }


def _mendelian(child: list[str], mother: list[str], father: list[str]) -> bool:
    """True when the child's two alleles can be one from the mother and one from the father."""
    a, b = child
    return (a in mother and b in father) or (b in mother and a in father)


def _pairs(call: dict) -> list[tuple[str, str]]:
    return [(c["haplotype_a"], c["haplotype_b"]) for c in call["candidates"] if not c["not_assessable"]]


@app.command()
def check(
    module: Annotated[str, typer.Argument(help="Phenotype module name, e.g. blood_groups")],
    mother: Annotated[str, typer.Option(help="Sample id user/sample")],
    father: Annotated[str, typer.Option(help="Sample id user/sample")],
    child: Annotated[list[str], typer.Option(help="Sample id user/sample; repeat for each child")],
) -> None:
    load_env()
    mom, dad = _calls(mother, module), _calls(father, module)
    violations = 0
    table = Table(title=f"{module}: Mendelian consistency")
    for col in ("child", "gene", "level", "result", "detail"):
        table.add_column(col)

    for kid_id in child:
        kid = _calls(kid_id, module)
        for gene in sorted(kid):
            if gene not in mom or gene not in dad:
                table.add_row(kid_id, gene, "gene", "unchecked", "a parent has no call for this gene")
                continue
            # Sites.
            ks, ms, fs = _site_genotypes(kid[gene]), _site_genotypes(mom[gene]), _site_genotypes(dad[gene])
            for site, kg in ks.items():
                mg, fg = ms.get(site), fs.get(site)
                if kg is None or mg is None or fg is None:
                    table.add_row(kid_id, gene, f"site {site}", "unchecked", "not read in child or a parent")
                elif _mendelian(kg, mg, fg):
                    table.add_row(kid_id, gene, f"site {site}", "ok", f"child {'/'.join(kg)} from {'/'.join(mg)} x {'/'.join(fg)}")
                else:
                    violations += 1
                    table.add_row(kid_id, gene, f"site {site}", "[red]VIOLATION[/red]", f"child {'/'.join(kg)} cannot come from {'/'.join(mg)} x {'/'.join(fg)}")
            # Results. Only firm calls in all three are a real test; an unresolved result is consistent
            # with almost anything, so it is reported as partial or unchecked rather than as a pass.
            statuses = {kid[gene]["status"], mom[gene]["status"], dad[gene]["status"]}
            if "not_assessable" in statuses or "no_match" in statuses:
                table.add_row(kid_id, gene, "result", "unchecked", "not readable from the file in the child or a parent")
                continue
            kp, mp, fp = _pairs(kid[gene]), _pairs(mom[gene]), _pairs(dad[gene])
            if not kp or not mp or not fp:
                table.add_row(kid_id, gene, "result", "unchecked", "no assessable diplotype for child or a parent")
                continue
            firm = statuses == {"called"}
            ok = any(
                sorted(k) == sorted([m_hap, f_hap])
                for k, m, f in product(kp, mp, fp)
                for m_hap in m for f_hap in f
            )
            summary = f"child {kid[gene]['phenotype'] or kid[gene]['status']} from {mom[gene]['phenotype'] or mom[gene]['status']} x {dad[gene]['phenotype'] or dad[gene]['status']}"
            if ok:
                table.add_row(kid_id, gene, "result", "ok" if firm else "consistent (partial)", summary)
            else:
                violations += 1
                table.add_row(kid_id, gene, "result", "[red]VIOLATION[/red]", summary)

    console.print(table)
    if violations:
        console.print(f"[red]{violations} Mendelian violation(s).[/red] A wrong call, a sample swap or non-paternity; check the sites listed.")
        raise typer.Exit(1)
    console.print("[green]No Mendelian violations.[/green] Unchecked rows are not passes: they were not readable in everyone.")


if __name__ == "__main__":
    app()
