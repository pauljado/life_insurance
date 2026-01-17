import argparse
import os
import sys
import yaml

import numpy as np


sys.path.append(os.path.join(os.path.dirname(__file__)))

from analytics.sensitivity import run_lapse_sensitivity
from analytics.stochastic import run_stochastic_npv
from data_loader import load_mortality_data
from engine import MarginOptimizer, LifePolicy  # Import LifePolicy
from models.vasicek import VasicekParams


current_dir = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(current_dir, "settings.yaml")

with open(settings_path, "r") as f:
    config = yaml.safe_load(f)


def _load_policy(product_key: str, mortality_file: str, sheet_name: str) -> LifePolicy:
    mortality_lookup = load_mortality_data(mortality_file, sheet_name)
    return LifePolicy(mortality_lookup, config[product_key])


def run_policy(product_key: str, mortality_file: str, sheet_name: str) -> None:
    policy = _load_policy(product_key, mortality_file, sheet_name)
    policy.run()
    print(policy.summary_metrics(verbose=True))


def run_optimization(product_key: str, mortality_file: str, sheet_name: str, target_margin: float) -> None:
    policy = _load_policy(product_key, mortality_file, sheet_name)
    optimizer = MarginOptimizer(policy)
    best_premium = optimizer.solve_for_premium(target_margin=target_margin)
    print(f"Optimal Premium: {best_premium}")


def run_sensitivity(product_key: str, mortality_file: str, sheet_name: str) -> None:
    mortality_lookup = load_mortality_data(mortality_file, sheet_name)
    assumptions = config[product_key]
    modifiers = [round(x, 2) for x in list(np.arange(0.5, 1.6, 0.1))]
    results = run_lapse_sensitivity(mortality_lookup, assumptions, modifiers)
    for row in results:
        print(
            f"Modifier {row['modifier']:.2f} -> Profit Margin {row['profit_margin']:.2%} | NPV {row['npv']:,.2f}"
        )


def run_stochastic(product_key: str, mortality_file: str, sheet_name: str, n_simulations: int) -> None:
    mortality_lookup = load_mortality_data(mortality_file, sheet_name)
    assumptions = config[product_key]
    params = VasicekParams(r0=0.05, kappa=0.15, theta=0.04, sigma=0.015, T=assumptions["projection_years"], dt=1.0)
    output = run_stochastic_npv(
        mortality_lookup,
        assumptions,
        params,
        n_simulations=n_simulations,
    )
    metrics = output["tail_metrics"]
    print(f"Mean NPV: {metrics['mean']:,.2f}")
    print(f"VaR 90%: {metrics['var_90']:,.2f}")
    print(f"CTE 90%: {metrics['cte_90']:,.2f}")
    print(f"CTE 95%: {metrics['cte_95']:,.2f}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Life insurance pricing engine")
    parser.add_argument("--product", default="product_B")
    parser.add_argument("--mortality-file", default="VBT_2015.xlsx")
    parser.add_argument("--sheet", default="Sheet1")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run")

    optimize_parser = subparsers.add_parser("optimize")
    optimize_parser.add_argument("--target-margin", type=float, default=0.07)

    subparsers.add_parser("sensitivity")

    stochastic_parser = subparsers.add_parser("stochastic")
    stochastic_parser.add_argument("--n-simulations", type=int, default=1000)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command or args.command == "run":
        run_policy(args.product, args.mortality_file, args.sheet)
        return

    if args.command == "optimize":
        run_optimization(args.product, args.mortality_file, args.sheet, args.target_margin)
        return

    if args.command == "sensitivity":
        run_sensitivity(args.product, args.mortality_file, args.sheet)
        return

    if args.command == "stochastic":
        run_stochastic(args.product, args.mortality_file, args.sheet, args.n_simulations)
        return


if __name__ == "__main__":
    main()