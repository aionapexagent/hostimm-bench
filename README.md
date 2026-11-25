# hostimm-bench

The harness behind every number on hostimm.com. Four workloads, one output format, no hidden steps.

Anyone can rerun these. That is the point: a verdict you cannot reproduce is a press release.

## Workloads

| ID | Name | What it measures |
|---|---|---|
| W1 | serve | time to first token, p50 and p95 output tokens per second, over N fixed requests, against any OpenAI-compatible endpoint |
| W2 | transcribe | wall time and word error rate on a fixed audio file (faster-whisper local, or a hosted speech API) |
| W3 | agent | total input and output tokens, wall time, dollars per completed task for a fixed 50-step agent loop |
| W4 | deploy | minutes to a working URL, TLS validity, and time to first byte over N samples |

## Quick start

```bash
pip install -r requirements.txt

# W1 against any OpenAI-compatible endpoint
python w1_serve.py --base-url https://api.example.com/v1 --model some-model \
  --api-key $KEY --requests 500 --price-per-hour 1.09 --out results/w1-example.json

# W4 against a deployed URL
python w4_deploy.py --url https://your-app.example.com --samples 60 --out results/w4-example.json
```

## Output

Every run writes one JSON file with the same top-level shape:

```json
{
  "workload": "W1",
  "started": "2026-11-25T18:00:00Z",
  "target": {"provider": "runpod", "instance": "L40S", "price_usd_per_hour": 1.09},
  "requests": 500,
  "metrics": {"ttft_ms_p50": 0, "ttft_ms_p95": 0, "tokens_per_second_p50": 0, "tokens_per_second_p95": 0},
  "cost": {"measured_usd_per_1m_output_tokens": 0, "modeled": true},
  "notes": "anything that went wrong, in plain words"
}
```

`modeled: true` means the cost came from a list price and an assumed utilisation. `modeled: false` means it came from an invoice. The site never mixes the two.

## Rules this harness encodes

1. Fixed prompts, fixed request count, fixed seed where the provider allows it. A benchmark you can tune is not a benchmark.
2. Report p50 and p95, never a single average. The average hides the two slowest requests that decide whether a product feels fast.
3. The JSON is the source of truth. If an article quotes a number, the file is linked.
4. Failures are data. A provider that times out is reported as a timeout, not dropped from the sample.
5. No charge for running it: the scripts only consume what the caller's key allows.

## License

MIT. Take it, run it, publish your own numbers. If you find a mistake in ours, open an issue and it gets corrected in public with a dated line.

## Who pays for this

No ads, and no vendor money touching a number. The site runs on readers: <https://hostimm.com/membership/>. If a measurement here saved you a month of guessing, that is the invoice.
