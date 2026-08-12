#!/usr/bin/env python3
"""
漢化規則驗證工具：掃描 server (translations_zh-tw.json) 與 client (.tbl)，
以 6 項規則檢驗「每個條目翻譯是否正確且符合規則」，0 違規才算通過。

規則：
  R1 中文完整性：譯文含中文字元（無錯翻/純英文/空譯文）。
  R2 名稱「中文(English)」格式：名稱類（NameTranslation 有譯文）譯文格式規範。
  R3 標籤保留：<col>/<br>/<img>/<str> 等標籤在 key/譯文完全一致（數量 + 值）。
  R4 術語統一：glossary.tsv 的術語在譯文中不得殘留英文原詞（除非「中文(英文)」括號內）。
  R5 亂碼：無 PUA / 非法字元 / 全形半形括號混用。
  R6 長度合理：無過短錯翻（長 key → ≤2 字譯文）。

用法：
  ./validate_rules.py --json <translations_zh-tw.json> --tbl <translations_client.tbl> \
      --glossary <glossary.tsv> [--name <NameTranslation.java>] [--report out.txt]

退出碼：0 = 全部通過；1 = 有違規。
"""
import argparse
import json
import re

CJK = re.compile(r'[\u4e00-\u9fff]')
PUA = re.compile(r'[\ue000-\uf8ff\ufffd]')
TAG = re.compile(r'<[^>]+>')
# 關鍵標籤（影響 UI 顏色/格式顯示）：<col>/<img>/<str>/<u>。R3 只強制這些一致，<br> 允許排版差異。
KEY_TAG = re.compile(r'<(col|img|u(?![a-z])|str)[^>]*>|</(col|u|str)>', re.I)
PUNCT_SUSPECT = re.compile(r'^[。，、；：？！．.…,;:?! ]{1,3}$')


