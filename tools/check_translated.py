#!/usr/bin/env python3
"""
已翻譯表品質檢查工具：掃描 server (translations_zh-tw.json) 與 client (.tbl)，
偵測「已翻譯但漏翻/錯翻」的條目。

分類：
  A. 標點錯翻：英文句子 key → 純標點 / ≤2 字譯文（多行片段被誤翻成標點）。
  B. 譯文無中文的句子：非咒語/程式碼/擬聲但仍為英文譯文（漏翻或錯翻）。
  C. 名稱譯文無中文：名稱類（人名/地名/物品名）譯文仍是英文。
  D. 咒語標點污染：咒語/擬聲被加上中文標點（。？！）。

輸出：
  check_translated_report.txt  分類報告
  check_translated_fix.json    待修正清單（含類型，供清理/重翻腳本用）

用法：
  ./check_translated.py --json <translations_zh-tw.json> --tbl <translations_client.tbl>
"""
import argparse
import json
import re

CJK = re.compile(r'[\u4e00-\u9fff]')
PUNCT_ONLY = re.compile(r'^[。，、；：？！．.…,;:?!<> ]{1,3}$')

# 程式碼 / SQL / 模板特徵 → 不判定漏翻
CODE = re.compile(
    r'[\$:]|=>|->|\$\{|\{\{|::|@|\.get\(|\.set\(|\.name=|System\.|RSA_|label=\[|chunk:|obj=|flag|\bINSERT\b|\bSELECT\b|\bCREATE\b|\bUPDATE\b|\bDELETE\b|FROM |WHERE |VALUES|INTEGER|\bresult =|stage =|npc\(|player\(|item\(|;"|\\u|\\t|\^\d|^\d|\[old|Offer \$|timer\.|\.location|\.amount|ConfigFile|ComponentDefinition|ZoneBorders|WrapperID|_id |_value|_amount|_state|_type|_size|_flags|_tasks|_coins|duel_|price_index|bot_offers|player_offers|scoreboard|members|\.getRights|\.itemName|Message\\u|StatusUpdate|DUEL_|DROP_|COMMAND|IP_LOG')
# 咒語 / 擬聲 / 拉丁咒語特徵
SPELL = re.compile(
    r'^(Veni|Sall|Sent|Senven|Salm|Sallam|Klar|Sep|Dips|Dint|Sott|Ann|Mir|Sin|Snar|Brack|Vid|Av |Ra |Bow|Bur|Kar|Sch|Gr|Ukk|Amitus|En tanai|Su tana|Extralias|Holarius|Possessus|projectus|Castus|Absolutus|Defeati|the possessed|Present thyself|With least|and utmost|Es lem|Mi lov|Throwus|puro|Snarth|Tourniquet|Schl|Schorp|fnales|Dintenta|Sallamakar|Senventior|Brimhaven|Rimmington|Pollnivneach|Rellekka|Taverley|Yanille)', re.I)
# 名稱特徵（人名/地名，譯文無中文 → C 類）
NAME_HINT = re.compile(r'^[A-Z][a-z]+ [A-Z][a-z]+$|^[A-Z][a-z]+ \([A-Za-z]|\([0-9,]+\)$|^[A-Z][a-z]+')

def classify(key, val):
    """回傳問題類型；無問題回傳 None。"""
    if not val:
        return 'EMPTY'
    if val == key:
        # 譯文=原文：若像名稱/句子 → 漏翻
        if ' ' in key and len(key) >= 5 and re.search(r'[A-Za-z]{3,}', key):
            if not CODE.search(key):
                return 'C_SAME' if (NAME_HINT.match(key) and not SPELL.search(key)) else 'B_SAME'
        return None
    if CJK.search(val):
        # 譯文含中文：檢查咒語被加中文標點污染
        if SPELL.search(key) and re.search(r'[。？！]', val) and not CJK.search(val.replace('。', '').replace('？', '').replace('！', '')):
            return 'D_SPELL_PUNCT'
        return None
    # 譯文無中文
    if not re.search(r'[A-Za-z]{3,}', key):
        return None
    if PUNCT_ONLY.match(val) or (len(val.strip()) <= 2 and len(key) >= 15):
        return 'A_PUNCT'
    if CODE.search(key):
        return None
    if SPELL.search(key):
        return 'D_SPELL'
    return 'B_NEED_ZH'

def scan_table(table, src_label):
    """掃描一個 en→zh 表，回傳分類結果。"""
    result = {'A_PUNCT': [], 'B_NEED_ZH': [], 'B_SAME': [], 'C_SAME': [],
              'D_SPELL': [], 'D_SPELL_PUNCT': [], 'EMPTY': []}
    for k, v in table.items():
        c = classify(k, v)
        if c:
            result.setdefault(c, []).append((k, v))
    return result

def scan_tbl(path):
    data = open(path, 'rb').read().split(b'\0')
    return {data[i].decode('utf-8', 'replace'): data[i + 1].decode('utf-8', 'replace')
            for i in range(0, len(data) - 1, 2)}

def main():
    ap = argparse.ArgumentParser(description='已翻譯表品質檢查')
    ap.add_argument('--json', help='server 翻譯表')
    ap.add_argument('--tbl', help='client 翻譯表')
    ap.add_argument('--report', default='check_translated_report.txt')
    ap.add_argument('--fix', default='check_translated_fix.json')
    args = ap.parse_args()

    all_fix = []
    counts = {}
    with open(args.report, 'w', encoding='utf-8') as rp:
        for label, path in (('server', args.json), ('client', args.tbl)):
            if not path:
                continue
            table = json.load(open(path, encoding='utf-8')) if label == 'server' else scan_tbl(path)
            res = scan_table(table, label)
            rp.write(f"\n{'='*60}\n{label} 表 ({len(table)} 條)\n{'='*60}\n")
            cat_names = {
                'A_PUNCT': 'A. 標點錯翻（應移除）',
                'B_NEED_ZH': 'B. 譯文無中文句子（需補翻）',
                'B_SAME': 'B. 譯文=原文句子（漏翻）',
                'C_SAME': 'C. 名稱譯文無中文',
                'D_SPELL': 'D. 咒語/擬聲（保留英文）',
                'D_SPELL_PUNCT': 'D. 咒語被加中文標點（應還原）',
                'EMPTY': '空譯文',
            }
            for cat, items in res.items():
                rp.write(f"\n[{cat_names.get(cat, cat)}] {len(items)} 條\n")
                for k, v in items:
                    rp.write(f"  {k!r}  =>  {v!r}\n")
                    all_fix.append({'src': label, 'type': cat, 'en': k, 'zh': v})
                counts[(label, cat)] = len(items)

    json.dump(all_fix, open(args.fix, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"報告: {args.report}")
    print(f"待修正清單: {args.fix}（共 {len(all_fix)} 條）")
    for (label, cat), n in counts.items():
        if n:
            print(f"  {label} [{cat}] = {n}")

if __name__ == '__main__':
    main()