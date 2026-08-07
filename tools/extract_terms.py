#!/usr/bin/env python3
"""
2009scape 專有名詞術語萃取工具
從 config JSON（NPC/道具/商店名）萃取所有專有名詞，加上既有術語表。

產出格式（JSON 陣列）：
  [{"en": "Hans", "zh-tw": "", "source": "npc", "status": "untranslated"}, ...]
"""
import argparse
import json
import os
import re

BLACKLIST_SUBSTR = [
    "=", "{", "}", "${", "%", "^", "\\", "\"", ";",
]

def looks_term(s):
    if len(s) < 2:
        return False
    if not any(c.isalpha() for c in s):
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    for b in BLACKLIST_SUBSTR:
        if b in s:
            return False
    # 排除整串大寫（多半是縮寫/代碼，如 VARP, ID）
    if s.isupper() and len(s) <= 5:
        return False
    # 排除單一字母
    if len(s) == 1:
        return False
    return True

def load_npc(path):
    res = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for e in data:
        if isinstance(e, dict) and e.get("name") and looks_term(e["name"]):
            res.append({"en": e["name"], "zh-tw": "", "source": "npc", "status": "untranslated"})
    return res

def load_items(path):
    res = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for e in data:
        if isinstance(e, dict) and e.get("name") and looks_term(e["name"]):
            res.append({"en": e["name"], "zh-tw": "", "source": "item", "status": "untranslated"})
    return res

def load_shops(path):
    res = []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for e in data:
        if isinstance(e, dict) and e.get("title") and looks_term(e["title"]):
            res.append({"en": e["title"], "zh-tw": "", "source": "shop", "status": "untranslated"})
    return res

def load_existing_glossary(path):
    res = []
    if not os.path.exists(path):
        return res
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2 and parts[0] and not parts[0].startswith("en\t"):
                res.append({"en": parts[0], "zh-tw": parts[1], "source": "glossary", "status": "translated" if parts[1] else "untranslated"})
    return res

def main():
    ap = argparse.ArgumentParser(description="專有名詞術語萃取")
    ap.add_argument("--npc-config", required=True)
    ap.add_argument("--item-config", required=True)
    ap.add_argument("--shop-config", required=True)
    ap.add_argument("--glossary", help="既有術語表 TSV")
    ap.add_argument("--out", default="terms.json")
    ap.add_argument("--dedupe", action="store_true")
    args = ap.parse_args()

    all_terms = []
    all_terms += load_npc(args.npc_config)
    all_terms += load_items(args.item_config)
    all_terms += load_shops(args.shop_config)
    if args.glossary:
        all_terms += load_existing_glossary(args.glossary)

    if args.dedupe:
        seen = set()
        deduped = []
        for t in all_terms:
            if t["en"] not in seen:
                seen.add(t["en"])
                deduped.append(t)
        all_terms = deduped

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(all_terms, f, ensure_ascii=False, indent=2)

    from collections import Counter
    c = Counter(t["source"] for t in all_terms)
    print(f"萃取完成: {len(all_terms)} 條 -> {args.out}")
    print(f"  來源分佈: {dict(c)}")

if __name__ == "__main__":
    main()
