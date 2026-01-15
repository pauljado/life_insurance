from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from data_loader import load_mortality_data
from engine import LifePolicy


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
FRONTEND_DIR = BASE_DIR / "frontend"
SETTINGS_PATH = BACKEND_DIR / "settings.yaml"

ALLOWED_EXTENSIONS = {".xlsx"}

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")


def load_config() -> dict:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def _serialize_array(arr) -> list[float]:
    return [float(x) for x in arr]


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
        _validate_lapse_vector(assumptions["lapse_vector"], assumptions["projection_years"])

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


if __name__ == "__main__":
    app.run(debug=True)
