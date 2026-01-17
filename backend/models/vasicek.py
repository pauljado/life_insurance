from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class VasicekParams:
    r0: float
    kappa: float
    theta: float
    sigma: float
    T: int
    dt: float = 1.0


class VasicekModel:
    def __init__(self, params: VasicekParams):
        self.params = params
        self.n_steps = int(params.T / params.dt)

    def generate_paths(self, n_paths: int, seed: Optional[int] = None) -> np.ndarray:
        params = self.params
        rates = np.zeros((n_paths, self.n_steps + 1))
        rates[:, 0] = params.r0

        rng = np.random.default_rng(seed)
        z = rng.normal(0, 1, (n_paths, self.n_steps))
        sqrt_dt = np.sqrt(params.dt)

        for t in range(self.n_steps):
            r_t = rates[:, t]
            drift = params.kappa * (params.theta - r_t) * params.dt
            shock = params.sigma * sqrt_dt * z[:, t]
            rates[:, t + 1] = r_t + drift + shock

        return rates
