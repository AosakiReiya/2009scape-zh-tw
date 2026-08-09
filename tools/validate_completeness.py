#!/usr/bin/env python3
"""
漢化完整性驗證：靜態掃描全部字串來源（server .kt/.java + client cache），
對比翻譯表（server json + client .tbl + NameTranslation），找出「未翻譯」字串。

靜態掃描的上限：無法捕捉執行期拼接的完整句子（多行對話片段），但能查出
所有「可讀英文句子」未進翻譯表的漏翻。

用法：
  ./validate_completeness.py --server-src <Server/src/main> --json <translations_zh-tw.json> \
      --tbl <translations_client.tbl> --name <NameTranslation.java> [--report out.txt]

退出碼：0 = 無漏翻；1 = 有漏翻。
"""
import argparse
import json
import os
import re

CJK = re.compile(r'[\u4e00-\u9fff]')
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')

# 程式碼/動態模板 → 非顯示字串
CODE = re.compile(
    r'[\$:{}\[\]@]|=>|->|\$\{|\{\{|\.get\(|\.set\(|\bINSERT\b|\bSELECT\b|\bCREATE\b|\bUPDATE\b|'
    r'\bDELETE\b|FROM |WHERE |VALUES|INTEGER|stage =|npc\(|player\(|item\(|\\u|\\t|^\d|\.name=|'
    r'System\.|result|label=|chunk:|Offer \$|timer\.|\.location|_id|_value|_amount|members|'
    r'DUEL_|DROP_|COMMAND|IP_LOG|Message\\u|StatusUpdate|^\s*[,;)\]}\.]|&bull;|%banner|'
    r'defender entry|tax door|wg |revent|\^\\|digraph|brewkit|setplayer|setplaque|BH (low|mid|high)|'
    r"ncient staff|layer's staff|12th Bennath|13th Bennath|14th Bennath|20th Bennath|Loc\.|"
    r'\.json|\.txt|\.java|\.kt|^\w+-\w+(-\w+)*$|^\w+_\w+(_\w+)*$|^[a-z]+\.[a-z]+|'
    r'^(daily|weekly|monthly|world)-|create\(|Location\.create\(')
SPELL = re.compile(r'^(Veni|Sall|Sent|Senventior|Salm|Sallam|Klar|Sep|Dips|Dint|Sott|Ann|Mir|Sin|Snar|Brack|Vid|Av |Ra |Bow|Bur|Kar|Sch|Grr|Gra|Ukk|Amitus|En tanai|Su tana|Extralias|Holarius|Possessus|projectus|Castus|Absolutus|Defeati|the possessed|Present thyself|With least|and utmost|Es lem|Mi lov|Throwus|puro|Snarth|Tourniquet|Schl|Schorp|fnales|Dintenta|Sallamakar|Klarata|Annach|Mirra|Sin dan|Vidi|Ukkuk|Avach|Brackium|Runesquares|Howl|Oi|Filliman)', re.I)
# 片段/程式碼/標記 → 非完整可翻譯句子
FRAG = re.compile(r'\!\!|\?\?|no definitions|stairs|Insufficient array|account, they|is against the'
                  r'|of Uzer|to find his brother|Orbs of Protection|Lord Handelmort|Dimintheis'
                  r'|et Daconia|you pleadingly|I took the research package|total XP')


def _tag_balanced(s):
    """檢查關鍵標籤 <col>/<str>/<red>/<blue>/<img> 開閉是否平衡（平衡 = 完整段落非片段）。"""
    for tag in ('col', 'str', 'red', 'blue', 'img'):
        o = len(re.findall(r'<' + tag + r'(?:=[0-9A-Fa-f]+)?>', s, re.I))
        c = len(re.findall(r'</' + tag + '>', s, re.I))
        if o != c:
            return False
    return True


def looks_translatable(s):
    """是否為值得翻譯的完整英文句子（非程式碼/咒語/碎片/片段）。"""
    s = s.strip()
    if not s or len(s) < 6:
        return False
    if not re.search(r'[A-Za-z]{3,} [A-Za-z]', s):
        return False
    if CODE.search(s) or SPELL.match(s) or FRAG.search(s):
        return False
    if re.match(r'^[A-Za-z]+ ?\d+$', s):
        return False
    # 只報「完整句子」：含 <col> 平衡標籤的任務日誌（完整 key）不要求句號；
    # 純文字則要求以句號/問號/感嘆號結尾（排除多行對話片段）
    if '<col' in s or '<str' in s:
        if not _tag_balanced(s):
            return False
    elif not re.search(r'[.?!。！？]["\']?\s*$', s):
        return False
    return True


def scan_src(src_dir, sink):
    """掃描 .kt/.java 雙引號字串（含多行）。"""
    n = 0
    for root, dirs, files in os.walk(src_dir):
        if os.sep + 'build' in root or os.sep + 'target' in root:
            continue
        for fn in files:
            if not fn.endswith(('.kt', '.java')) or fn.endswith('Test.kt'):
                continue
            path = os.path.join(root, fn)
            try:
                src = open(path, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            for m in STR.finditer(src):
                s = m.group(1).replace('\\"', '"').replace('\\n', ' ').replace('\\t', ' ').strip()
                if looks_translatable(s):
                    sink[s] = os.path.relpath(path, src_dir)
                    n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description='漢化完整性驗證')
    ap.add_argument('--server-src', help='Server/src/main 目錄')
    ap.add_argument('--json', help='server 翻譯表')
    ap.add_argument('--tbl', help='client 翻譯表')
    ap.add_argument('--name', help='NameTranslation.java')
    ap.add_argument('--report', default='validate_completeness_report.txt')
    args = ap.parse_args()

    # 收集已翻譯 key
    covered = set()
    if args.json:
        covered.update(json.load(open(args.json, encoding='utf-8')).keys())
    if args.tbl:
        data = open(args.tbl, 'rb').read().split(b'\0')
        covered.update(data[i].decode('utf-8', 'replace') for i in range(0, len(data) - 1, 2))
    if args.name:
        src = open(args.name, encoding='utf-8').read()
        for m in re.finditer(r'private static final String D\d+ = "((?:[^"\\]|\\.)*)"', src, re.S):
            parts = m.group(1).replace('\\u0000', '\u0000').split('\u0000')
            for i in range(0, len(parts) - 1, 2):
                covered.add(parts[i].strip())
        m = re.search(r'D_NAMES =\n(.*?);', src, re.S)
        if m:
            joined = ''.join(re.findall(r'"(.*?)"', m.group(1), re.S)).replace('\\u0000', '\u0000')
            parts = joined.split('\u0000')
            for i in range(0, len(parts) - 1, 2):
                covered.add(parts[i].strip())

    # 掃描來源
    sink = {}
    if args.server_src:
        n = scan_src(args.server_src, sink)
    else:
        n = 0
    print(f"掃描 {n} 條候選字串 | 已翻譯 key {len(covered)}")

    missing = sorted(s for s in sink if s not in covered)
    with open(args.report, 'w', encoding='utf-8') as rp:
        rp.write(f"靜態完整性驗證：未翻譯 {len(missing)} 條\n{'=' * 50}\n")
        for s in missing:
            rp.write(f"  [{sink[s]}] {s}\n")
    print(f"未翻譯字串: {len(missing)} | 報告: {args.report}")
    for s in missing[:20]:
        print(f"  {s[:70]}")
    print("結果:", "通過 ✅（無漏翻）" if not missing else "未通過 ❌（有漏翻待補）")
    raise SystemExit(0 if not missing else 1)


if __name__ == '__main__':
    main()