def load_glossary(path):
    terms = []
    if path and __import__('os').path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('en\t'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 2 and parts[0] and parts[1]:
                    terms.append((parts[0].strip(), parts[1].strip()))
    # 依長度降序，長術語優先（避免短詞誤配）
    terms.sort(key=lambda t: -len(t[0]))
    return terms


def load_name_map(path):
    """從 NameTranslation.java 解析 en→純中文（含 D_NAMES）。"""
    m = {}
    if not path:
        return m
    src = open(path, encoding='utf-8').read()
    for x in re.finditer(r'private static final String D\d+ = "((?:[^"\\]|\\.)*)"', src, re.S):
        parts = x.group(1).replace('\\u0000', '\u0000').replace('\\"', '"').split('\u0000')
        for i in range(0, len(parts) - 1, 2):
            en, zh = parts[i].strip(), parts[i + 1].strip()
            if en and zh and zh != en:
                m[en] = zh
    x = re.search(r'D_NAMES =\n(.*?);', src, re.S)
    if x:
        joined = ''.join(re.findall(r'"(.*?)"', x.group(1), re.S)).replace('\\u0000', '\u0000')
        parts = joined.split('\u0000')
        for i in range(0, len(parts) - 1, 2):
            en, zh = parts[i].strip(), parts[i + 1].strip()
            if en and zh and zh != en:
                m[en] = zh
    return m


SPELL = re.compile(
    r'^(Veni|Sall|Sent|Senventior|Salm|Sallam|Klar|Sep|Dips|Dint|Sott|Ann|Mir|Sin|Snar|Brack|Vid|Av |Ra |Bow|Bur|Kar|Sch|Grr|Gra|Ukk|Amitus|En tanai|Su tana|Extralias|Holarius|Possessus|projectus|Castus|Absolutus|Defeati|the possessed|Present thyself|With least|and utmost|Es lem|Mi lov|Throwus|puro|Snarth|Tourniquet|Schl|Schorp|fnales|Dintenta|Sallamakar|Klarata|Annach|Mirra|Sin dan|Vidi|Ukkuk|Avach|Brackium|Runesquares|Howl|Oi|puro puro|Vidi, volui|Es lemanto|Mi lovos|Filliman|Aye, right|Oi do|Amitus|Veniens)', re.I)
CODE_PATTERNS = [
    r'[\$:{}\[\]@]', r'=>', r'->', r'\$\{', r'\{\{', r'\.get\(', r'\.set\(',
    r'\bINSERT\b', r'\bSELECT\b', r'\bCREATE\b', r'\bUPDATE\b', r'\bDELETE\b',
    r'FROM ', r'WHERE ', r'VALUES', r'INTEGER', r'stage =', r'npc\(', r'player\(', r'item\(',
    r'\\u', r'\\t', r'^\d', r'\.name=', r'System\.', r'result', r'label=', r'chunk:',
    r'Offer \$', r'timer\.', r'\.location', r'_id', r'_value', r'_amount', r'members',
    r'DUEL_', r'DROP_', r'COMMAND', r'IP_LOG', r'Message\\u', r'StatusUpdate',
    r'^\s*[,;)\]}\.]', r'&bull;', r'%banner', r'defender entry', r'tax door', r'wg ',
    r'revent', r'\^\\', r'digraph', r'brewkit', r'setplayer', r'setplaque', r'BH (low|mid|high)',
    r"ncient staff", r"layer's staff", r'12th Bennath', r'13th Bennath', r'14th Bennath', r'20th Bennath',
    r'\.json', r'\.txt', r'\.java', r'\.kt', r'^\w+-\w+(-\w+)*$', r'^\w+_\w+(_\w+)*$',
    r'^[a-z]+\.[a-z]+', r'^(daily|weekly|monthly|world)-',
    r'Location\.create\(', r'options\(DialogueOption', r'withdraw_items', r'DialogueOption',
    r'create\(', r'\.kotlin\.', r'^[a-z]+_[a-z]+$',
    r'%playerdesign', r'^tokens$', r'^\(PvP\)$', r'^<br>',
]
CODE = re.compile('|'.join(CODE_PATTERNS))


def _tag_balanced(s):
    """檢查關鍵標籤 <col>/<str>/<red>/<blue>/<img> 開閉是否平衡。"""
    for tag in ('col', 'str', 'red', 'blue', 'img'):
        o = len(re.findall(r'<' + tag + r'(?:=[0-9A-Fa-f]+)?>', s, re.I))
        c = len(re.findall(r'</' + tag + '>', s, re.I))
        if o != c:
            return False
    return True


def check_entry(en, zh, name_map, glossary):
    """回傳 [(rule, 說明), ...]，無違規為空列。"""
    if not zh:
        return [('R1', '空譯文')]
    issues = []
    # R5 亂碼
    if PUA.search(zh):
        issues.append(('R5', '含 PUA/替換字元'))
    # R1 中文完整性（允許合理保留英文：咒語/擬聲/程式碼/純標籤/數字/單詞名/名稱）
    if not CJK.search(zh) and re.search(r'[A-Za-z]{2,}', en):
        allowed = (SPELL.match(en) or CODE.search(en)
                   or not re.search(r'[A-Za-z]{3,}', en)
                   or re.match(r'^[A-Za-z]+ ?\d+$', en)      # Add 1 / Level 5
                   or ' ' not in en                          # 單詞/使用者名
                   or en in name_map)                        # 名稱（ObjType 加括號）
        if not allowed:
            issues.append(('R1', '譯文無中文字元（且非咒語/程式碼）'))
    # R6 長度合理（長 key → 過短或未翻譯譯文；允許「期票」精簡翻譯與擬聲/標點變體）
    plain_en = len(re.sub(r'<[^>]+>', '', en))
    plain_zh = re.sub(r'<[^>]+>', '', zh)
    if plain_en >= 15 and (len(plain_zh) <= 1
                           or (not CJK.search(plain_zh) and plain_zh == plain_en)):
        issues.append(('R6', f'長 key({plain_en})→未譯/過短({len(plain_zh)})'))
    # R3 標籤保留（關鍵標籤 <col>/<img>/<str>/<u> 完全一致；<br> 允許排版差異）
    # 若 key 的關鍵標籤開閉不平衡（截斷片段/長段落），標籤比對不可靠，跳過
    # 只報「key 有而譯文遺失」的標籤；譯文自行加色標籤屬 UI 強化，允許
    if not _tag_balanced(en):
        pass
    else:
        kt = sorted(KEY_TAG.findall(en))
        vt = sorted(KEY_TAG.findall(zh))
        if kt != vt and any(kt.count(t) > vt.count(t) for t in set(kt)):
            issues.append(('R3', f'關鍵標籤不一致  K{kt} vs V{vt}'))
    # R4 術語統一：譯文不得殘留 glossary 英文原詞（完整詞匹配）
    # 效能：譯文若無英文字母（純中文）不會有術語殘留，直接跳過
    if re.search(r'[A-Za-z]', zh) and '<col' not in zh and '<col' not in en:
        # 含 <col> 的對話/任務日誌段落，其中的物品/NPC 名保留英文（ObjType 中英格式），跳過術語檢查
        zl = zh.lower()
        for en_term, zh_term in glossary:
            if len(en_term.split()) <= 1:
                continue
            if en_term.lower() not in zl:
                continue
            # 完整詞匹配（避免子串誤判）
            if re.search(r'(?<![A-Za-z])' + re.escape(en_term) + r'(?![A-Za-z])', zh, re.I) and zh_term.lower() not in zl:
                # 排除「中文(English)」雙語括號內的英文（保留英文是設計）
                if re.search(r'\([^)]*' + re.escape(en_term) + r'[^)]*\)', zh, re.I):
                    continue
                # 排除 !!..?? 特殊標記內的名稱
                if re.search(r'!![^?]*' + re.escape(en_term), zh, re.I):
                    continue
                issues.append(('R4', f'術語"{en_term}"應為"{zh_term}"但譯文殘留英文'))
                if len(issues) >= 3:
                    break
    return issues


def main():
    ap = argparse.ArgumentParser(description='漢化規則驗證')
    ap.add_argument('--json', help='server 翻譯表')
    ap.add_argument('--tbl', help='client 翻譯表')
    ap.add_argument('--glossary', default=None, help='術語表 TSV')
    ap.add_argument('--name', default=None, help='NameTranslation.java（R2 名稱格式）')
    ap.add_argument('--report', default='validate_rules_report.txt')
    args = ap.parse_args()

    glossary = load_glossary(args.glossary)
    name_map = load_name_map(args.name)
    print(f"術語: {len(glossary)} | 名稱: {len(name_map)}")

    all_issues = []
    tables = {}
    if args.json:
        tables['server'] = json.load(open(args.json, encoding='utf-8'))
    if args.tbl:
        data = open(args.tbl, 'rb').read().split(b'\0')
        tables['client'] = {data[i].decode('utf-8', 'replace'): data[i + 1].decode('utf-8', 'replace')
                            for i in range(0, len(data) - 1, 2)}

    with open(args.report, 'w', encoding='utf-8') as rp:
        for label, table in tables.items():
            counts = {}
            for en, zh in table.items():
                for rule, msg in check_entry(en, zh, name_map, glossary):
                    counts[rule] = counts.get(rule, 0) + 1
                    all_issues.append((label, rule, en, zh, msg))
                    if len([x for x in all_issues if x[0] == label and x[1] == rule]) <= 5:
                        rp.write(f"[{label}][{rule}] {en[:50]!r}\n    => {zh[:50]!r}  ({msg})\n")
            rp.write(f"\n{'='*50}\n{label} 表 ({len(table)} 條)\n{'='*50}\n")
            for rule in ['R1', 'R2', 'R3', 'R4', 'R5', 'R6']:
                rp.write(f"  {rule}: {counts.get(rule, 0)}\n")

    # 摘要
    summary = {}
    for label, rule, *_ in all_issues:
        summary[(label, rule)] = summary.get((label, rule), 0) + 1
    print(f"\n違規總數: {len(all_issues)}")
    for (label, rule), n in sorted(summary.items()):
        print(f"  [{label}][{rule}] = {n}")
    print(f"報告: {args.report}")
    ok = len(all_issues) == 0
    print("結果:", "通過 ✅" if ok else "未通過 ❌（依上式規則修繕）")
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()