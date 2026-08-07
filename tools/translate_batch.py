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
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "5"))
MAX_TERMS = int(os.environ.get("MAX_TERMS", "60"))
TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))

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
                if len(parts) >= 2 and parts[0] and parts[1]:
                    glossary[parts[0]] = parts[1]
    return glossary

def select_relevant_terms(texts, glossary, max_terms=MAX_TERMS):
    """動態選取該批字串中實際出現的術語（避免 9000 條全塞拖慢）。"""
    if not glossary:
        return {}
    blob = " ".join(texts).lower()
    relevant = {}
    # 依長度排序，長術語優先（減少短詞誤配）
    for en, zh in sorted(glossary.items(), key=lambda kv: -len(kv[0])):
        if en.lower() in blob:
            relevant[en] = zh
            if len(relevant) >= max_terms:
                break
    return relevant

def build_prompt(texts, glossary, bilingual=False):
    """gemma 專用 prompt：術語區塊 + 台灣正體 + 片段提示 + 編號輸出。

    bilingual=True：專有名詞（人名/地名/物品名）音譯成中文，輸出「中文 (English)」格式。
    """
    relevant = select_relevant_terms(texts, glossary)
    gloss_lines = "\n".join(f"{en} translates to {zh}" for en, zh in relevant.items())
    gloss_block = (
        f"\nReference translations (use these EXACT terms when they appear):\n{gloss_lines}\n"
        if gloss_lines else ""
    )
    formatted = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    if bilingual:
        extra_rules = (
            "- These are NAMES (NPC names, place names, item/object names).\n"
            "- Transliterate NPC names and place names into Chinese phonetic text; translate item/object names into Chinese.\n"
            "- Output format: 「中文 (English original)」 — Chinese first, then the original English in half-width parentheses.\n"
            "- Never leave the output as English only; always provide the Chinese translation."
        )
        return f"""你是 RuneScape 2009 遊戲的台灣正體中文翻譯。
請翻譯以下 {len(texts)} 個名稱。{gloss_block}
規則：
- 只輸出編號翻譯，每個一行。
- 人名、地名必須音譯成中文（如 Bigface Oz → 大臉奧茲）；物品/物件名意譯成中文。
- 輸出格式為「中文 (原始英文)」，中文在前，英文用半形括號放在後。
- 不允許只輸出英文；一定給出中文。
- 照抄上方術語表的用法，不得更改。
{formatted}"""
    return f"""You are a professional game translator for RuneScape 2009.
Translate the following {len(texts)} English lines into Traditional Chinese (Taiwan, 正體中文).{gloss_block}
Rules:
- Output ONLY the numbered translations, one per line.
- Use the reference translations for the terms listed above without exception.
- Some lines may be fragments joined with other text at runtime; translate faithfully without adding or removing meaning.
- Keep <col=...>, <br>, <img=...> and other markup tags exactly as they are (do not translate or remove them).
- Do not add explanations.
{formatted}"""

def build_book_prompt(lines, glossary):
    """書籍分組 prompt：整段上下文一起送，輸出逐行翻譯。lines = [(line_no, text), ...]"""
    relevant = select_relevant_terms([t for _, t in lines], glossary)
    gloss_lines = "\n".join(f"{en} translates to {zh}" for en, zh in relevant.items())
    gloss_block = (
        f"\nReference translations (use these EXACT terms when they appear):\n{gloss_lines}\n"
        if gloss_lines else ""
    )
    formatted = "\n".join(f"L{n}: {t}" for n, t in lines)
    return f"""You are a professional game translator for RuneScape 2009.
Translate a book passage into Traditional Chinese (Taiwan, 正體中文).{gloss_block}
The text is split across display lines (L55, L56, ...). Translate each line faithfully so the whole passage reads naturally.
Keep <col=...> tags exactly as they are. Output ONLY the lines, one per line, using the same L<number> prefix:
{formatted}"""

def translate_batch_ollama(texts, glossary):
    prompt = build_prompt(texts, glossary)
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": TEMPERATURE},
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json().get("response", "")
    return parse_output(content, len(texts))

def translate_batch_openai(texts, glossary, bilingual=False):
    """相容 OpenAI 風格 /v1/chat/completions"""
    prompt = build_prompt(texts, glossary, bilingual)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a professional game translator for RuneScape 2009, translating English into Traditional Chinese (Taiwan)."},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_output(content, len(texts))

def translate_book_openai(lines, glossary):
    """書籍分組翻譯（OpenAI 風格）。lines = [(line_no, text), ...]，回傳 {line_no: 譯文}"""
    prompt = build_book_prompt(lines, glossary)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a professional game translator for RuneScape 2009, translating English into Traditional Chinese (Taiwan)."},
            {"role": "user", "content": prompt},
        ],
        "temperature": TEMPERATURE,
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return parse_book_output(content)

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

def parse_book_output(content):
    """解析書籍分組翻譯輸出。回傳 {line_no: 譯文}。"""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r"^L(\d+)[\s:\.\)]*\s*(.+)$", line)
        if m:
            result[int(m.group(1))] = sanitize(m.group(2))
    return result

