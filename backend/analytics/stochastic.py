from __future__ import annotations

from typing import Optional

import numpy as np

from analytics.risk_metrics import TailMetrics, summarize_tail_metrics
from engine import LifePolicy
from models.vasicek import VasicekModel, VasicekParams


def run_stochastic_npv(
    mortality_map,
    assumptions: dict,
    vasicek_params: VasicekParams,
    n_simulations: int = 1000,
    seed: Optional[int] = None,
    max_paths: Optional[int] = 200,
) -> dict:
    model = VasicekModel(vasicek_params)
    rate_paths = model.generate_paths(n_simulations, seed=seed)

    npvs = np.empty(n_simulations, dtype=float)

    for i in range(n_simulations):
        path = rate_paths[i, :]
        sim_assumptions = dict(assumptions)
        sim_assumptions["interest_rate"] = path
        policy = LifePolicy(mortality_map, sim_assumptions)
        policy.run()
        npvs[i] = float(policy.summary_metrics(verbose=False)["npv"])

    metrics: TailMetrics = summarize_tail_metrics(npvs)

    years = list(range(0, rate_paths.shape[1]))
    mean_path = rate_paths.mean(axis=0)
    p05 = np.percentile(rate_paths, 5, axis=0)
    p95 = np.percentile(rate_paths, 95, axis=0)

    if max_paths is not None and rate_paths.shape[0] > max_paths:
        rate_paths_out = rate_paths[:max_paths]
    else:
        rate_paths_out = rate_paths

    return {
        "npvs": npvs.tolist(),
        "tail_metrics": {
            "mean": metrics.mean,
            "var_90": metrics.var_90,
            "var_95": metrics.var_95,
            "cte_90": metrics.cte_90,
            "cte_95": metrics.cte_95,
        },
        "rate_paths": rate_paths_out.tolist(),
        "rate_path_summary": {
            "years": years,
            "mean": mean_path.tolist(),
            "p05": p05.tolist(),
            "p95": p95.tolist(),
        },
    }
