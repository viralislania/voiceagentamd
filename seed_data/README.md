# Seed Dataset Kit — Banking Agent POC

Hand-written seed examples + tooling to build the fine-tuning dataset for the
8B banking agent. This is the highest-leverage, least-available-off-the-shelf
part of the POC: there is no public Hinglish banking-journey dataset, so you
seed by hand and augment.

## Contents

| File | What it is | Count |
|------|-----------|-------|
| `classify_seeds.jsonl` | Intent classification + slot extraction, all 8 intents, EN/HI/Hinglish | 34 |
| `disambiguation_seeds.jsonl` | Adversarial confusable pairs (data-query vs RAG, etc.) | 20 |
| `slot_filling_seeds.jsonl` | Multi-turn FD + complaint slot-filling (ask-one-slot, then tool_call) | 10 |
| `formatting_rag_seeds.jsonl` | Tool-result formatting ("never invent numbers") + grounded RAG answers | 13 |
| `docs/` | Mock help documents for the RAG path | 5 docs |
| `augment.py` | Paraphrase-expand seeds into `data/train.jsonl` + `data/eval.jsonl` | — |
| `evaluate.py` | Measure intent acc / slot F1 / JSON validity / tool-call correctness | — |

**77 hand-written seeds total.** After augmentation (default 6 paraphrases per
classification seed across EN/HI/Hinglish) you land in the ~1,500–2,500 example
range — a good size for a QLoRA POC.

## The three patterns these seeds teach

1. **Transactional journey** (`open_fixed_deposit`, `open_savings`, `raise_complaint`)
   → multi-turn slot-fill, then a `tool_call` action.
2. **Structured data retrieval** (`account_statement`, `balance_inquiry`,
   `transaction_failure`) → tool-call to the mock DB, then format ONLY returned numbers.
3. **Knowledge RAG** (`help_knowledge`) → retrieve from `docs/`, answer grounded in snippets.

## The disambiguation seeds are the important ones

Zero-shot models routinely blur these. The `disambiguation_seeds.jsonl` file
deliberately pairs near-identical surface forms with different intents:

| User says | Intent | Why |
|-----------|--------|-----|
| "what is my balance" | `balance_inquiry` | live data → tool |
| "what is the minimum balance I need" | `help_knowledge` | policy → RAG |
| "why did my transfer fail" | `transaction_failure` | this txn → tool |
| "why do transfers fail sometimes" | `help_knowledge` | general → RAG |
| "open an FD" | `open_fixed_deposit` | action → journey |
| "how do I open an FD" | `help_knowledge` | how-to → RAG |

Keep this ratio high; it's what lets the small model route correctly.

## Workflow

```bash
# 0. (Phase A) validate architecture zero-shot FIRST, before any training.
#    Point evaluate.py at the un-fine-tuned base model to get a baseline.
EVAL_MODEL=Qwen/Qwen2.5-7B-Instruct python evaluate.py

# 1. Augment seeds -> data/train.jsonl + data/eval.jsonl
#    Uses a served model (a strong teacher, or your base) for paraphrasing.
AUG_MODEL=Qwen/Qwen2.5-7B-Instruct python augment.py

# 2. QLoRA fine-tune (see train_qlora.py in the main build plan)
python train_qlora.py

# 3. Merge + serve quantized (see build plan section 5.6), then re-evaluate
EVAL_MODEL=out/bank-8b-merged python evaluate.py
#    Compare JSON-validity before/after 4-bit quantization. If it drops, use 8-bit.
```

## Guidelines if you extend the seeds by hand

- **Keep the assistant target strict JSON** for classification/slot/action seeds.
  The model learns the output contract from these — consistency matters more than volume.
- **Vary the user turn, not the target.** Same intent, many phrasings, three languages.
- **Match `docs/` to the RAG answers.** The `formatting_rag_seeds.jsonl` answers quote
  figures (₹5,000 min balance, ₹150 penalty, 1% premature-withdrawal penalty, etc.)
  that are stated in `docs/`. If you change one, change the other.
- **Keep numbers in tool-result seeds traceable.** Every figure in an assistant
  formatting answer must appear in the `tool` message — that's the behavior you're teaching.
- **Add negatives.** Out-of-scope ("what's the weather") → `fallback`. Ambiguous
  policy-vs-data → the RAG side. These sharpen boundaries more than more easy examples.

## Mapping to the build plan

These files populate the `data/` directory referenced by `train_qlora.py`, and the
`docs/` directory referenced by `rag_index.py`, in the main POC build plan document.
The eval metrics here are the ones the plan's checklist step 6 ("evaluate intent acc /
slot F1 / JSON validity") calls for.
