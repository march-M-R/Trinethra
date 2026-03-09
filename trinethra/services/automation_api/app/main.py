from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Trinetra Automation API", version="1.0")


# ----------------------------
# CORS
# ----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# ENV
# ----------------------------

MODEL_URL = os.getenv(
    "MODEL_URL",
    "https://trinethra-model-service.onrender.com",
)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ----------------------------
# Policy
# ----------------------------

APPROVE_CUTOFF = 0.70
BLOCK_CUTOFF = 0.92


# ----------------------------
# Request schema (matches UI)
# ----------------------------

class ProcessClaimRequest(BaseModel):

    amount: float
    zip: str
    incident_date: str
    days_since_policy_start: int
    age: int
    years_with_insurer: int
    previous_claims: int
    channel: str
    police_report_filed: bool = False
    injury_involved: bool = False


# ----------------------------
# DB connection
# ----------------------------

def db():

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


# ----------------------------
# Health
# ----------------------------

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ----------------------------
# Model call
# ----------------------------

def call_model(payload):

    try:

        r = requests.post(
            f"{MODEL_URL}/predict",
            json={"payload": payload},
            timeout=10,
        )

        data = r.json()

        return data

    except Exception as e:

        return {
            "risk_signal": 0.5,
            "threshold": 0.8,
            "model_version": "fallback",
        }


# ----------------------------
# Decision logic
# ----------------------------

def decide(risk):

    if risk >= BLOCK_CUTOFF:
        return "BLOCK", 0.95

    if risk < APPROVE_CUTOFF:
        return "AUTO_APPROVE", 0.85

    return "ROUTE_TO_REVIEW", 0.90


# ----------------------------
# Process Claim
# ----------------------------

@app.post("/process_claim")
def process_claim(req: ProcessClaimRequest):

    try:

        payload = req.dict()

        # -------------------
        # call model
        # -------------------

        model = call_model(payload)

        risk = float(model["risk_signal"])
        threshold = float(model["threshold"])
        model_version = model["model_version"]

        action, confidence = decide(risk)

        # -------------------
        # save event
        # -------------------

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO events(domain,event_type,entity_id,payload)
                    VALUES(%s,%s,%s,%s::jsonb)
                    RETURNING event_id
                    """,
                    (
                        "insurance",
                        "claim",
                        f"claim_{int(time.time())}",
                        psycopg2.extras.Json(payload),
                    ),
                )

                event_id = cur.fetchone()["event_id"]

                cur.execute(
                    """
                    INSERT INTO decision_events
                    (event_id,action,confidence,risk_signal,model_version)
                    VALUES(%s,%s,%s,%s,%s)
                    """,
                    (
                        event_id,
                        action,
                        confidence,
                        risk,
                        model_version,
                    ),
                )

        summary = f"Risk score {risk:.2f}. Decision: {action}"

        return {

            "action": action,
            "confidence": confidence,
            "risk_signal": risk,
            "threshold": threshold,
            "model_version": model_version,

            "observability": {
                "llm_summary": summary
            },

            "llm_summary": summary

        }

    except Exception as e:

        return {
            "error": str(e)
        }


# ----------------------------
# Decisions
# ----------------------------

@app.get("/decisions")
def decisions(limit: int = 50):

    try:

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                    decision_id,
                    action,
                    confidence,
                    risk_signal,
                    model_version
                    FROM decision_events
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,),
                )

                return cur.fetchall()

    except Exception as e:

        return {"error": str(e)}


# ----------------------------
# KPIs
# ----------------------------

@app.get("/kpis")
def kpis():

    try:

        with db() as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                    COUNT(*) total,
                    SUM(CASE WHEN action='AUTO_APPROVE' THEN 1 ELSE 0 END) approvals,
                    SUM(CASE WHEN action='BLOCK' THEN 1 ELSE 0 END) blocks
                    FROM decision_events
                    """
                )

                row = cur.fetchone()

        total = row["total"] or 0
        approvals = row["approvals"] or 0
        blocks = row["blocks"] or 0

        fraud_rate = blocks / total if total else 0

        return {

            "total_decisions": total,
            "approvals": approvals,
            "blocks": blocks,
            "fraud_rate": fraud_rate

        }

    except Exception as e:

        return {"error": str(e)}