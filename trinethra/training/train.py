import argparse
import json
import os
from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd
import xgboost as xgb

from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer

import joblib


def pick_threshold_under_fpr(y_true: np.ndarray, y_proba: np.ndarray, max_fpr: float) -> float:
    fpr, tpr, thr = roc_curve(y_true, y_proba)
    valid = np.where(fpr <= max_fpr)[0]
    if len(valid) == 0:
        return float(0.99)
    best_idx = valid[np.argmax(tpr[valid])]
    return float(thr[best_idx])


def metrics_at_threshold(y_true: np.ndarray, y_proba: np.ndarray, thr: float) -> Dict[str, float]:
    y_pred = (y_proba >= thr).astype(int)

    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0

    return {
        "precision": float(precision),
        "recall": float(recall),
        "fpr": float(fpr),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to carclaims.csv")
    parser.add_argument("--label", default="FraudFound_P", help="Target label column")
    parser.add_argument("--max_fpr", type=float, default=0.05, help="FPR budget")
    parser.add_argument("--version", default=None, help="Model version (default: timestamp)")
    args = parser.parse_args()

    df = pd.read_csv(args.data)

    if args.label not in df.columns:
        raise ValueError(
            f"Label column '{args.label}' not found. Found columns like: {list(df.columns)[:30]}"
        )

    y = df[args.label].astype(int).values
    X = df.drop(columns=[args.label])

    cat_cols = [c for c in X.columns if X[c].dtype == "object"]
    num_cols = [c for c in X.columns if c not in cat_cols]

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    scale_pos_weight = (neg / pos) if pos > 0 else 1.0

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", "passthrough", num_cols),
        ]
    )

    # Fit preprocessor and transform splits
    preprocessor.fit(X_train)
    X_train_t = preprocessor.transform(X_train)
    X_val_t = preprocessor.transform(X_val)
    X_test_t = preprocessor.transform(X_test)

    dtrain = xgb.DMatrix(X_train_t, label=y_train)
    dval = xgb.DMatrix(X_val_t, label=y_val)
    dtest = xgb.DMatrix(X_test_t, label=y_test)

    params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 5,
        "eta": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "lambda": 1.0,
        "scale_pos_weight": scale_pos_weight,
        "seed": 42,
    }

    booster = xgb.train(
        params=params,
        dtrain=dtrain,
        num_boost_round=2000,
        evals=[(dval, "val")],
        early_stopping_rounds=30,
        verbose_eval=False,
    )

    # Predict on test
    proba_test = booster.predict(dtest)

    roc_auc = float(roc_auc_score(y_test, proba_test))
    pr_auc = float(average_precision_score(y_test, proba_test))

    thr = pick_threshold_under_fpr(y_test, proba_test, args.max_fpr)
    thr_metrics = metrics_at_threshold(y_test, proba_test, thr)

    version = args.version or datetime.utcnow().strftime("v%Y%m%d_%H%M%S")

    os.makedirs("../models", exist_ok=True)

    model_path = f"../models/fraud_model_{version}.joblib"
    metrics_path = f"../models/metrics_{version}.json"
    meta_path = f"../models/model_metadata_{version}.json"

    # Save bundle: preprocessor + booster
    model_bundle = {"preprocessor": preprocessor, "booster": booster}
    joblib.dump(model_bundle, model_path)

    metrics = {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "max_fpr": args.max_fpr,
        "threshold": thr,
        **thr_metrics,
    }

    metadata = {
        "model_version": version,
        "threshold": thr,
        "label": args.label,
        "created_utc": datetime.utcnow().isoformat() + "Z",
        "categorical_columns": cat_cols,
        "numeric_columns": num_cols,
        "feature_schema": list(X.columns),
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Training complete: {version}")
    print(f"Saved model:   {model_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Saved meta:    {meta_path}")
    print(f"ROC AUC: {roc_auc:.4f} | PR AUC: {pr_auc:.4f} | Thr: {thr:.4f} | FPR: {metrics['fpr']:.4f}")
    print(f"Precision: {metrics['precision']:.4f} | Recall: {metrics['recall']:.4f}")
    print(f"Fraud rate (train): {pos/(pos+neg):.4%} | scale_pos_weight: {scale_pos_weight:.2f}")


if __name__ == "__main__":
    main()