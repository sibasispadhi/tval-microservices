from fastapi import FastAPI
from pydantic import BaseModel, field_validator
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
import time

app = FastAPI(title="risk")

SCORES = Histogram("risk_score", "Distribution of risk scores", buckets=(0.1,0.2,0.4,0.6,0.8,0.9,1.0))
REQUESTS = Counter("risk_requests_total", "Total risk evaluations")
LAT = Histogram("risk_latency_seconds", "Latency of risk evaluation", buckets=(0.005,0.01,0.02,0.05,0.1,0.2))

class Txn(BaseModel):
    amount: float
    currency: str
    merchant_id: str
    user_id: str
    txn_type: str

    @field_validator("txn_type")
    @classmethod
    def check_kind(cls, v):
        if v not in {"POS","REFUND"}:
            raise ValueError("txn_type must be POS or REFUND")
        return v

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest().decode()

@app.post("/score")
def score(t: Txn):
    start = time.perf_counter()
    base = 0.2 if t.txn_type == "POS" else 0.15
    amt = min(t.amount/200.0, 1.0)
    score = max(0.0, min(1.0, base + 0.6*amt))
    approved = score < 0.75
    SCORES.observe(score)
    REQUESTS.inc()
    LAT.observe(time.perf_counter()-start)
    return {"approved":approved, "score":score, "explain":"base + f(amount)"}
