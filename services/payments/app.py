import os, time, asyncio
from fastapi import FastAPI
from pydantic import BaseModel
import httpx
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse

RISK_URL = os.getenv("RISK_URL", "http://risk:8000")
LEDGER_URL = os.getenv("LEDGER_URL", "http://ledger:8000")
P95_SLO_MS = int(os.getenv("P95_SLO_MS", "200"))
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "8"))

app = FastAPI(title="payments")
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

REQUESTS = Counter("payments_requests_total", "Total payment requests")
ERRORS = Counter("payments_errors_total", "Errors in payments")
LATENCY = Histogram("payments_latency_seconds", "Latency of payments", buckets=(0.05,0.1,0.2,0.3,0.5,1.0,2.0))

class Payment(BaseModel):
    amount: float
    currency: str = "USD"
    merchant_id: str
    user_id: str
    txn_type: str = "POS"  # POS or REFUND

@app.get("/health")
def health():
    return {"status":"ok","p95_slo_ms":P95_SLO_MS,"max_concurrency":MAX_CONCURRENCY}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest().decode()

@app.post("/pay")
async def pay(p: Payment):
    start = time.perf_counter()
    REQUESTS.inc()

    async with semaphore:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(f"{RISK_URL}/score", json=p.model_dump())
            r.raise_for_status()
            data = r.json()
            if not data.get("approved", False):
                duration = time.perf_counter() - start
                LATENCY.observe(duration)
                return {"status":"rejected", "score": data.get("score",0)}

            l = await client.post(f"{LEDGER_URL}/record", json=p.model_dump())
            l.raise_for_status()
            duration = time.perf_counter() - start
            LATENCY.observe(duration)
            return {"status":"approved", "ledger_id": l.json().get("id")}
