#!/usr/bin/env python3
"""
將術語表 JSON（terms.json）轉為完整 glossary.tsv。

用法：
  ./terms_to_glossary.py translations/zh-tw/terms.json --out translations/glossary.tsv
"""
import argparse
import json

def main():
    ap = argparse.ArgumentParser(description="術語表 JSON → TSV")
    ap.add_argument("terms_json", help="術語表 JSON 路徑")
    ap.add_argument("--out", default="glossary.tsv")
    args = ap.parse_args()

    with open(args.terms_json, encoding="utf-8") as f:
        terms = json.load(f)

    rows = ["en\tzh-tw\t備註"]
    for t in terms:
        en = t.get("en", "")
        zh = t.get("zh-tw", "")
        if en and zh:
            rows.append(f"{en}\t{zh}\t{t.get('source','')}")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")

    print(f"完成: {len(rows)-1} 條術語 -> {args.out}")

if __name__ == "__main__":
    main()
