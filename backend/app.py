from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, request, send_from_directory
import numpy as np
from werkzeug.utils import secure_filename

from analytics.sensitivity import run_lapse_sensitivity
from analytics.stochastic import run_stochastic_npv
from data_loader import load_mortality_data
from engine import LifePolicy, MarginOptimizer
from models.vasicek import VasicekParams


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"
SETTINGS_PATH = BACKEND_DIR / "settings.yaml"

ALLOWED_EXTENSIONS = {".xlsx"}

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")

_CACHE: dict[str, dict] = {}
_CACHE_ORDER: list[str] = []
_CACHE_MAX = 128


def load_config() -> dict:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def list_data_files() -> list[str]:
    files = []
    if DATA_DIR.exists():
        files.extend(sorted([p.name for p in DATA_DIR.glob("*.xlsx")]))
    if UPLOAD_DIR.exists():
        files.extend(sorted([f"uploads/{p.name}" for p in UPLOAD_DIR.glob("*.xlsx")]))
    return files


def _validate_lapse_vector(lapse_vector: list[float], projection_years: int) -> None:
    if len(lapse_vector) != projection_years:
        raise ValueError(
            f"lapse_vector length ({len(lapse_vector)}) must match projection_years ({projection_years})"
        )


def _coerce_inputs(base: dict, overrides: dict[str, Any]) -> dict:
    merged = json.loads(json.dumps(base))
    for key, value in overrides.items():
        if key == "expenses" and isinstance(value, dict):
            merged.setdefault("expenses", {})
            merged["expenses"].update(value)
        else:
            merged[key] = value
    return merged


def _validate_assumptions(assumptions: dict) -> None:
    required = [
        "age",
        "premium",
        "claims_amount",
        "policyholder_count",
        "projection_years",
        "interest_rate",
        "lapse_vector",
        "expenses",
        "inflation_rate",
    ]
    missing = [key for key in required if key not in assumptions]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    if "commission" not in assumptions["expenses"] or "maintenance" not in assumptions["expenses"]:
        raise ValueError("expenses must include commission and maintenance")

    _validate_lapse_vector(assumptions["lapse_vector"], assumptions["projection_years"])


def _serialize_array(arr) -> list[float]:
    return [float(x) for x in arr]


def _make_cache_key(endpoint: str, payload: dict) -> str:
    return f"{endpoint}:{json.dumps(payload, sort_keys=True, default=str)}"


def _cache_get(key: str) -> dict | None:
    return _CACHE.get(key)


def _cache_set(key: str, value: dict) -> None:
    if key in _CACHE:
        return
    _CACHE[key] = value
    _CACHE_ORDER.append(key)
    if len(_CACHE_ORDER) > _CACHE_MAX:
        oldest = _CACHE_ORDER.pop(0)
        _CACHE.pop(oldest, None)


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/products")
def api_products():
    config = load_config()
    return jsonify({"products": config})


@app.route("/api/data-files")
def api_data_files():
    return jsonify({"files": list_data_files()})


@app.route("/api/products", methods=["POST"])
def api_save_product():
    payload = request.get_json(silent=True) or {}
    product_key = payload.get("product_key")
    assumptions = payload.get("assumptions")
    overwrite = bool(payload.get("overwrite", False))

    if not product_key:
        return jsonify({"error": "product_key is required"}), 400
    if not assumptions:
        return jsonify({"error": "assumptions are required"}), 400

    config = load_config()
    if product_key in config and not overwrite:
        return jsonify({"error": f"Product already exists: {product_key}"}), 409

    try:
        _validate_assumptions(assumptions)
        config[product_key] = assumptions
        save_config(config)
        return jsonify({"products": config})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "Missing file field"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Only .xlsx files are allowed"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename)
    dest = UPLOAD_DIR / safe_name
    file.save(dest)

    return jsonify({"uploaded": f"uploads/{safe_name}", "files": list_data_files()})


@app.route("/api/run", methods=["POST"])
def api_run():
    payload = request.get_json(silent=True) or {}

    product_key = payload.get("product_key", "product_A")
    inputs = payload.get("inputs", {})
    mortality_file = payload.get("mortality_file")
    sheet_name = payload.get("sheet_name", "Sheet1")

    config = load_config()
    if product_key not in config:
        return jsonify({"error": f"Unknown product_key: {product_key}"}), 400

    if not mortality_file:
        return jsonify({"error": "mortality_file is required"}), 400

    file_path = DATA_DIR / mortality_file
    if mortality_file.startswith("uploads/"):
        file_path = DATA_DIR / mortality_file

    if not file_path.exists():
        return jsonify({"error": f"Data file not found: {mortality_file}"}), 404

    try:
        assumptions = _coerce_inputs(config[product_key], inputs)
        _validate_assumptions(assumptions)

        mortality_lookup = load_mortality_data(str(file_path), sheet_name)
        policy = LifePolicy(mortality_lookup, assumptions)
        policy.run()
        metrics = policy.summary_metrics(verbose=False)

        st = policy.final_state
        projection = {
            "years": list(range(1, st.term + 1)),
            "premiums": _serialize_array(st.premiums),
            "claims": _serialize_array(st.claims),
            "expenses": _serialize_array(st.expenses),
            "net_cashflow": _serialize_array(st.net_cashflow),
            "pv_cashflow": _serialize_array(st.pv_cashflow),
        }

        return jsonify({"metrics": metrics, "projection": projection})

    except Exception as exc:  # noqa: BLE001 - return message to UI
        return jsonify({"error": str(exc)}), 400