def sanitize(text):
    """清理模型輸出的雜訊：多餘空白、行尾符號、控制字元、重複空格。"""
    if not text:
        return text
    # 移除行尾反斜線（模型偶發）
    text = re.sub(r"\\\s*$", "", text.strip())
    # 移除控制字元
    text = "".join(ch for ch in text if ch >= " " or ch == "\t")
    # 壓縮連續空白
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

def main():
    ap = argparse.ArgumentParser(description="2009scape 翻譯表批次翻譯")
    ap.add_argument("table", help="翻譯表 JSON 路徑")
    ap.add_argument("--glossary", help="術語表 TSV 路徑")
    ap.add_argument("--dry-run", action="store_true", help="只輸出將翻譯的條目，不呼叫 API")
    ap.add_argument("--update-glossary", action="store_true",
                    help="翻譯過程中把已翻譯術語動態併入 glossary（供後續批次注入，適合術語表翻譯）")
    ap.add_argument("--bilingual", action="store_true",
                    help="名稱模式：人名/地名音譯、物品/物件名意譯，輸出「中文 (English)」格式")
    args = ap.parse_args()

    with open(args.table, "r", encoding="utf-8") as f:
        table = json.load(f)
    glossary = load_glossary(args.glossary)

    # 先標記 concat 片段為 skip（執行期拼接，攔截器永不命中，不浪費 LLM）
    skip_count = 0
    for e in table:
        if e.get("fragment_type") == "concat" and not e.get("zh-tw"):
            e["status"] = "skip"
            skip_count += 1
    print(f"標記 {skip_count} 條 concat 片段為 skip")

    # 收集未翻譯且未跳過的條目
    pending = [(i, e) for i, e in enumerate(table) if not e.get("zh-tw") and e.get("status") != "skip"]
    print(f"共 {len(table)} 條，待翻譯 {len(pending)} 條")

    if args.dry_run:
        for i, e in pending[:20]:
            print(f"  {i}: {e['en']}")
        print("... (dry-run，未呼叫 API)")
        return

    # 依 group_id 分組 bookline（先翻譯，因為需整組上下文）
    from collections import defaultdict
    book_groups = defaultdict(list)
    for i, e in pending:
        if e.get("fragment_type") == "bookline" and e.get("group_id"):
            book_groups[e["group_id"]].append((i, e))

    def api_call(lines, is_book, bilingual):
        for attempt in range(MAX_RETRIES + 1):
            try:
                if is_book:
                    if "/api/generate" in API_URL:
                        return {}  # ollama 暫不支援書本分組
                    return translate_book_openai(lines, glossary)
                if "/api/generate" in API_URL:
                    return translate_batch_ollama([t for _, t in lines], glossary)
                return translate_batch_openai([t for _, t in lines], glossary, bilingual)
            except requests.RequestException as e:
                if attempt >= MAX_RETRIES:
                    print(f"!! API 持續失敗（{e}），跳過，下次續傳", file=sys.stderr)
                    return {}
                print(f"!! API 錯誤（{e}），{attempt + 1}/{MAX_RETRIES} 重試中...", file=sys.stderr)
                time.sleep(min(2 ** (attempt + 1), 60))
        return {}

    # 先處理 bookline 分組
    for gid, entries in book_groups.items():
        entries.sort(key=lambda x: x[1].get("line_no", 0))
        lines = [(e["line_no"], e["en"]) for _, e in entries]
        print(f">> 書籍 {gid} ({len(entries)} 行) ...")
        translated = api_call(lines, True, args.bilingual)
        for i, e in entries:
            t = translated.get(e["line_no"])
            if t:
                e["zh-tw"] = t
                e["status"] = "translated"
            else:
                print(f"!! 書籍行 {e['line_no']} 無輸出: {e['en']}", file=sys.stderr)

    # 剩餘條目（非 bookline）
    remaining = [(i, e) for i, e in pending if e.get("fragment_type") != "bookline"]

    # 批次處理
    for batch_start in range(0, len(remaining), TEXTS_PER_BATCH):
        batch = remaining[batch_start:batch_start + TEXTS_PER_BATCH]
        texts = [(e["en"]) for _, e in batch]
        print(f">> 批次 {batch_start//TEXTS_PER_BATCH + 1}: {len(texts)} 條 ...")

        translated = api_call([(i, t) for i, t in enumerate(texts)], False, args.bilingual)

        for offset, (idx, entry) in enumerate(batch):
            t = translated.get(offset + 1)
            if t:
                t = sanitize(t)
                if t:
                    entry["zh-tw"] = t
                    entry["status"] = "translated"
                    # 術語迭代：翻譯完成的術語併入 glossary，供後續批次注入
                    if args.update_glossary:
                        glossary[entry["en"]] = t
                    continue
            print(f"!! 第 {offset+1} 條無輸出: {entry['en']}", file=sys.stderr)

        # 批次間即時存檔（斷點續傳）
        with open(args.table, "w", encoding="utf-8") as f:
            json.dump(table, f, ensure_ascii=False, indent=2)
        print(f">> 已存檔（累計完成 {sum(1 for e in table if e.get('zh-tw'))}/{len(table)}）")
        time.sleep(REQUEST_DELAY)

    # 最終存檔（確保書本分組結果寫入）
    with open(args.table, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)
    print("完成。")

if __name__ == "__main__":
    main()
