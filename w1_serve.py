#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# AION (Autonomous Intelligence Operating Node)
# Architect: AlexH  |  Architecture: APEX V2
# Project: hostimm.com  |  https://hostimm.com
# Community: llmresearch.net (EN)  |  forumai.ro (RO)
# License: MIT, see LICENSE. Reuse encouraged, attribution appreciated.
# This file contains no proprietary methods, credentials, client data or
# internal material. If that ever changes, the proprietary part ships as a
# separate, clearly tagged light version instead of landing here.
# ---------------------------------------------------------------------------
"""W1 SERVE: measure time to first token and throughput on an OpenAI-compatible endpoint.

Usage:
  python w1_serve.py --base-url URL --model NAME --api-key KEY [--requests 500] [--price-per-hour 1.09] [--out file.json]

No SDK, no retries hidden, no dropped samples: a failure is recorded as a failure.
"""
import argparse, json, os, statistics, time, urllib.request, urllib.error, datetime, sys

PROMPTS = [
    "Explain in exactly three sentences why a small business might move a database to a managed service.",
    "List the four steps to deploy a FastAPI app behind nginx on a fresh Ubuntu server.",
    "Write a Python function that retries an HTTP request with exponential backoff and a hard timeout.",
    "Summarise the trade-off between serverless GPUs and dedicated GPU instances in two paragraphs.",
    "Write a short email declining a meeting without sounding rude.",
]


def one_request(base_url, model, key, prompt, max_tokens, timeout):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": True,
    }).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "text/event-stream")
    if key:
        req.add_header("Authorization", "Bearer " + key)

    t0 = time.perf_counter()
    ttft = None
    tokens = 0
    ok = True
    err = ""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                delta = (ev.get("choices") or [{}])[0].get("delta") or {}
                if delta.get("content"):
                    if ttft is None:
                        ttft = (time.perf_counter() - t0) * 1000
                    tokens += 1
    except urllib.error.HTTPError as e:
        ok, err = False, "http %s: %s" % (e.code, e.read()[:200].decode("utf-8", "replace"))
    except Exception as e:
        ok, err = False, "%s: %s" % (type(e).__name__, e)

    total = time.perf_counter() - t0
    tps = (tokens / (total - (ttft or 0) / 1000)) if tokens > 1 else 0
    return {"ok": ok, "error": err, "ttft_ms": ttft, "tokens": tokens,
            "total_s": round(total, 3), "tokens_per_second": round(tps, 1)}


def pct(values, p):
    if not values:
        return None
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((p / 100) * (len(values) - 1)))))
    return round(values[k], 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key", default=os.environ.get("HOSTIMM_API_KEY", ""))
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--max-tokens", type=int, default=160)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--price-per-hour", type=float, default=0.0, help="rented GPU price, 0 for a hosted API")
    ap.add_argument("--provider", default="")
    ap.add_argument("--instance", default="")
    ap.add_argument("--out", default="results/w1.json")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    print("W1: %d requests against %s (%s)" % (a.requests, a.base_url, a.model))

    samples = []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for i in range(a.requests):
        r = one_request(a.base_url, a.model, a.api_key, PROMPTS[i % len(PROMPTS)], a.max_tokens, a.timeout)
        samples.append(r)
        if (i + 1) % 25 == 0:
            print("  %d/%d ok=%d" % (i + 1, a.requests, sum(1 for s in samples if s["ok"])))

    ok = [s for s in samples if s["ok"] and s["ttft_ms"]]
    ttfts = [s["ttft_ms"] for s in ok]
    tpss = [s["tokens_per_second"] for s in ok if s["tokens_per_second"]]
    tokens = sum(s["tokens"] for s in ok)
    seconds = sum(s["total_s"] for s in ok)
    measured_cost_per_1m = None
    if a.price_per_hour and tpss:
        measured_cost_per_1m = round((a.price_per_hour / 3600) / statistics.median(tpss) * 1_000_000, 4)

    out = {
        "workload": "W1",
        "started": started,
        "target": {"provider": a.provider, "instance": a.instance, "model": a.model,
                   "base_url": a.base_url, "price_usd_per_hour": a.price_per_hour},
        "requests": a.requests,
        "successful": len(ok),
        "failed": a.requests - len(ok),
        "metrics": {
            "ttft_ms_p50": pct(ttfts, 50), "ttft_ms_p95": pct(ttfts, 95),
            "tokens_per_second_p50": pct(tpss, 50), "tokens_per_second_p95": pct(tpss, 95),
            "output_tokens_generated": tokens, "wall_seconds": round(seconds, 1),
        },
        "cost": {
            "measured_usd_per_1m_output_tokens": measured_cost_per_1m,
            "modeled": True,
            "note": "cost uses the list price per hour and the p50 throughput unless an invoice is attached",
        },
        "errors": sorted({s["error"] for s in samples if s["error"]})[:5],
        "samples": [{"ttft_ms": s["ttft_ms"], "tokens": s["tokens"], "tps": s["tokens_per_second"]} for s in samples],
    }
    json.dump(out, open(a.out, "w"), indent=1)
    print("wrote", a.out)
    print("p50 %.1f tok/s | p95 %.1f | ttft p50 %.0f ms | failures %d" % (
        out["metrics"]["tokens_per_second_p50"] or 0, out["metrics"]["tokens_per_second_p95"] or 0,
        out["metrics"]["ttft_ms_p50"] or 0, out["failed"]))


if __name__ == "__main__":
    sys.exit(main())
