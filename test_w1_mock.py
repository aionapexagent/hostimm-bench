"""Prove w1_serve.py counts tokens from the usage block, not from SSE events."""
import json, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        assert body.get("stream_options", {}).get("include_usage") is True, "client did not ask for usage"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        # three text events, one usage event with 40 tokens, then DONE
        for chunk in ["Hello", " from", " the mock"]:
            ev = {"choices": [{"delta": {"content": chunk}}]}
            self.wfile.write(("data: " + json.dumps(ev) + "\n\n").encode())
            self.wfile.flush()
            time.sleep(0.02)
        usage_ev = {"choices": [], "usage": {"completion_tokens": 40}}
        self.wfile.write(("data: " + json.dumps(usage_ev) + "\n\ndata: [DONE]\n\n").encode())
        self.wfile.flush()

    def log_message(self, *a):
        pass

srv = HTTPServer(("127.0.0.1", 8765), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

out = "C:/Users/rofor/AppData/Local/hermes/cache/scratch/w1test.json"
r = subprocess.run([sys.executable, "w1_serve.py", "--base-url", "http://127.0.0.1:8765/v1",
                    "--model", "mock", "--requests", "2", "--max-tokens", "10", "--out", out],
                   capture_output=True, text=True)
print(r.stdout[-400:], r.stderr[-300:])
d = json.load(open(out))
m = d["metrics"]
print("tokens:", m["output_tokens_generated"], "mode:", m["tokens_mode"], "reported_reqs:", m["tokens_reported_requests"])
print("TPS p50:", m["tokens_per_second_p50"], "TTFT p50:", m["ttft_ms_p50"])
assert m["tokens_mode"] == "reported", "mode should be reported"
assert m["output_tokens_generated"] == 80, "should be 2 x 40 tokens from usage"
print("PASS: tokens come from usage.completion_tokens, not from 3 SSE events")
