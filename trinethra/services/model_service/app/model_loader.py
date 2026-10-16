# services/model_service/app/model_loader.py

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple, List



# repo root: .../trinethra/trinethra
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MODELS_DIR = os.getenv("MODELS_DIR", os.path.join(REPO_ROOT, "models"))


@dataclass
class LoadedModel:
    model_version: str
    threshold: float
    label: str
    feature_schema: List[str]
    categorical_columns: List[str]
    numeric_columns: List[str]
    preprocessor: Any
    booster: Any
    metrics: Dict[str, Any]


_loaded: LoadedModel | None = None


def _latest_metadata_path() -> str:
    paths = glob.glob(os.path.join(MODELS_DIR, "model_metadata_*.json"))
    if not paths:
        raise FileNotFoundError(f"No model_metadata_*.json found in {MODELS_DIR}")
    return sorted(paths)[-1]


def load_latest_model() -> LoadedModel:
    # Import inside the guarded prediction path so missing native libraries
    # degrade scoring rather than preventing the service from starting.
    import joblib

    global _loaded

    meta_path = _latest_metadata_path()
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    version = meta["model_version"]
    threshold = float(meta["threshold"])
    label = meta.get("label", "FraudFound_P")
    schema = meta.get("feature_schema", [])

    cat_cols = meta.get("categorical_columns", [])
    num_cols = meta.get("numeric_columns", [])

    model_path = os.path.join(MODELS_DIR, f"fraud_model_{version}.joblib")
    metrics_path = os.path.join(MODELS_DIR, f"metrics_{version}.json")

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Expected model file not found: {model_path}")

    metrics: Dict[str, Any] = {}
    if os.path.exists(metrics_path):
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

    # We saved a dict bundle: {"preprocessor": ..., "booster": ...}
    bundle = joblib.load(model_path)
    preprocessor = bundle["preprocessor"]
    booster = bundle["booster"]

    _loaded = LoadedModel(
        model_version=version,
        threshold=threshold,
        label=label,
        feature_schema=schema,
        categorical_columns=cat_cols,
        numeric_columns=num_cols,
        preprocessor=preprocessor,
        booster=booster,
        metrics=metrics,
    )
    return _loaded


def get_model() -> LoadedModel:
    global _loaded
    if _loaded is None:
        return load_latest_model()
    return _loaded


# -----------------------------
# Safe casting helpers
# -----------------------------
def _safe_int(x: Any, default: int) -> int:
    try:
        if x is None:
            return default
        return int(float(x))
    except Exception:
        return default


def _safe_float(x: Any, default: float) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _safe_str(x: Any, default: str) -> str:
    if x is None:
        return default
    s = str(x).strip()
    return s if s else default


