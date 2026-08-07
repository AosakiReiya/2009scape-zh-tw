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
# 注意：此處過濾的是「萃取出的字串內容」，不是原始碼行。
# 只用於濾掉明確的技術/路徑雜訊；Kotlin 關鍵字（val/fun/var/import）不在此列，
# 因為它們會誤傷正常英文句子（如 "Survival Guide" 含 "val "、"important" 含 "import"）。
BLACKLIST_SUBSTR = [
    "java.", "kotlin.", "org.", "com.", "core.", "content.", "api.",
    ".kt", ".java", "package ", "TODO", "FIXME", "//", "/*", "*/",
    "http://", "https://",
]

# 以連接字/冠詞/所有格/be 動詞等結尾的片段特徵（執行期拼接或書籍斷行）
# BookLine("...", line_no) 擷取
BOOKLINE_RE = re.compile(r'BookLine\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*(\d+)\s*\)')
# 分頁界限：BookLine 之後緊接 "), " 再出現 Page( / PageSet( / ), Page( 等
PAGE_BOUNDARY_RE = re.compile(r'PageSet?\(|\)\s*,\s*Page\(|\)\s*\)\s*,\s*Page\(')

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

def classify_fragment(s, is_bookline):
    """判定片段類型。
    - template: 含 ${} 的 Kotlin 模板（執行期代入，照翻）
    - bookline: BookLine 斷行（需按上下文分組翻譯）
    - concat: 執行期拼接片段（以尾隨空格結尾，攔截器永不命中，跳過）
    - 其他: 正常完整句
    """
    if is_bookline:
        return "bookline"
    if "${" in s:
        return "template"
    # 只有「以空格結尾」才是明確的執行期拼接片段
    # （以連接字結尾可能是完整短句如 "Rocking Out"，不宜誤殺）
    if s.endswith(" "):
        return "concat"
    return "normal"

def _triple_to_entry(m, results, rel):
    """三引號多行字串：合併為單行加入 results，並以佔位符回傳（避免被 "..." 正則重複抓取）。"""
    s = re.sub(r"\s+", " ", m.group(1)).strip()
    if looks_translatable(s):
        results.append({"en": s, "zh-tw": "", "source": rel, "status": "untranslated",
                        "fragment_type": "normal"})
    return '"""""'

def extract_from_kotlin(path):
    """從 .kt 原始碼提取字串常數池。"""
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        return results
    rel = os.path.relpath(path)

    # 依原始碼順序解析 BookLine，並偵測分頁界限分組
    bookline_entries = []  # (group_id, en, line_no)
    group_id = 0
    prev_end = None
    for m in BOOKLINE_RE.finditer(src):
        s = m.group(1)
        if not looks_translatable(s):
            continue
        if prev_end is not None and PAGE_BOUNDARY_RE.search(src[prev_end:m.start()]):
            group_id += 1
        bookline_entries.append((group_id, s, int(m.group(2))))
        prev_end = m.end()

    # 抓 Kotlin 三引號多行字串（"""..."""），內容合併為單行；移除已抓區段避免與下方 "..." 重複
    src = re.sub(r'"""(.*?)"""', lambda m: _triple_to_entry(m, results, rel), src, flags=re.S)

    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', src):
        s = m.group(1)
        if not looks_translatable(s):
            continue
        entry = {"en": s, "zh-tw": "", "source": rel, "status": "untranslated",
                 "fragment_type": classify_fragment(s, False)}
        # 若屬 BookLine，覆寫為 bookline 型態並附加分組資訊
        for gid, be, ln in bookline_entries:
            if be == s:
                entry["fragment_type"] = "bookline"
                entry["group_id"] = f"{rel}#{gid}"
                entry["line_no"] = ln
                break
        results.append(entry)
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
                    results.append({"en": v, "zh-tw": "", "source": rel, "field": k,
                                    "status": "untranslated", "fragment_type": "normal"})
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
                if (fn.endswith(".kt") or fn.endswith(".java")) and not fn.endswith("Test.kt"):
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
