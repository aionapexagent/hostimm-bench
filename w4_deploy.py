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
"""W4 DEPLOY: measure what a deployed URL actually does, from here, honestly.

Usage:
  python w4_deploy.py --url https://app.example.com --samples 60 --out results/w4.json
  python w4_deploy.py --latency --urls https://api.openai.com/v1 https://api.runpod.io --out results/latency.json

Two modes:
  default  one URL, N samples: DNS, TCP, TLS, time to first byte, status, size
  --latency several URLs, N samples each: same numbers, no downloads, for network-distance comparisons

This measures the path from the machine that runs it to the endpoint. It is not a verdict on a host's
compute performance, and the output says so.
"""
import argparse, json, os, socket, ssl, statistics, time, datetime, urllib.request, urllib.error, sys


def probe(url, timeout=20):
    host = urllib.parse.urlsplit(url).hostname if hasattr(urllib, "parse") else None
    import urllib.parse as up
    parts = up.urlsplit(url)
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)

    t0 = time.perf_counter()
    try:
        ip = socket.gethostbyname(host)
    except Exception as e:
        return {"ok": False, "error": "dns: %s" % e}
    t_dns = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except Exception as e:
        return {"ok": False, "error": "tcp: %s" % e, "dns_ms": round(t_dns, 1)}
    t_tcp = (time.perf_counter() - t1) * 1000

    t_tls = None
    if parts.scheme == "https":
        t2 = time.perf_counter()
        try:
            ctx = ssl.create_default_context()
            sock = ctx.wrap_socket(sock, server_hostname=host)
            t_tls = (time.perf_counter() - t2) * 1000
        except Exception as e:
            sock.close()
            return {"ok": False, "error": "tls: %s" % e, "dns_ms": round(t_dns, 1), "tcp_ms": round(t_tcp, 1)}
        cert = sock.getpeercert() or {}
        not_after = cert.get("notAfter", "")
    else:
        not_after = ""
    sock.close()

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "hostimm-bench/1.0 (+https://hostimm.com/how-we-test/)")
    t3 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            first = r.read(1)
            t_ttfb = (time.perf_counter() - t3) * 1000
            rest = r.read(200000)
            return {"ok": True, "dns_ms": round(t_dns, 1), "tcp_ms": round(t_tcp, 1),
                    "tls_ms": round(t_tls, 1) if t_tls else None, "ttfb_ms": round(t_ttfb, 1),
                    "status": r.status, "bytes": 1 + len(rest or b""), "cert_expires": not_after,
                    "server": r.headers.get("Server", "")}
    except urllib.error.HTTPError as e:
        t_ttfb = (time.perf_counter() - t3) * 1000
        return {"ok": True, "dns_ms": round(t_dns, 1), "tcp_ms": round(t_tcp, 1),
                "tls_ms": round(t_tls, 1) if t_tls else None, "ttfb_ms": round(t_ttfb, 1),
                "status": e.code, "bytes": 0, "cert_expires": not_after,
                "server": e.headers.get("Server", "") if e.headers else ""}
    except Exception as e:
        return {"ok": False, "error": "http: %s" % e}


def summary(rows):
    def p(key, q):
        vals = [r[key] for r in rows if r.get("ok") and isinstance(r.get(key), (int, float))]
        if not vals:
            return None
        vals = sorted(vals)
        k = max(0, min(len(vals) - 1, int(round((q / 100) * (len(vals) - 1)))))
        return round(vals[k], 1)
    return {
        "samples": len(rows),
        "ok": sum(1 for r in rows if r.get("ok")),
        "dns_ms_p50": p("dns_ms", 50), "tcp_ms_p50": p("tcp_ms", 50), "tls_ms_p50": p("tls_ms", 50),
        "ttfb_ms_p50": p("ttfb_ms", 50), "ttfb_ms_p95": p("ttfb_ms", 95),
        "status_last": rows[-1].get("status") if rows else None,
        "cert_expires": rows[-1].get("cert_expires") if rows else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--urls", nargs="*", default=[])
    ap.add_argument("--latency", action="store_true")
    ap.add_argument("--samples", type=int, default=30)
    ap.add_argument("--out", default="results/w4.json")
    a = ap.parse_args()

    targets = a.urls if a.latency else ([a.url] if a.url else [])
    if not targets:
        print("give --url or --latency --urls ...")
        return 2

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    results = {}
    for url in targets:
        rows = []
        for _ in range(a.samples):
            rows.append(probe(url))
            time.sleep(0.2)
        results[url] = {"summary": summary(rows), "samples": rows}
        s = results[url]["summary"]
        print("%-45s ttfb p50 %sms  tls %sms  dns %sms  ok %d/%d" % (
            url, s["ttfb_ms_p50"], s["tls_ms_p50"], s["dns_ms_p50"], s["ok"], s["samples"]))

    out = {
        "workload": "W4-latency" if a.latency else "W4",
        "started": started,
        "note": "Measures the path from the machine running the harness to the endpoint. "
                "Not a measure of compute performance.",
        "samples_per_target": a.samples,
        "results": results,
    }
    json.dump(out, open(a.out, "w"), indent=1)
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
