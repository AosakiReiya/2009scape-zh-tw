#!/usr/bin/env python3
"""
2009scape 翻譯表批次翻譯工具
呼叫本地 LLM API（Ollama / llama.cpp / LM Studio 等）翻譯翻譯表。

特性：
- 翻譯表分離（不直接改原始碼/JSON）
- 斷點續傳（已翻譯的跳過）
- 術語表強制（glossary.tsv 中的專有名詞統一）
- 批次處理 + 延遲控制

用法：
  ./translate_batch.py translations/zh-tw/strings.json [--glossary glossary.tsv]

翻譯表格式（extract_strings.py 輸出）：
  [{"en": "...", "zh-tw": "", "source": "...", "status": "untranslated"}, ...]
"""

import argparse
import json
import os
import re
import sys
import time

import requests

# ==================== 配置 ====================
API_URL = os.environ.get("LLM_API_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.environ.get("LLM_MODEL", "qwen2.5:7b")
TEXTS_PER_BATCH = int(os.environ.get("TEXTS_PER_BATCH", "30"))
REQUEST_DELAY = float(os.environ.get("REQUEST_DELAY", "1.0"))
TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "180"))

# ==================== 工具函數 ====================

def load_glossary(path):
    """載入術語表（TSV: en\tzh-tw\t備註）"""
    glossary = {}
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("en\t"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2 and parts[0]:
                    glossary[parts[0]] = parts[1]
    return glossary

def build_prompt(texts, glossary):
    gloss_lines = "\n".join(f"{en} = {zh}" for en, zh in glossary.items())
    gloss_block = f"\n=== 術語表（必須使用） ===\n{gloss_lines}\n" if gloss_lines else ""
    formatted = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    return f"""Translate {len(texts)} lines of English to Traditional Chinese (Taiwan, 正體中文).{gloss_block}
Output ONLY translated text, one per line, keep numbering:
{formatted}"""

def translate_batch_ollama(texts, glossary):
    prompt = build_prompt(texts, glossary)
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json().get("response", "")
    return parse_output(content, len(texts))

def translate_batch_openai(texts, glossary):
    """相容 OpenAI 風格 /v1/chat/completions"""
    prompt = build_prompt(texts, glossary)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a professional game translator."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_output(content, len(texts))

def parse_output(content, expected):
    """解析模型輸出，提取編號翻譯行。"""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r"^(\d+)[\.\)]?\s*(.+)$", line)
        if m:
            idx = int(m.group(1))
            result[idx] = m.group(2).strip()
    # 補齊：有些模型只輸出翻譯沒有編號
    if len(result) < expected:
        bare = [line.strip() for line in content.splitlines() if line.strip() and not re.match(r"^\d+", line.strip())]
        idx = 1
        for t in bare:
            if idx not in result:
                result[idx] = t
            idx += 1
    return result

def main():
    ap = argparse.ArgumentParser(description="2009scape 翻譯表批次翻譯")
    ap.add_argument("table", help="翻譯表 JSON 路徑")
    ap.add_argument("--glossary", help="術語表 TSV 路徑")
    ap.add_argument("--dry-run", action="store_true", help="只輸出將翻譯的條目，不呼叫 API")
    args = ap.parse_args()

    with open(args.table, "r", encoding="utf-8") as f:
        table = json.load(f)
    glossary = load_glossary(args.glossary)

    # 收集未翻譯條目
    pending = [(i, e) for i, e in enumerate(table) if not e.get("zh-tw")]
    print(f"共 {len(table)} 條，待翻譯 {len(pending)} 條")

    if args.dry_run:
        for i, e in pending[:20]:
            print(f"  {i}: {e['en']}")
        print("... (dry-run，未呼叫 API)")
        return

    # 批次處理
    for batch_start in range(0, len(pending), TEXTS_PER_BATCH):
        batch = pending[batch_start:batch_start + TEXTS_PER_BATCH]
        texts = [e["en"] for _, e in batch]
        print(f">> 批次 {batch_start//TEXTS_PER_BATCH + 1}: {len(texts)} 條 ...")

        try:
            # 依 API_URL 判斷格式
            if "/api/generate" in API_URL:
                translated = translate_batch_ollama(texts, glossary)
            else:
                translated = translate_batch_openai(texts, glossary)
        except requests.RequestException as e:
            print(f"!! API 錯誤（{e}），跳過此批次，下次續傳", file=sys.stderr)
            break

        for offset, (idx, entry) in enumerate(batch):
            t = translated.get(offset + 1)
            if t:
                entry["zh-tw"] = t
                entry["status"] = "translated"
            else:
                print(f"!! 第 {offset+1} 條無輸出: {entry['en']}", file=sys.stderr)

        # 批次間即時存檔（斷點續傳）
        with open(args.table, "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=2)
        print(f">> 已存檔（累計完成 {sum(1 for e in table if e.get('zh-tw'))}/{len(table)}）")
        time.sleep(REQUEST_DELAY)

    print("完成。")

if __name__ == "__main__":
    main()
