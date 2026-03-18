"""AIOA Runner — bridges the benchmark control plane with the AIOA pipeline.

Accepts a RunSpec from benchmark_control_arcade.run_models, invokes the
existing AIOA programmatic pipeline with the provided run_id, writes output
into a per-run subdirectory of output_dir, and returns a structured result.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from benchmark_control_arcade.run_models import RunSpec

# AIOA pipeline imports — aio-analyzer is an editable path dependency.
from src.input_layer import CompetitorConfig, Prompt, PromptSet, SearchTerm, TermSet
from src.pipeline import run_full_pipeline
from src.stores.json_store import JsonFileStore


async def run_aioa_benchmark(
    spec: RunSpec,
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Run an AIOA benchmark for the given spec.

    The pipeline output is written into *output_dir* / *run_id* /.
    A real JsonFileStore is wired up so artifacts land on disk.

    Returns a dict with at least:
    - run_id: str — the exact run_id that was passed in
    - artifacts: list[str] — relative paths written under output_dir / run_id
    - summary: dict — key metrics from the analysis
    """
    run_output_dir = Path(output_dir) / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)

    # Build a minimal PromptSet and TermSet from the spec.
    # The spec.options may carry custom prompts/terms; fall back to sensible defaults.
    target: str = spec.target
    competitors_list: list[str] = spec.options.get("competitors", [])
    competitor_config = CompetitorConfig(target=target, competitors=competitors_list)

    raw_prompts: list[dict] = spec.options.get("prompts", [])
    if raw_prompts:
        prompts = [
            Prompt(id=p.get("id", f"p{i}"), text=p["text"])
            for i, p in enumerate(raw_prompts)
        ]
    else:
        prompts = [
            Prompt(
                id="default_p1",
                text=f"What are the best tools for {target}?",
            )
        ]

    raw_terms: list[dict] = spec.options.get("terms", [])
    if raw_terms:
        terms = [
            SearchTerm(id=t.get("id", f"s{i}"), query=t["query"])
            for i, t in enumerate(raw_terms)
        ]
    else:
        terms = [
            SearchTerm(
                id="default_s1",
                query=target,
            )
        ]

    prompt_set = PromptSet(prompt_set_id=f"aioa-{run_id}", prompts=prompts)
    term_set = TermSet(term_set_id=f"aioa-{run_id}", terms=terms)

    store = JsonFileStore(workspace=run_output_dir)

    analysis = await run_full_pipeline(
        prompt_set=prompt_set,
        term_set=term_set,
        competitors=competitor_config,
        output_dir=run_output_dir,
        store=store,
        run_id=run_id,
    )

    # Collect artifacts: any files written under run_output_dir
    artifacts: list[str] = [
        str(p.relative_to(output_dir))
        for p in run_output_dir.rglob("*")
        if p.is_file()
    ]

    return {
        "run_id": run_id,
        "artifacts": sorted(artifacts),
        "summary": analysis.get("summary", {}),
    }
