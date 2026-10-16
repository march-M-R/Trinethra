"""Run: python -m unittest discover -s tests -v"""
import importlib
import importlib.util
from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


automation = load("automation_main", "trinethra/services/automation_api/app/main.py")
explain = load("explain_main", "trinethra/services/explain_service/app/main.py")
loader = load("model_loader", "trinethra/services/model_service/app/model_loader.py")

CLAIM = dict(claim_id="CLM-test", policy_id="POL-test", claim_type="AUTO", amount=1200,
             zip="07302", incident_date="2024-01-05", days_since_policy_start=12,
             age=48, years_with_insurer=5, previous_claims=3, channel="Online",
             police_report_filed=True, injury_involved=False)


class PipelineTests(unittest.TestCase):
    def test_health_reports_unavailable_database(self):
        with patch.object(automation, "db", side_effect=RuntimeError("database unavailable")):
            response = TestClient(automation.app).get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unavailable")


    def test_model_endpoint_handles_failed_and_successful_prediction(self):
        model = importlib.import_module("trinethra.services.model_service.app.main")
        client = TestClient(model.app)
        with patch.object(model, "predict_risk", side_effect=RuntimeError("unavailable native runtime")):
            response = client.post("/predict", json={"payload": CLAIM})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["degraded"])
            self.assertIn("fallback", response.json()["warning"])
        with patch.object(model, "predict_risk", return_value=(.2, .163, "test-model")):
            response = client.post("/predict", json={"payload": CLAIM})
            self.assertFalse(response.json()["degraded"])
            self.assertEqual(response.json()["threshold"], .163)
            self.assertEqual(client.post("/predict", json={"payload": {}}).status_code, 422)

    def test_model_threshold_boundary_and_fallback(self):
        with patch.object(automation, "BLOCK_CUTOFF", None):
            self.assertEqual(automation.decide(.16, .163)[0], "AUTO_APPROVE")
            self.assertEqual(automation.decide(.163, .163)[0], "ROUTE_TO_REVIEW")
            self.assertEqual(automation.decide(.99, .163)[0], "ROUTE_TO_REVIEW")
            self.assertEqual(automation.decide(.01, .163, True)[0], "ROUTE_TO_REVIEW")
        with patch.object(automation, "BLOCK_CUTOFF", .92):
            self.assertEqual(automation.decide(.92, .163)[0], "BLOCK")
            self.assertEqual(automation.decide(.99, .163, True)[0], "ROUTE_TO_REVIEW")

    def test_intake_mapping_without_amount_proxies(self):
        schema = ["Age", "PastNumberOfClaims", "PoliceReportFiled", "AgentType",
                  "Days_Policy_Accident", "VehiclePrice", "Deductible", "Month"]
        row = loader.adapt_features_to_schema(CLAIM, schema)
        self.assertEqual(row["Age"], 48)
        self.assertEqual(row["PastNumberOfClaims"], "2 to 4")
        self.assertEqual(row["PoliceReportFiled"], "Yes")
        self.assertEqual(row["AgentType"], "Internal")
        self.assertEqual(row["Days_Policy_Accident"], "8 to 15")
        self.assertEqual(row["Month"], "Jun")
        expensive = loader.adapt_features_to_schema({**CLAIM, "amount": 90000}, schema)
        self.assertEqual(row["VehiclePrice"], expensive["VehiclePrice"])
        self.assertEqual(row["Deductible"], expensive["Deductible"])

    def test_invalid_claims_do_not_call_model(self):
        client = TestClient(automation.app)
        with patch.object(automation, "call_model") as model:
            for field, value in [("amount", -1), ("age", -1), ("previous_claims", -1),
                                 ("incident_date", "bad"), ("incident_date", "2999-01-01")]:
                self.assertEqual(client.post("/process_claim", json={**CLAIM, field: value}).status_code, 422)
            model.assert_not_called()
        self.assertEqual(client.get("/decisions/not-a-uuid").status_code, 422)

    def test_invalid_model_response_rejected(self):
        for risk, threshold, degraded in [(float("nan"), .16, False), (.1, 0, False),
                                           (1.1, .16, False), (.1, .16, "false")]:
            with patch.object(automation.requests, "post") as post:
                post.return_value.json.return_value = dict(risk_signal=risk, threshold=threshold,
                                                           model_version="test", degraded=degraded)
                with self.assertRaises(automation.HTTPException) as error:
                    automation.call_model(CLAIM)
                self.assertEqual(error.exception.status_code, 502)

    def test_saved_decision_contains_degraded_status_and_metadata(self):
        calls = []
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, sql, params): calls.append((sql, params))
            def fetchone(self): return {"event_id": "event-test", "decision_id": "decision-test"}
        class Connection:
            def cursor(self): return Cursor()
        @contextmanager
        def db(): yield Connection()
        prediction = dict(risk_signal=.01, threshold=.16, model_version="stub", degraded=True, warning="fallback")
        with patch.object(automation, "db", db), patch.object(automation, "call_model", return_value=prediction):
            response = TestClient(automation.app).post("/process_claim", json=CLAIM)
        self.assertEqual(response.status_code, 200, response.text)
        decision = response.json()
        self.assertEqual(decision["action"], "ROUTE_TO_REVIEW")
        self.assertTrue(decision["degraded"])
        self.assertIsNone(decision["confidence"])
        self.assertEqual(decision["decision_id"], "decision-test")
        sql, params = calls[1]
        self.assertIn("observability", sql)
        self.assertEqual(params[4], "AMBER")
        self.assertEqual(params[8], "policy_v3")
        self.assertTrue(params[10].adapted["degraded"])

    def test_explanation_uses_recorded_threshold_not_fixed_band(self):
        summary = explain._build_summary(CLAIM, dict(action="ROUTE_TO_REVIEW", risk_signal=.2, threshold=.163), {})
        self.assertIn("at or above", summary)
        self.assertIn("0.163", summary)
        self.assertNotIn("model confidence", summary)
        self.assertIn("not measured causes", explain._build_key_factors(CLAIM, {})[0])
        degraded = explain._build_summary(CLAIM, dict(action="ROUTE_TO_REVIEW", degraded=True), {})
        self.assertIn("Human review is required", degraded)

    def test_kpi_window_is_applied(self):
        calls = []
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, sql, params): calls.append((sql, params))
            def fetchone(self): return dict(total=4, approvals=1, blocks=1, reviews=2)
        class Connection:
            def cursor(self): return Cursor()
        @contextmanager
        def db(): yield Connection()
        with patch.object(automation, "db", db):
            response = TestClient(automation.app).get("/kpis?window_hours=48")
        self.assertEqual(response.json()["block_rate"], .25)
        self.assertEqual(calls[0][1], (48,))
        self.assertIn("WHERE timestamp", calls[0][0])
        self.assertNotIn("fraud_rate", response.json())


if __name__ == "__main__":
    unittest.main()
