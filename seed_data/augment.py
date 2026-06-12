#!/usr/bin/env python3
"""
augment.py — Expand hand-written seed examples into a full training set.

Strategy (mirrors the CST5 approach used by Hinglish-TOP: paraphrase seeds to
multiply labeled data, reportedly up to ~20x less hand-labeling needed):

  1. Load all seed JSONL files.
  2. For each CLASSIFICATION/SLOT seed, ask a strong LLM to produce N paraphrases
     of the *user turn* in English, Hindi (Devanagari), and Hinglish (Roman),
     keeping the assistant target (intent+slots) identical.
  3. Validate every generated example: JSON parses, intent in allowed set,
     slot values plausible.
  4. Deduplicate, shuffle, split train/eval (85/15), write data/train.jsonl
     and data/eval.jsonl.

Run zero-shot first to validate the pipeline, then use this to scale up.

Notes:
- This calls your served model (vLLM) or any API. Point BASE_URL/MODEL at it.
- Keep the assistant target BYTE-IDENTICAL to the seed — only the user turn varies.
- Do NOT paraphrase tool-result formatting targets numerically; vary only phrasing.
"""

import json, glob, random, re, os, time
from collections import defaultdict
import requests

random.seed(42)

# ---- config ----
BASE_URL = os.environ.get("AUG_BASE_URL", "http://localhost:8001/v1")
MODEL    = os.environ.get("AUG_MODEL", "out/bank-8b-merged")  # or a strong teacher model
PARAPHRASES_PER_SEED = 6          # tune up for more data
ALLOWED_INTENTS = {"open_fixed_deposit","open_savings","account_statement",
                   "balance_inquiry","transaction_failure","raise_complaint",
                   "help_knowledge","fallback"}
SEED_GLOB = "seed_data/*.jsonl"
OUT_DIR = "data"

LANG_MIX = ["English", "Hindi (Devanagari script)", "Hinglish (Hindi-English code-mixed, Roman script)"]

PARAPHRASE_PROMPT = """You are generating training data for a banking assistant.
Rewrite the following user message into {n} natural variations in {lang}.
Keep the MEANING and any numbers/amounts/tenures EXACTLY the same.
Vary phrasing, politeness, word order, and filler words like a real customer would.
Return ONLY a JSON array of strings, nothing else.

Original user message: {text}"""


def call_llm(prompt: str) -> str:
    r = requests.post(f"{BASE_URL}/chat/completions", json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8, "max_tokens": 512,
    }, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def extract_json_array(text: str):
    # strip code fences and grab the first [...] block
    text = re.sub(r"```(json)?", "", text).strip()
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
        return [s for s in arr if isinstance(s, str) and s.strip()]
    except json.JSONDecodeError:
        return []


def load_seeds():
    seeds = []
    for path in glob.glob(SEED_GLOB):
        for line in open(path):
            line = line.strip()
            if line:
                seeds.append(json.loads(line))
    return seeds


def get_user_turn(ex):
    for m in ex["messages"]:
        if m["role"] == "user":
            return m["content"]
    return None


def set_user_turn(ex, new_text):
    ex = json.loads(json.dumps(ex))  # deep copy
    for m in ex["messages"]:
        if m["role"] == "user":
            m["content"] = new_text
            break
    return ex


def is_classification_seed(ex):
    # has a 'tool' role -> it's a formatting/RAG seed; don't paraphrase user numerically
    return not any(m["role"] == "tool" for m in ex["messages"])


def validate(ex):
    """Validate a classification/slot example's assistant target."""
    target = ex["messages"][-1]["content"]
    try:
        obj = json.loads(target)
    except json.JSONDecodeError:
        return False
    if "intent" in obj:
        return obj["intent"] in ALLOWED_INTENTS
    if "action" in obj:
        return obj["action"] in {"ask", "tool_call"}
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    seeds = load_seeds()
    print(f"loaded {len(seeds)} seeds")

    augmented = list(seeds)  # keep originals
    seen = set(get_user_turn(s) for s in seeds)

    for i, seed in enumerate(seeds):
        if not is_classification_seed(seed):
            # formatting/RAG: keep as-is (don't risk corrupting numbers)
            continue
        user_text = get_user_turn(seed)
        if not user_text:
            continue
        lang = LANG_MIX[i % len(LANG_MIX)]
        prompt = PARAPHRASE_PROMPT.format(n=PARAPHRASES_PER_SEED, lang=lang, text=user_text)
        try:
            variations = extract_json_array(call_llm(prompt))
        except Exception as e:
            print(f"  seed {i}: LLM error {e}; skipping")
            continue
        for v in variations:
            v = v.strip()
            if v and v not in seen:
                new_ex = set_user_turn(seed, v)
                if validate(new_ex):
                    augmented.append(new_ex)
                    seen.add(v)
        if (i + 1) % 10 == 0:
            print(f"  processed {i+1}/{len(seeds)} seeds, total={len(augmented)}")
        time.sleep(0.05)

    # dedupe by (user_turn, target)
    uniq = {}
    for ex in augmented:
        key = (get_user_turn(ex), ex["messages"][-1]["content"])
        uniq[key] = ex
    final = list(uniq.values())
    random.shuffle(final)

    split = int(len(final) * 0.85)
    train, evald = final[:split], final[split:]

    with open(f"{OUT_DIR}/train.jsonl", "w") as f:
        for ex in train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(f"{OUT_DIR}/eval.jsonl", "w") as f:
        for ex in evald:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # quick label distribution report
    dist = defaultdict(int)
    for ex in final:
        try:
            obj = json.loads(ex["messages"][-1]["content"])
            dist[obj.get("intent", obj.get("action", "format/rag"))] += 1
        except Exception:
            dist["format/rag"] += 1
    print(f"\nfinal: {len(final)} examples ({len(train)} train / {len(evald)} eval)")
    print("label distribution:")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {k:24s} {v}")


if __name__ == "__main__":
    main()
