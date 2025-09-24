# Hybrid RCM Agent – Technical Design Spec  
*(Last update: 2025‑07‑24)*

## 0 Executive Summary  
The Hybrid RCM Agent automates payer‑portal and EHR tasks by combining:

| Layer | Role |
|-------|------|
| **Embedding Memory (pgvector)** | Stores text + image embeddings keyed by state_id with success EMA. |
| **MiniLM Gate** | Fast semantic check to reuse actions. |
| **Llama‑3 8 B Repair** | DOM diff + selector repair (< 450 ms). |
| **Claude 3 Sonnet Vision Fallback** | Handles icon/colour edge cases via screenshot. |
| **Trace Memory** | Full action sequences for anticipation. |
| **Playwright Driver** | Executes JSON actions; returns DOM & screenshot. |
| **PHI Masking** | RoBERTa‑de‑id for text, PaddleOCR blur for images. |

Outcome: 10–20× faster median latency and ~90 % cheaper token spend vs GPT‑4‑only agents.

---

## 1 Embedding & State‑Dedup  
Embed **every** page (BGE text + SigLIP img).  

```python
SAME_PAGE_THR = 0.80
def should_insert(mini_score, action_repaired):
    if mini_score >= SAME_PAGE_THR:
        return action_repaired          # replace only if selector drifted
    return True                         # novel layout
```

* ~1 % of visits become new states; pgvector stays < 5 M rows.

---

## 2 Run‑Loop  

```
Page → embed → pgvector k‑NN → MiniLM  
    ├─ same+selector OK  → execute  
    ├─ same+selector drift → Llama‑3 repair → execute  
    └─ low similarity      → Claude Sonnet vision → execute  
After success → update trace & state table
```

---

## 3 Prompt Engineering  

### Llama‑3 Repair  
Inputs: CURRENT_DOM, RETRIEVED_DOM, RETRIEVED_ACTION, TRACE_SLICE.  
Outputs strict JSON tool‑call or reject.  

### Claude Sonnet Fallback  
Receives screenshot (base64) + DOM summary + prior trace; identical JSON schema.

---

## 4 OCR & PHI Redaction  

| Engine | CER | Page latency | Notes |
|--------|-----|--------------|-------|
| **PaddleOCR PP‑OCR v4** | 1‑4 % | 35 ms | chosen |

Masked regions are black‑barred before any external model call.

---

## 5 Performance & Cost  

| Path | Median latency | Cost/10 k steps |
|------|---------------|-----------------|
| Cache hit | 30 ms | $0.02 |
| Llama‑3 8 B | 430 ms | $0.70 |
| Claude‑Sonnet | 600 ms | $1.4 |

---

## 6 Roadmap (abridged)  

| Day | Deliverable |
|-----|-------------|
| 0‑4 | MVP with GPT‑4o repair |
| 5‑7 | Add pgvector + trace |
| Week 2 | Swap to Llama‑3 repair & Claude fallback |
| Month 1 | Fine‑tune MiniLM & reach >80 % cache hits |
| Month 3 | Add self‑healing EMA decay |

---

## 7 Citrix / Pixel Automation  

Add Playwright tools:

```json
{"tool":"screen_click","x":417,"y":186}
{"tool":"screen_type","text":"12345"}
```

Vision LLM controls coordinate clicks; screenshots fed back each step.

---

*(See the canvas for full tables, SQL schemas, and benchmark details.)*