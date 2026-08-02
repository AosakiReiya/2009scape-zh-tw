#!/usr/bin/env python3
"""
2009scape 字串萃取工具
掃描伺服器 Kotlin 原始碼與 config JSON，輸出翻譯表骨架。

用法：
  ./extract_strings.py --server-src <path> [--configs <path>] [--out <path>]

輸出格式（JSON 陣列）：
  {
    "en": "Ho Ho Ho!",
    "zh-tw": "",
    "source": "content/.../SantaHolidayRandomDialogue.kt",
    "status": "untranslated"
  }
"""

import argparse
import json
import os
import re
import sys

# 只提取「像句子」的英文字串：含空格或較長，過濾 bytecode/套件名雜訊
SENTENCE_RE = re.compile(r"[A-Za-z][A-Za-z ]{2,}")
BLACKLIST_SUBSTR = [
    "java.", "kotlin.", "org.", "com.", "core.", "content.", "api.",
    "http", ".kt", ".java", "fun ", "val ", "var ", "import ", "package ",
    "import", "TODO", "FIXME", "//", "/*", "*/",
]

def looks_translatable(s):
    if len(s) < 3:
        return False
    if "\u0000" in s:
        return False
    # 過濾大量成對大括號/參數佔位（非句子，如 "val {0} = {1}"）
    if s.count("{") >= 2 and "}" in s and s.count("{") == s.count("}"):
        pass  # 仍可能是含 <col> 標籤的對話，保留
    if not SENTENCE_RE.search(s):
        return False
    if not any(c.isalpha() for c in s):
        return False
    for b in BLACKLIST_SUBSTR:
        if b in s:
            return False
    # 需要至少一個空格（濾掉單字/識別字）或長度 >= 12
    if " " not in s and len(s) < 12:
        return False
    # 過濾純技術符號串（只有標點/符號無實質單詞）
    words = [w for w in re.split(r"[^A-Za-z]+", s) if w]
    if not words:
        return False
    return True

def extract_from_kotlin(path):
    """從 .kt 原始碼提取字串常數池。"""
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        return results
    rel = os.path.relpath(path)
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', src):
        s = m.group(1)
        if looks_translatable(s):
            results.append({"en": s, "zh-tw": "", "source": rel, "status": "untranslated"})
    return results

def extract_from_json(path):
    """從 config JSON 提取 name / examine / title 等文字欄位。"""
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return results
    rel = os.path.relpath(path)
    TEXT_KEYS = ("name", "examine", "title", "destroy_message", "verb")
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in TEXT_KEYS and isinstance(v, str) and looks_translatable(v):
                    results.append({"en": v, "zh-tw": "", "source": rel, "field": k, "status": "untranslated"})
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(data)
    return results

def main():
    ap = argparse.ArgumentParser(description="2009scape 字串萃取")
    ap.add_argument("--server-src", required=True, help="伺服器 Kotlin 原始碼根目錄")
    ap.add_argument("--configs", help="config JSON 目錄")
    ap.add_argument("--out", default="strings.json", help="輸出翻譯表路徑")
    ap.add_argument("--dedupe", action="store_true", help="依 en 去重")
    args = ap.parse_args()

    all_results = []
    if args.server_src:
        for root, dirs, files in os.walk(args.server_src):
            if "/build/" in root or "/target/" in root:
                continue
            for fn in files:
                if fn.endswith(".kt") and not fn.endswith("Test.kt"):
                    all_results.extend(extract_from_kotlin(os.path.join(root, fn)))
    if args.configs:
        for fn in os.listdir(args.configs):
            if fn.endswith(".json"):
                all_results.extend(extract_from_json(os.path.join(args.configs, fn)))

    if args.dedupe:
        seen = set()
        deduped = []
        for r in all_results:
            if r["en"] not in seen:
                seen.add(r["en"])
                deduped.append(r)
        all_results = deduped

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"萃取完成: {len(all_results)} 條 -> {args.out}")

if __name__ == "__main__":
    main()
