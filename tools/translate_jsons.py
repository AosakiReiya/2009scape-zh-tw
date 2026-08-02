#!/usr/bin/env python3
"""
將翻譯表回寫到 2009scape config JSON。

用法：
  ./translate_jsons.py --table <strings.json> --configs <configs目錄> [--key name]

翻譯表中的 source 欄位（如 "item_configs.json"）與 field 欄位
（name / examine / title）決定寫入位置。符合的英文字串以中文覆寫。

注意：這是針對「伺服器 config 覆蓋」途徑的工具。
cache 中的名稱（obj.dat/npc.dat）需另以 cache 編輯工具處理。
"""

import argparse
import json
import os

TEXT_KEYS = ("name", "examine", "title", "destroy_message", "verb")

def build_lookup(table):
    """建 en -> zh-tw 對照（優先 field 精確）。"""
    lookup = {}
    for e in table:
        zh = e.get("zh-tw")
        if zh:
            lookup[e["en"]] = zh
    return lookup

def main():
    ap = argparse.ArgumentParser(description="翻譯表回寫 config JSON")
    ap.add_argument("--table", required=True, help="翻譯表 JSON")
    ap.add_argument("--configs", required=True, help="config JSON 目錄")
    ap.add_argument("--dry-run", action="store_true", help="只顯示將改動的內容")
    args = ap.parse_args()

    with open(args.table, "r", encoding="utf-8") as f:
        table = json.load(f)
    lookup = build_lookup(table)

    changed = 0
    for fn in sorted(os.listdir(args.configs)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(args.configs, fn)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def walk(obj):
            nonlocal changed
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if k in TEXT_KEYS and isinstance(v, str) and v in lookup:
                        if args.dry_run:
                            print(f"  [{fn}] {k}: {v!r} -> {lookup[v]!r}")
                        else:
                            obj[k] = lookup[v]
                        changed += 1
                    elif isinstance(v, (dict, list)):
                        walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)
        if not args.dry_run and changed:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"完成：{'預覽' if args.dry_run else '回寫'} {changed} 個欄位")

if __name__ == "__main__":
    main()