@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    payload = request.get_json(silent=True) or {}

    product_key = payload.get("product_key", "product_A")
    inputs = payload.get("inputs", {})
    mortality_file = payload.get("mortality_file")
    sheet_name = payload.get("sheet_name", "Sheet1")
    target_margin = payload.get("target_margin")

    config = load_config()
    if product_key not in config:
        return jsonify({"error": f"Unknown product_key: {product_key}"}), 400

    if target_margin is None:
        return jsonify({"error": "target_margin is required"}), 400

    if not mortality_file:
        return jsonify({"error": "mortality_file is required"}), 400

    file_path = DATA_DIR / mortality_file
    if mortality_file.startswith("uploads/"):
        file_path = DATA_DIR / mortality_file

    if not file_path.exists():
        return jsonify({"error": f"Data file not found: {mortality_file}"}), 404

    try:
        assumptions = _coerce_inputs(config[product_key], inputs)
        _validate_assumptions(assumptions)

        mortality_lookup = load_mortality_data(str(file_path), sheet_name)
        policy = LifePolicy(mortality_lookup, assumptions)

        optimizer = MarginOptimizer(policy)
        optimal_premium = optimizer.solve_for_premium(target_margin=float(target_margin))
        if optimal_premium <= 0:
            raise ValueError("Optimization failed to find a valid premium.")

        policy.premium = optimal_premium
        policy.run()
        metrics = policy.summary_metrics(verbose=False)

        st = policy.final_state
        projection = {
            "years": list(range(1, st.term + 1)),
            "premiums": _serialize_array(st.premiums),
            "claims": _serialize_array(st.claims),
            "expenses": _serialize_array(st.expenses),
            "net_cashflow": _serialize_array(st.net_cashflow),
            "pv_cashflow": _serialize_array(st.pv_cashflow),
        }

        return jsonify({
            "metrics": metrics,
            "projection": projection,
            "optimal_premium": optimal_premium,
        })

    except Exception as exc:  # noqa: BLE001 - return message to UI
        return jsonify({"error": str(exc)}), 400


@app.route("/api/sensitivity", methods=["POST"])
def api_sensitivity():
    payload = request.get_json(silent=True) or {}
    cache_key = _make_cache_key("sensitivity", payload)
    cached = _cache_get(cache_key)
    if cached is not None:
        return jsonify({"cached": True, **cached})

    product_key = payload.get("product_key", "product_A")
    inputs = payload.get("inputs", {})
    mortality_file = payload.get("mortality_file")
    sheet_name = payload.get("sheet_name", "Sheet1")
    modifiers = payload.get("lapse_modifiers", [])

    if not modifiers:
        modifiers = [round(x, 2) for x in list(np.arange(0.5, 1.6, 0.1))]

    config = load_config()
    if product_key not in config:
        return jsonify({"error": f"Unknown product_key: {product_key}"}), 400

    if not mortality_file:
        return jsonify({"error": "mortality_file is required"}), 400

    file_path = DATA_DIR / mortality_file
    if mortality_file.startswith("uploads/"):
        file_path = DATA_DIR / mortality_file

    if not file_path.exists():
        return jsonify({"error": f"Data file not found: {mortality_file}"}), 404

    try:
        assumptions = _coerce_inputs(config[product_key], inputs)
        _validate_assumptions(assumptions)

        mortality_lookup = load_mortality_data(str(file_path), sheet_name)
        results = run_lapse_sensitivity(mortality_lookup, assumptions, modifiers)

        response = {"results": results}
        _cache_set(cache_key, response)
        return jsonify(response)

    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


@app.route("/api/stochastic", methods=["POST"])
def api_stochastic():
    payload = request.get_json(silent=True) or {}
    cache_key = _make_cache_key("stochastic", payload)
    cached = _cache_get(cache_key)
    if cached is not None:
        return jsonify({"cached": True, **cached})

    product_key = payload.get("product_key", "product_A")
    inputs = payload.get("inputs", {})
    mortality_file = payload.get("mortality_file")
    sheet_name = payload.get("sheet_name", "Sheet1")
    n_simulations = int(payload.get("n_simulations", 1000))
    seed = payload.get("seed")
    max_paths = payload.get("max_paths", 200)

    vasicek_payload = payload.get("vasicek", {})
    r0 = float(vasicek_payload.get("r0", 0.05))
    kappa = float(vasicek_payload.get("kappa", 0.15))
    theta = float(vasicek_payload.get("theta", 0.04))
    sigma = float(vasicek_payload.get("sigma", 0.015))
    dt = float(vasicek_payload.get("dt", 1.0))

    config = load_config()
    if product_key not in config:
        return jsonify({"error": f"Unknown product_key: {product_key}"}), 400

    if not mortality_file:
        return jsonify({"error": "mortality_file is required"}), 400

    file_path = DATA_DIR / mortality_file
    if mortality_file.startswith("uploads/"):
        file_path = DATA_DIR / mortality_file

    if not file_path.exists():
        return jsonify({"error": f"Data file not found: {mortality_file}"}), 404

    try:
        assumptions = _coerce_inputs(config[product_key], inputs)
        _validate_assumptions(assumptions)

        mortality_lookup = load_mortality_data(str(file_path), sheet_name)
        T = int(assumptions["projection_years"])

        params = VasicekParams(r0=r0, kappa=kappa, theta=theta, sigma=sigma, T=T, dt=dt)
        output = run_stochastic_npv(
            mortality_lookup,
            assumptions,
            params,
            n_simulations=n_simulations,
            seed=seed,
            max_paths=max_paths,
        )

        response = {"stochastic": output}
        _cache_set(cache_key, response)
        return jsonify(response)

    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(debug=True)
