#!/usr/bin/env python3
"""
翻譯表簡→繁後處理（opencc s2twp）。
確保 LLM 輸出的正體中文一致性（hy-mt2-7b 偶爾漏出簡體字）。

用法：
  ./s2tw_fix.py translations/zh-tw/strings.json [--skip-list glossary.tsv]

選項：
  --skip-list <tsv>  術語表中已訂義的 en->zh-tw 值不覆寫（優先保留人工/術語表譯法）
"""
import argparse
import json

def main():
    ap = argparse.ArgumentParser(description="翻譯表簡→繁後處理")
    ap.add_argument("table", help="翻譯表 JSON 路徑")
    ap.add_argument("--skip-list", help="術語表 TSV（其 zh-tw 值不覆寫）")
    args = ap.parse_args()

    import opencc
    converter = opencc.OpenCC("s2twp")

    skip = set()
    if args.skip_list:
        with open(args.skip_list, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[1]:
                    skip.add(parts[1])

    with open(args.table, encoding="utf-8") as f:
        table = json.load(f)

    changed = 0
    for e in table:
        zh = e.get("zh-tw")
        if not zh or zh in skip:
            continue
        fixed = converter.convert(zh)
        if fixed != zh:
            e["zh-tw"] = fixed
            changed += 1

    with open(args.table, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=2)
    print(f"完成：修正 {changed} 條簡體滲入")

if __name__ == "__main__":
    main()
