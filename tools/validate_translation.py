#!/usr/bin/env python3
"""
翻譯輸出驗證工具：偵測 LLM 雙語 pass 產生的垃圾譯文，供重翻腳本過濾。

偵測模式：
  1. 自雙語：譯文含「X (X)」金屬/專有名詞對自己加括號（如 Adamant (Adamant) 短劍）。
  2. 單行 key 塞長段落：key 不含 <br> 但譯文含 ≥2 個 <br><br>（如 Minimum requirements: 被誤植成整段描述）。
  3. 羅馬字重複：譯文含「(X) I (X I)」重複編號。
  4. PUA / 替換字元。
  5. 結構失真：譯文 <col>/<str>/<red> 標籤數與 key 差異過大。

用法：
  過濾單一譯文：  python3 validate_translation.py --check '<key>' '<譯文>'
  掃描 .tbl：     python3 validate_translation.py --tbl translations_client.tbl
  掃描 server 表：python3 validate_translation.py --json translations_zh-tw.json
"""
import argparse
import re
import sys

CJK = re.compile(r'[\u4e00-\u9fff]')
PUA = re.compile(r'[\ue000-\uf8ff\ufffd]')
SELF_BI = re.compile(r'(?i)(Adamant|Mithril|Rune|Bronze|Iron|Steel|Black|White|Dragon|Adam|Addy|Mith)\s*\(\s*\1')
ROMAN_DUP = re.compile(r'\(([^)]*)\)\s*([IVX0-9]+)\s*\(\s*\1\s*\2\s*\)')


def is_garbage(key: str, val: str) -> str:
    """回傳問題描述；無問題回傳空字串。"""
    if not val:
        return "空譯文"
    if PUA.search(val):
        return "含私人使用區/替換字元"
    if SELF_BI.search(val):
        return "自雙語 X (X)"
    if ROMAN_DUP.search(val):
        return "羅馬字重複"
    # 單行 key 塞長段落：key 無 <br> 但譯文含大量 <br><br>
    key_br = key.count('<br>')
    val_br = val.count('<br><br>')
    if key_br == 0 and val_br >= 2:
        return "單行 key 塞長段落(%d個<br><br>)" % val_br
    # 結構失真：<col> 開關不平衡
    if val.count('<col') != val.count('</col>') and '<col' in val:
        return "col 標籤不平衡"
    # 譯文幾乎全英文但 key 是英文句（可能漏翻）
    if len(val) > 6 and not CJK.search(val) and sum(1 for c in val if c.isalpha()) / max(len(val), 1) > 0.7:
        return "疑似漏翻(無中文)"
    return ""


def check_pair(key, val, verbose=True):
    issue = is_garbage(key, val)
    if verbose and issue:
        print("  [%s] %s\n      K: %s\n      V: %s" % (issue, key[:40], key[:50], val[:50]))
    return issue


def main():
    ap = argparse.ArgumentParser(description="翻譯輸出驗證")
    ap.add_argument("--check", nargs=2, metavar=("KEY", "VAL"), help="檢查單一 key/val 對")
    ap.add_argument("--tbl", help="掃描 translations_client.tbl")
    ap.add_argument("--json", help="掃描 translations_zh-tw.json")
    args = ap.parse_args()

    if args.check:
        issue = is_garbage(args.check[0], args.check[1])
        print(issue if issue else "OK")
        sys.exit(1 if issue else 0)

    bad = 0
    if args.tbl:
        data = open(args.tbl, 'rb').read().split(b'\0')
        pairs = [(data[i].decode('utf-8', 'replace'), data[i+1].decode('utf-8', 'replace'))
                 for i in range(0, len(data) - 1, 2)]
        print("掃描 .tbl（%d 對）..." % len(pairs))
        for k, v in pairs:
            if check_pair(k, v):
                bad += 1
    if args.json:
        import json
        d = json.load(open(args.json))
        print("掃描 server 表（%d 條）..." % len(d))
        for k, v in d.items():
            if check_pair(k, v):
                bad += 1
    print("共 %d 條疑似問題" % bad)


if __name__ == "__main__":
    main()