import os, time, uuid, json, argparse
from datetime import datetime, timezone
import requests, yaml
from jsonschema import validate

PROM_URL = os.getenv("PROM_URL", "http://prometheus:9090")
OPA_URL = os.getenv("OPA_URL", "http://opa:8181/v1/data/tval/allow")
PROPOSALS_DIR = os.getenv("PROPOSALS_DIR", "/app/manifests")
LOGS_DIR = os.getenv("LOGS_DIR", "/app/logs")
TARGET_SERVICE = os.getenv("TARGET_SERVICE", "payments")
P95_SLO_MS = int(os.getenv("P95_SLO_MS", "200"))

SCHEMA_PATH = "/app/schemas/justification_schema.json"

def load_schema():
    """Lazily load the justification JSON schema. Return None if not available.

    Loading is deferred so the agent image can be built without requiring the
    host-mounted `schemas` directory at build time. At runtime the compose
    mount will provide the schema file.
    """
    try:
        with open(SCHEMA_PATH) as fh:
            return json.load(fh)
    except Exception:
        # If schema missing, proceed without validation but log a warning.
        print(f"[agent] Warning: schema not found at {SCHEMA_PATH}; skipping validation")
        return None

SCHEMA = load_schema()

def prom_query(q):
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": q}, timeout=10)
    r.raise_for_status()
    v = r.json()["data"]["result"]
    if not v:
        return None
    return float(v[0]["value"][1])

def p95_latency_ms():
    q = 'histogram_quantile(0.95, sum(rate(payments_latency_seconds_bucket[5m])) by (le)) * 1000'
    return prom_query(q)

def error_rate():
    q = 'rate(payments_errors_total[5m])'
    v = prom_query(q)
    return 0.0 if v is None else v

def current_concurrency():
    try:
        r = requests.get("http://payments:8000/health", timeout=3).json()
        return int(r.get("max_concurrency", 8))
    except Exception:
        return 8

def verify_with_opa(param, proposed):
    payload = {"input": {"target": TARGET_SERVICE, "param": param, "proposed": proposed}}
    r = requests.post(OPA_URL, json=payload, timeout=5)
    r.raise_for_status()
    return r.json().get("result", False)

def save_manifest(param, proposed):
    action_id = str(uuid.uuid4())
    manifest = {
        "apiVersion": "tval/v1",
        "kind": "Proposal",
        "metadata": {"id": action_id, "target": TARGET_SERVICE},
        "spec": {"param": param, "proposed": proposed}
    }
    path = os.path.join(PROPOSALS_DIR, f"{action_id}.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(manifest, f)
    return action_id, path

def log_justification(action_id, param, current, proposed, policy_result, metrics, human_required):
    record = {
        "action_id": action_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": TARGET_SERVICE,
        "param": param,
        "current": current,
        "proposed": proposed,
        "metrics": metrics,
        "policy_result": policy_result,
        "human_required": human_required,
        "explain": "Latency vs SLO; increase concurrency if p95>SLO and error_rate low"
    }
    # Validate if schema is available; do not fail the control loop if
    # validation or schema loading fails — still write the justification.
    try:
        if SCHEMA is not None:
            validate(record, SCHEMA)
    except Exception as e:
        print(f"[agent] Warning: justification validation failed: {e}")
    path = os.path.join(LOGS_DIR, f"{action_id}.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=2)
    return path

def control_loop_once():
    p95 = p95_latency_ms()
    err = error_rate()
    cur = current_concurrency()

    if p95 is None:
        print("[agent] No latency data yet.")
        return

    metrics = {"p95_ms": p95, "error_rate": err, "p95_slo_ms": P95_SLO_MS}

    proposal = cur
    if p95 > P95_SLO_MS and err < 0.05:
        proposal = min(cur + 2, 64)
    elif p95 < 0.7 * P95_SLO_MS and cur > 4:
        proposal = max(cur - 2, 4)

    if proposal == cur:
        print(f"[agent] No change (cur={cur}, p95={p95:.1f}ms).")
        return

    allowed = verify_with_opa("MAX_CONCURRENCY", proposal)
    action_id, mpath = save_manifest("MAX_CONCURRENCY", proposal)
    jpath = log_justification(action_id, "MAX_CONCURRENCY", cur, proposal, allowed, metrics, True)
    print(f"[agent] Proposed change -> manifest={mpath}, justification={jpath}, allowed={allowed}")

def summarize_trust_index():
    logs = []
    for name in os.listdir(LOGS_DIR):
        if name.endswith(".json"):
            try:
                logs.append(json.load(open(os.path.join(LOGS_DIR, name))))
            except Exception:
                pass
    if not logs:
        print("no_logs,trust_index=0.00")
        return

    policy_pass = sum(1 for r in logs if r["policy_result"])/len(logs)
    approval_consistency = policy_pass
    rollback_rate = 0.05  # placeholder

    trust_index = (policy_pass + approval_consistency + (1 - rollback_rate))/3.0
    header = "policy_pass_rate,approval_consistency,rollback_rate,trust_index"
    row = f"{policy_pass:.3f},{approval_consistency:.3f},{rollback_rate:.3f},{trust_index:.3f}"
    print(header)
    print(row)

    # Persist summary CSV to logs directory for later inspection.
    try:
        outpath = os.path.join(LOGS_DIR, "trust_index_summary.csv")
        with open(outpath, "w") as fh:
            fh.write(header + "\n")
            fh.write(row + "\n")
        print(f"[agent] saved trust index summary to {outpath}")
    except Exception as e:
        print(f"[agent] Warning: could not save trust index summary: {e}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--summarize", action="store_true")
    args = ap.parse_args()

    if args.summarize:
        summarize_trust_index()
    elif args.once:
        control_loop_once()
    else:
        while True:
            try:
                control_loop_once()
            except Exception as e:
                print("[agent] error:", e)
            time.sleep(15)
