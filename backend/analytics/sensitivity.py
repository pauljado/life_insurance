from __future__ import annotations

import copy
from typing import Iterable

from engine import LifePolicy


def _apply_lapse_modifier(assumptions: dict, modifier: float) -> dict:
    updated = copy.deepcopy(assumptions)
    updated["lapse_vector"] = [round(rate * modifier, 3) for rate in updated["lapse_vector"]]
    return updated


def run_lapse_sensitivity(mortality_map, assumptions: dict, modifiers: Iterable[float]) -> list[dict]:
    results: list[dict] = []
    for mod in modifiers:
        modified = _apply_lapse_modifier(assumptions, float(mod))
        policy = LifePolicy(mortality_map, modified)
        policy.run()
        metrics = policy.summary_metrics(verbose=False)
        results.append({
            "modifier": float(mod),
            "profit_margin": float(metrics["profit_margin"]),
            "npv": float(metrics["npv"]),
        })
    return results
