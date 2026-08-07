#!/usr/bin/env python3
"""
2009scape 漏翻譯偵測工具。

整合兩種來源找出「遊戲顯示但未翻譯」的英文字串：
  1. 執行期記錄（最準）：server Translation.logMissing 寫出的 missing_translations.log，
     以及 client 的 missing_translations_client.log。
  2. 靜態掃描（免跑遊戲）：掃描 Server/src/main 的 .kt/.java 英文字串字面量。

並做：
  - 例外過濾（人名/專有名詞/數字/佔位符/符號/短串等合理保留項）。
  - 對比翻譯表（server translations_zh-tw.json + client translations_client.tbl）。
  - 「中文(英文)」雙語格式視為正常（譯文含中文字元即跳過）。
  - 輸出 translate_batch.py 相容的待翻譯 JSON。

用法：
  ./find_missing_translations.py \
      --server-log data/logs/missing_translations.log \
      --client-log missing_translations_client.log \
      --server-src <Server/src/main> \
      --json data/configs/translations_zh-tw.json \
      --tbl translations_client.tbl \
      --glossary translations/glossary.tsv \
      --allowlist tools/missing_allowlist.txt \
      --out missing_translations_out.json

輸出：
  missing_translations_out.json  [{en, zh-tw:"", source, status:"untranslated"}, ...]
  missing_translations_report.txt 分類報告（含「已進表但譯文無中文」）。
"""
import argparse
import json
import os
import re

CJK = re.compile(r'[\u4e00-\u9fff]')
LETTER = re.compile(r'[A-Za-z]')
TAG = re.compile(r'<[^>]+>')
PLACEHOLDER = re.compile(r'%[0-9d%]|%s|\$[A-Za-z_]+|\{\{\w+\}\}|\$\{')
GOLD = re.compile(r'^[\d,]+ ?(gp|coins?|gold|k|m)?$', re.I)
SYMBOLS = re.compile(r'^[^A-Za-z]{3,}$')
SAVE_KEY = re.compile(r'^(/save:|save:|config:|jobs:|daily-|weekly-|[\w-]+:[a-z]|[\w-]+:[\w-]+:[a-z])', re.I)
SHORT_KEY = re.compile(r'^[a-z0-9_\-]{1,3}$')
CODE_KEY = re.compile(r'^[a-z][a-z0-9_]*(:[a-z0-9_]+)+$')


def norm(s):
    """剝標籤 + 壓縮空白。"""
    return re.sub(r'\s+', ' ', TAG.sub('', s)).strip()


def has_cjk(s):
    return bool(CJK.search(s))


def looks_sentence(s):
    """是否為值得翻譯的英文句子（含字母、有空格、夠長）。"""
    if not s:
        return False
    if not LETTER.search(s):
        return False
    if ' ' not in s:
        return False
    letters = sum(1 for c in s if c.isalpha())
    if letters < 3:
        return False
    if len(s) < 5:
        return False
    return True


def is_exception(s, allowlist):
    """合理保留項（不列為漏翻）。回傳 True 表示例外。"""
    if s in allowlist:
        return True
    t = s.strip()
    if not t:
        return True
    if has_cjk(t):
        return True
    if not LETTER.search(t):
        return True
    if PLACEHOLDER.search(t):
        return True           # 含 %1 / $xxx / ${} 佔位 → 動態模板，跳過
    if GOLD.match(t):
        return True           # 純數字/金幣
    if SYMBOLS.match(t):
        return True           # 純符號（*** 等）
    stripped = TAG.sub('', t)
    if len(stripped) < 3:
        return True
    if not looks_sentence(t):
        return True           # 無空格/過短 → 名稱或單字
    if SAVE_KEY.match(t) or CODE_KEY.match(t) or SHORT_KEY.match(t):
        return True           # 程式 key / save key
    # 全是小寫 + 連字/冒號 → 內部識別字，非文句
    return False


def load_glossary_en_set(path):
    """glossary.tsv 的 en key 集合（已承認術語，作為 allowlist 基底）。"""
    out = set()
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('en\t'):
                continue
            parts = line.split('\t')
            if parts and parts[0]:
                out.add(parts[0].strip())
    return out


def load_allowlist(path):
    out = set()
    if path and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    out.add(line)
    return out


def load_log(path, sink, src_label):
    if not path or not os.path.exists(path):
        return 0
    n = 0
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n').strip()
            if line and line not in sink:
                sink[line] = src_label
                n += 1
    return n


