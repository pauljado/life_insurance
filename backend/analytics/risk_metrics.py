from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class TailMetrics:
    mean: float
    var_90: float
    var_95: float
    cte_90: float
    cte_95: float


def summarize_tail_metrics(npv_results: Iterable[float]) -> TailMetrics:
    npvs = np.array(list(npv_results), dtype=float)
    if npvs.size == 0:
        raise ValueError("npv_results must not be empty")

    sorted_npvs = np.sort(npvs)
    n_sims = len(sorted_npvs)

    cutoff_90 = max(int(n_sims * 0.10), 1)
    cutoff_95 = max(int(n_sims * 0.05), 1)

    var_90 = sorted_npvs[cutoff_90 - 1]
    var_95 = sorted_npvs[cutoff_95 - 1]

    cte_90 = float(np.mean(sorted_npvs[:cutoff_90]))
    cte_95 = float(np.mean(sorted_npvs[:cutoff_95]))

    return TailMetrics(
        mean=float(np.mean(npvs)),
        var_90=float(var_90),
        var_95=float(var_95),
        cte_90=cte_90,
        cte_95=cte_95,
    )
