#!/usr/bin/env python3
"""
evaluate.py — Measure the fine-tuned model on the held-out eval set.

Reports the metrics named in the build plan:
  - JSON validity rate   (did the model emit parseable JSON when required?)
  - Intent accuracy       (exact intent match)
  - Slot F1               (token-level over slot key:value pairs)
  - Tool-call correctness (right tool + right args, for action examples)

Run this BOTH on the un-fine-tuned base (Phase A baseline) and after QLoRA,
and again after 4-bit quantization to catch any JSON-validity regression.
"""

import json, os, re
import requests
from collections import defaultdict

BASE_URL = os.environ.get("EVAL_BASE_URL", "http://localhost:8001/v1")
MODEL    = os.environ.get("EVAL_MODEL", "out/bank-8b-merged")
EVAL_FILE = os.environ.get("EVAL_FILE", "data/eval.jsonl")


def call(messages):
    r = requests.post(f"{BASE_URL}/chat/completions", json={
        "model": MODEL, "messages": messages,
        "temperature": 0.0, "max_tokens": 256,
    }, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json(text):
    text = re.sub(r"```(json)?", "", text).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def slot_prf(gold: dict, pred: dict):
    gold_set = {f"{k}={v}" for k, v in (gold or {}).items()}
    pred_set = {f"{k}={v}" for k, v in (pred or {}).items()}
    if not gold_set and not pred_set:
        return 1.0, 1.0, 1.0
    tp = len(gold_set & pred_set)
    p = tp / len(pred_set) if pred_set else 0.0
    r = tp / len(gold_set) if gold_set else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def main():
    examples = [json.loads(l) for l in open(EVAL_FILE) if l.strip()]
    # Only score examples whose target is JSON (classification/slot/action),
    # skip free-text formatting/RAG targets here (eval those qualitatively).
    n = 0
    json_valid = 0
    intent_correct = 0
    intent_total = 0
    f1_sum = 0.0
    f1_count = 0
    toolcall_correct = 0
    toolcall_total = 0

    for ex in examples:
        msgs = ex["messages"]
        if any(m["role"] == "tool" for m in msgs):
            continue  # formatting/RAG handled separately
        gold = parse_json(msgs[-1]["content"])
        if gold is None:
            continue
        n += 1
        prompt_msgs = msgs[:-1]
        pred_text = call(prompt_msgs)
        pred = parse_json(pred_text)
        if pred is None:
            continue
        json_valid += 1

        if "intent" in gold:
            intent_total += 1
            if pred.get("intent") == gold["intent"]:
                intent_correct += 1
            _, _, f1 = slot_prf(gold.get("slots", {}), pred.get("slots", {}))
            f1_sum += f1; f1_count += 1

        if gold.get("action") == "tool_call":
            toolcall_total += 1
            if (pred.get("action") == "tool_call"
                    and pred.get("tool") == gold.get("tool")
                    and pred.get("args") == gold.get("args")):
                toolcall_correct += 1

    print(f"eval examples scored: {n}")
    print(f"JSON validity rate:   {json_valid}/{n} = {json_valid/n:.1%}" if n else "n/a")
    if intent_total:
        print(f"Intent accuracy:      {intent_correct}/{intent_total} = {intent_correct/intent_total:.1%}")
        print(f"Slot F1 (avg):        {f1_sum/f1_count:.3f}")
    if toolcall_total:
        print(f"Tool-call correctness:{toolcall_correct}/{toolcall_total} = {toolcall_correct/toolcall_total:.1%}")


if __name__ == "__main__":
    main()
