# Three transcription workflows, and what they bill

Companion files for the article *Three n8n transcription workflows, priced per run* on hostimm.com (2026-11-28).

All three import into n8n (tested on the current `n8nio/n8n` image, 2026-11-28) with no error. They are MIT licensed, same as the rest of this repo.

| File | Shape | Cost per run (list, 2026-11-28) |
|---|---|---|
| `01-basic-telegram-groq.json` | Telegram voice note, Groq `whisper-large-v3-turbo`, reply as text | $0.0106 per one minute note |
| `02-medium-drive-minutes.json` | Drive folder, `gpt-transcribe`, minutes with `gpt-5.6-sol`, markdown upload | $0.2840 per 45 minute meeting |
| `03-advanced-assemblyai-rag.json` | form upload, AssemblyAI with summary and speaker labels, Gemini embeddings, Pinecone, chat agent | $0.1995 per 45 minute meeting with one question |

Costs are list prices computed per call, not invoices. The control workload is one 45 minute meeting, 150 spoken words a minute, 9,045 transcript tokens measured at 1.34 tokens per word on a real episode. `cost_model.py` prints every line of the bill and `cost_model.json` holds the output.

## Credentials each file needs

- 01: Telegram bot token, one Header Auth credential for Groq (`Authorization: Bearer ...`).
- 02: Google Drive connection, one Header Auth credential for OpenAI. Replace `YOUR_FOLDER_ID` and `YOUR_MINUTES_FOLDER_ID`.
- 03: one Header Auth credential for AssemblyAI, Google Gemini (embeddings and chat), Pinecone, Google Sheets. Replace index name, sheet id and folder ids.

## What is deliberately different from the public templates

- The model is pinned in every node. Public template 10820 cannot choose its transcription model because n8n's OpenAI node hardcodes `whisper-1`; here it is an HTTP call to `gpt-transcribe`.
- Summaries on AssemblyAI use `speech_understanding.request.summarization`. The top level `summarization` and `summary_model` fields started returning errors on 2026-10-20.
- The text splitter is fixed at 900 characters with 100 overlap, so the embedding cost per meeting does not move when a default changes.
- The minutes prompt returns `null` rather than inventing an owner, and the output is markdown with a `.md` name. Public template 10820 writes plain text with a `.docx` name.
- A non-audio Telegram message gets one line back instead of a stack trace.

No API keys, no vendor eval, and no paid call was made to produce these numbers.
