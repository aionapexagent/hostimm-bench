import json, tiktoken
enc = tiktoken.get_encoding("cl100k_base")

# ---------- measured facts ----------
transcript = json.load(open("transcript_stats.json"))
TPW = transcript["tokens_per_word"]              # 1.34, measured on a real 96 min episode
MIN = 45.0                                       # control workload: one 45 minute meeting
WPM = 150                                        # assumption for a business meeting
words = MIN * WPM
ttoks = round(words * TPW)

wf = json.load(open("n8nwf/10820.json"))["workflow"]["workflow"]
sysprompt = [m for m in [n for n in wf["nodes"] if n["name"] == "OpenAI 2"][0]["parameters"]["messages"]["values"] if m.get("role") == "system"][0]["content"]
sys_tokens = len(enc.encode(sysprompt))

# ---------- prices, USD, read 2026-11-28 ----------
EURUSD = 1 / 0.912659      # ECB reference rate 2026-11-27
P = {
    "n8n_starter_exec": 20 * EURUSD / 2500,
    "n8n_pro_exec": 50 * EURUSD / 10000,
    "groq_v3_hr": 0.111,
    "groq_turbo_hr": 0.04,
    "openai_whisper1_min": 0.006,
    "openai_gpt_transcribe_min": 0.0045,
    "aai_stt37_hr": 0.21,
    "aai_univ2_hr": 0.15,
    "aai_diar_hr": 0.02,
    "aai_sum_low_hr": 0.02,
    "aai_sum_med_hr": 0.07,
    "gemini_embed_M": 0.15,
    "gemini_flash_in_M": 0.30,
    "gemini_flash_out_M": 2.50,
    "gpt5_in_M": 1.25, "gpt5_out_M": 10.0,
    "gpt56sol_in_M": 4.0, "gpt56sol_out_M": 20.0,
    "gpt56terra_in_M": 2.0, "gpt56terra_out_M": 12.0,
}
hours = MIN / 60

def llm_cost(in_tok, out_tok, pin, pout):
    return in_tok * P[pin] / 1e6 + out_tok * P[pout] / 1e6

# ---------- A: basic, Telegram voice note ----------
a_voice = 0.111 * (10 / 3600)          # 10 s billed minimum at large-v3
a_1min = P["groq_v3_hr"] / 60          # one minute voice note
a_exec = P["n8n_starter_exec"]
basic = {
    "transcription_10s": round(a_voice, 6),
    "transcription_1min": round(a_1min, 6),
    "n8n_execution": round(a_exec, 6),
    "total_1min": round(a_1min + a_exec, 6),
}

# ---------- B: medium, Drive -> whisper-1 -> gpt-5 minutes ----------
b_trans = MIN * P["openai_whisper1_min"]
b_trans_new = MIN * P["openai_gpt_transcribe_min"]
b_in = ttoks + sys_tokens + 20
b_out = 1200                            # assumption: minutes text plus reasoning tokens
b_llm_as_shipped = llm_cost(b_in, b_out, "gpt5_in_M", "gpt5_out_M")
b_llm_migrated = llm_cost(b_in, b_out, "gpt56sol_in_M", "gpt56sol_out_M")
medium = {
    "transcription_whisper1": round(b_trans, 4),
    "transcription_gpt_transcribe": round(b_trans_new, 4),
    "llm_as_shipped_gpt5": round(b_llm_as_shipped, 4),
    "llm_migrated_gpt56sol": round(b_llm_migrated, 4),
    "n8n_execution": round(P["n8n_starter_exec"], 6),
    "total_as_shipped": round(b_trans + b_llm_as_shipped + P["n8n_starter_exec"], 4),
    "total_after_migration": round(b_trans + b_llm_migrated + P["n8n_starter_exec"], 4),
    "total_new_transcriber_migrated": round(b_trans_new + b_llm_migrated + P["n8n_starter_exec"], 4),
}

# ---------- C: advanced, AssemblyAI -> Gemini embeddings -> Pinecone RAG ----------
c_base = hours * P["aai_stt37_hr"]
c_diar = hours * P["aai_diar_hr"]
c_sum = hours * P["aai_sum_low_hr"]
c_embed = (10616 * P["gemini_embed_M"] / 1e6)  # measured on a real transcript, 900/100 split
# chunks: default 1000 chars, 100 overlap
chunks = 51  # measured: 50.9 chunks per 45 min at 900/100
# chat after the run: 1 question, retriever called twice, memory 5 turns
chat_in = 2 * (ttoks / 40 * 5 + 600)     # rough: 5 retrieved chunks (~1/40 of transcript each) + prompt
chat_out = 250
c_chat = llm_cost(chat_in, chat_out, "gemini_flash_in_M", "gemini_flash_out_M")
advanced = {
    "transcription": round(c_base, 4),
    "diarization": round(c_diar, 4),
    "summarization_low": round(c_sum, 4),
    "embeddings": round(c_embed, 6),
    "chunks": chunks,
    "chat_one_question": round(c_chat, 6),
    "n8n_execution": round(P["n8n_starter_exec"], 6),
    "total_upload_and_index": round(c_base + c_diar + c_sum + c_embed + P["n8n_starter_exec"], 4),
    "total_with_one_chat": round(c_base + c_diar + c_sum + c_embed + P["n8n_starter_exec"] + c_chat, 4),
}

out = {"assumptions": {"meeting_min": MIN, "words_per_min": WPM, "words": words,
                       "tokens_per_word": TPW, "transcript_tokens": ttoks,
                       "system_prompt_tokens": sys_tokens, "gpt5_output_tokens_assumed": b_out,
                       "chunks_estimate": chunks, "chat_input_tokens": round(chat_in)},
       "prices_usd": P,
       "basic_voice_note": basic,
       "medium_meeting_minutes": medium,
       "advanced_rag": advanced}

json.dump(out, open("cost_model.json", "w"), indent=1)

print(json.dumps(out["assumptions"], indent=1))
for k in ("basic_voice_note", "medium_meeting_minutes", "advanced_rag"):
    print("\n==", k)
    for kk, vv in out[k].items():
        print(f"  {kk:32s} {vv}")

print("\nper 100 meetings, USD")
print("  medium as shipped  ", round(medium["total_as_shipped"] * 100, 2))
print("  medium migrated    ", round(medium["total_after_migration"] * 100, 2))
print("  advanced + 1 chat  ", round(advanced["total_with_one_chat"] * 100, 2))