def scan_src(src_dir, sink, src_label):
    """靜態掃描 .kt/.java 的雙引號英文字串字面量（保守過濾，寧缺勿錯）。"""
    STR = re.compile(r'"((?:[^"\\]|\\.)*)"')
    # 程式碼/多行/SQL 特徵 → 非 UI 字串
    CODE_FEATURE = re.compile(
        r'[\n\r;=<>?(){}`]|->|=>|\b(CREATE|SELECT|INSERT|UPDATE|DELETE|DROP|FROM|WHERE|VALUES|TABLE|PRIMARY|FOREIGN|INTO|ON|JOIN|SET|AND|OR|IF|THEN|ELSE|END|BEGIN|DECLARE)\b'
        r'|" \+ |\.get\(|\.set\(|\.add\(|println\(|log\(')
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
            rel = os.path.relpath(path, src_dir)
            for m in STR.finditer(src):
                s = m.group(1).replace('\\"', '"').replace('\\n', '\n')
                if not looks_sentence(s):
                    continue
                if CODE_FEATURE.search(s):
                    continue
                if '${' in s or re.search(r'\b(function|fun|val|var|import|package|class|return|if|else|when|throw|override|args|player|world|script|helper)\b', s):
                    continue
                if s not in sink:
                    sink[s] = f"{rel}:{src_label}"
                    n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description='漏翻譯偵測')
    ap.add_argument('--server-log')
    ap.add_argument('--client-log')
    ap.add_argument('--server-src')
    ap.add_argument('--json', help='server 翻譯表 translations_zh-tw.json')
    ap.add_argument('--tbl', help='client 翻譯表 translations_client.tbl')
    ap.add_argument('--glossary')
    ap.add_argument('--allowlist')
    ap.add_argument('--out', default='missing_translations_out.json')
    ap.add_argument('--report', default='missing_translations_report.txt')
    args = ap.parse_args()

    # 1) 載入翻譯表
    server_map = {}
    if args.json and os.path.exists(args.json):
        server_map = json.load(open(args.json, encoding='utf-8'))
    client_map = {}
    if args.tbl and os.path.exists(args.tbl):
        data = open(args.tbl, 'rb').read().split(b'\0')
        client_map = {data[i].decode('utf-8', 'replace'): data[i + 1].decode('utf-8', 'replace')
                      for i in range(0, len(data) - 1, 2)}
    S = dict(server_map); S.update(client_map)  # 合併(en→譯文)

    # 2) allowlist（術語表基底 + 手動）
    allow = load_glossary_en_set(args.glossary)
    allow |= load_allowlist(args.allowlist)

    # 3) 收集候選
    sink = {}
    n_server_log = load_log(args.server_log, sink, 'server-log')
    n_client_log = load_log(args.client_log, sink, 'client-log')
    n_scan = scan_src(args.server_src, sink, 'scan') if args.server_src else 0
    print(f"執行期 log: server={n_server_log} client={n_client_log} | 靜態掃描: {n_scan} | 候選總數: {len(sink)}")

    # 4) 過濾 + 分類
    missing = []      # 未進表，待翻譯
    translated_bad = []  # 已進表但譯文無中文
    skipped = 0
    for s, src in sink.items():
        if not looks_sentence(s):
            skipped += 1
            continue
        if is_exception(s, allow):
            skipped += 1
            continue
        if s in S:
            zh = S[s]
            if has_cjk(zh):
                skipped += 1      # 已翻譯（含「中文(英文)」）
                continue
            translated_bad.append({"en": s, "zh-tw": zh, "source": src, "status": "translated-no-cjk"})
        else:
            missing.append({"en": s, "zh-tw": "", "source": src, "status": "untranslated"})

    missing.sort(key=lambda e: e['en'])
    translated_bad.sort(key=lambda e: e['en'])

    # 5) 輸出待翻譯 JSON
    out = [{"en": e["en"], "zh-tw": "", "source": e["source"], "status": "untranslated"} for e in missing]
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 6) 報告
    with open(args.report, 'w', encoding='utf-8') as f:
        f.write(f"漏翻譯偵測報告\n{'=' * 50}\n")
        f.write(f"候選總數: {len(sink)}\n例外/已翻譯略過: {skipped}\n")
        f.write(f"\n[A] 未進表漏翻 ({len(missing)} 條) -> {args.out}\n")
        for e in missing:
            f.write(f"  [{e['source']}] {e['en']}\n")
        f.write(f"\n[B] 已進表但譯文無中文 ({len(translated_bad)} 條，需人工判斷是否補翻)\n")
        for e in translated_bad:
            f.write(f"  [{e['source']}] {e['en']}  =>  {e['zh-tw']}\n")

    print(f"未進表漏翻: {len(missing)}  -> {args.out}")
    print(f"已進表但譯文無中文: {len(translated_bad)}  -> 報告 {args.report}")


if __name__ == '__main__':
    main()