import os, time, uuid
from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import PlainTextResponse
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tval:tvalpass@postgres:5432/tvaldb")
engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, future=True)

app = FastAPI(title="ledger")

REQUESTS = Counter("ledger_requests_total", "Total ledger writes")
LATENCY = Histogram("ledger_latency_seconds", "Latency of ledger writes", buckets=(0.01,0.05,0.1,0.2,0.5,1.0))

class Entry(BaseModel):
    amount: float
    currency: str
    merchant_id: str
    user_id: str
    txn_type: str

@app.on_event("startup")
def init_db():
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ledger_entries(
            id UUID PRIMARY KEY,
            amount NUMERIC,
            currency TEXT,
            merchant_id TEXT,
            user_id TEXT,
            txn_type TEXT,
            ts TIMESTAMP DEFAULT NOW()
        )
        """))
        conn.commit()

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return generate_latest().decode()

@app.post("/record")
def record(e: Entry):
    start = time.perf_counter()
    eid = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ledger_entries(id, amount, currency, merchant_id, user_id, txn_type)
            VALUES (:id, :amount, :currency, :merchant_id, :user_id, :txn_type)
        """), {"id":eid, "amount":e.amount, "currency":e.currency, "merchant_id":e.merchant_id,
               "user_id":e.user_id, "txn_type":e.txn_type})
    LATENCY.observe(time.perf_counter()-start)
    REQUESTS.inc()
    return {"id":eid}