# -----------------------------
# Adapter: Automation API -> Kaggle carclaims schema (32 cols)
# -----------------------------
def adapt_features_to_schema(features: Dict[str, Any], schema: List[str]) -> Dict[str, Any]:
    """
    Map the intake's age, previous_claims, police_report_filed, channel,
    and days_since_policy_start to the vehicle-claims training schema.
    Legacy police_report is also accepted. Unprovided attributes retain
    explicit defaults; these approximations require validation before use.
    """

    claim_type = _safe_str(features.get("claim_type", None), "OTHER").upper()
    police_report = features.get("police_report_filed", features.get("police_report"))
    channel = _safe_str(features.get("channel", None), "OTHER").upper()

    # VALID defaults (avoid None) so OHE doesn't crash
    base: Dict[str, Any] = {
        "Month": _safe_str(features.get("Month", None), "Jun"),
        "WeekOfMonth": _safe_int(features.get("WeekOfMonth", None), 2),
        "DayOfWeek": _safe_str(features.get("DayOfWeek", None), "Monday"),
        "Make": _safe_str(features.get("Make", None), "Other"),
        "AccidentArea": _safe_str(features.get("AccidentArea", None), "Urban"),
        "DayOfWeekClaimed": _safe_str(features.get("DayOfWeekClaimed", None), "Monday"),
        "MonthClaimed": _safe_str(features.get("MonthClaimed", None), "Jun"),
        "WeekOfMonthClaimed": _safe_int(features.get("WeekOfMonthClaimed", None), 2),
        "Sex": _safe_str(features.get("Sex", None), "Female"),
        "MaritalStatus": _safe_str(features.get("MaritalStatus", None), "Single"),
        "Age": _safe_int(features.get("age", features.get("Age")), 35),
        "Fault": _safe_str(features.get("Fault", None), "Policy Holder"),
        "PolicyType": _safe_str(features.get("PolicyType", None), "Sedan - All Perils"),
        "VehicleCategory": _safe_str(features.get("VehicleCategory", None), "Sedan"),
        "VehiclePrice": _safe_str(features.get("VehiclePrice", None), "20000 to 29000"),
        "PolicyNumber": _safe_int(features.get("PolicyNumber", None), 100000),
        "RepNumber": _safe_int(features.get("RepNumber", None), 1),
        "Deductible": _safe_int(features.get("Deductible", None), 500),
        "DriverRating": _safe_int(features.get("DriverRating", None), 3),
        "Days_Policy_Accident": _safe_str(features.get("Days_Policy_Accident", None), "more than 30"),
        "Days_Policy_Claim": _safe_str(features.get("Days_Policy_Claim", None), "more than 30"),
        "PastNumberOfClaims": _safe_str(features.get("PastNumberOfClaims", None), "none"),
        "AgeOfVehicle": _safe_str(features.get("AgeOfVehicle", None), "3 years"),
        "AgeOfPolicyHolder": _safe_str(features.get("AgeOfPolicyHolder", None), "26 to 30"),
        "PoliceReportFiled": _safe_str(features.get("PoliceReportFiled", None), "No"),
        "WitnessPresent": _safe_str(features.get("WitnessPresent", None), "No"),
        "AgentType": _safe_str(features.get("AgentType", None), "External"),
        "NumberOfSuppliments": _safe_str(features.get("NumberOfSuppliments", None), "none"),
        "AddressChange_Claim": _safe_str(features.get("AddressChange_Claim", None), "no change"),
        "NumberOfCars": _safe_str(features.get("NumberOfCars", None), "1 vehicle"),
        "Year": _safe_int(features.get("Year", None), 1996),
        "BasePolicy": _safe_str(features.get("BasePolicy", None), "All Perils"),
    }

    # Map police_report -> PoliceReportFiled
    if police_report is True:
        base["PoliceReportFiled"] = "Yes"
    elif police_report is False:
        base["PoliceReportFiled"] = "No"

    # Map channel -> AgentType (DIRECT -> Internal, PARTNER -> External)
    if channel in {"DIRECT", "ONLINE", "CALL CENTER"}:
        base["AgentType"] = "Internal"
    elif "channel" in features:
        base["AgentType"] = "External"

    # Form fields mapped to the training dataset's categorical values.
    if "previous_claims" in features:
        count = _safe_int(features["previous_claims"], 0)
        base["PastNumberOfClaims"] = ("none" if count == 0 else "1" if count == 1
                                      else "2 to 4" if count <= 4 else "more than 4")
    if "days_since_policy_start" in features:
        days = _safe_int(features["days_since_policy_start"], 0)
        base["Days_Policy_Accident"] = ("none" if days == 0 else "1 to 7" if days <= 7
                                          else "8 to 15" if days <= 15
                                          else "15 to 30" if days <= 30 else "more than 30")
    if "age" in features:
        age = _safe_int(features["age"], 35)
        base["AgeOfPolicyHolder"] = ("16 to 17" if age < 18 else "18 to 20" if age <= 20
                                      else "21 to 25" if age <= 25 else "26 to 30" if age <= 30
                                      else "31 to 35" if age <= 35 else "36 to 40" if age <= 40
                                      else "41 to 50" if age <= 50 else "51 to 65" if age <= 65
                                      else "over 65")

    # Amount is not vehicle value or deductible: retain explicit values/defaults.
    # Do not manufacture vehicle attributes from claim amount.
    # Map claim_type -> BasePolicy / PolicyType
    if "THEFT" in claim_type:
        base["BasePolicy"] = "Theft"
        base["PolicyType"] = "Sedan - Theft"
        base["Fault"] = "Third Party"
        base["WitnessPresent"] = "No"
    elif "COLLISION" in claim_type:
        base["BasePolicy"] = "Collision"
        base["PolicyType"] = "Sedan - Collision"

    # Return exactly schema columns (no missing keys)
    row: Dict[str, Any] = {}
    for col in schema:
        if col in base:
            row[col] = base[col]
        else:
            row[col] = _safe_str(features.get(col, None), "Unknown")

    return row


def predict_risk(features: Dict[str, Any]) -> Tuple[float, float, str]:
    """
    Returns (risk_signal, threshold, model_version)
    """
    import pandas as pd
    import xgboost as xgb

    m = get_model()

    row = adapt_features_to_schema(features, m.feature_schema)
    X = pd.DataFrame([row])

    # IMPORTANT: ensure categorical cols are strings and not None
    for c in m.categorical_columns:
        if c in X.columns:
            X[c] = X[c].astype("string").fillna("MISSING")

    # Ensure numeric cols are numeric (coerce errors)
    for c in m.numeric_columns:
        if c in X.columns:
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)

    try:
        Xt = m.preprocessor.transform(X)
        dmat = xgb.DMatrix(Xt)
        proba = float(m.booster.predict(dmat)[0])
        return proba, float(m.threshold), m.model_version
    except Exception as e:
        raise RuntimeError(
            f"predict failed. schema_cols={len(m.feature_schema)} "
            f"input_cols={list(X.columns)} row_sample={row} err={repr(e)}"
        )