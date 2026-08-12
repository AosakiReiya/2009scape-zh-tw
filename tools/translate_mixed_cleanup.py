#!/usr/bin/env python3
"""
中英夾雜譯文清理工具（場景：既有表值重翻）

掃描翻譯表中「中文與英文夾雜」的劣質譯文（如「Pollnivneach 的 Sumona。」、
「處理 Scabaras 的事」），用本地 LLM 重翻成自然台灣正體中文。
規則：重要人名/地名輸出「中文 (English)」雙語；不允許括號外的中英夾雜。
品質閘：輸出仍含括號外英文（除 ${佔位符}/<col> 標籤/數字/H.A.M 等允許詞）→ 拒收。

用法：
  ./translate_mixed_cleanup.py --table <translations_zh-tw.json> \
      [--glossary translations/glossary.tsv] [--limit 500] [--min-freq 3]
環境變數：LLM_API_URL（預設 http://localhost:1234/v1/chat/completions）、
          LLM_MODEL（預設 gemma-4-26b-a4b-it）、BATCH（預設 15）
"""

import argparse
import json
import os
import re
import sys
import time

import requests

API_URL = os.environ.get("LLM_API_URL", "http://localhost:1234/v1/chat/completions")
MODEL = os.environ.get("LLM_MODEL", "gemma-4-26b-a4b-it")
BATCH = int(os.environ.get("BATCH", "15"))
TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "240"))

CJK = re.compile(r'[\u4e00-\u9fff]')
LAT = re.compile(r'[A-Za-z]{2,}')
# 允許保留在括號外的英文（佔位符/品牌/縮寫/材質）
ALLOWED = re.compile(
    r'\$(?:[A-Za-z_]+|\{[^}]*\})'          # $var / ${...}
    r'|<[^>]+>'                            # <col=...> 等標籤
    r'|H\.A\.M\.?|NPC|XP|GP|ID|PIN|GE|Team-\d|Scape2009|RuneScape|Jagex'
    r'|@\w+(\[[^\]]*\])?'                  # @name / @g[sirrah,milady]
    r'|%[A-Z]+'                            # %B / %GC 著色碼
    r'|!![^?]*\?\?'                        # !!Fenkenstrain?? 標記
)
DIGIT = re.compile(r'\d')


def load_glossary(path):
    gl = {}
    if path and os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 2 and p[0] and p[1] and p[0].lower() != 'en':
                gl[p[0]] = p[1]
    return gl


def is_mixed(v):
    """判斷譯文是否為劣質中英夾雜（括號外有英文詞）。"""
    if not CJK.search(v):
        return False
    if v.startswith('@pre:'):
        return False
    stripped = re.sub(r'\([^()]*\)|（[^()]*）', '', v)
    rest = ALLOWED.sub('', stripped)
    # 去掉純拉丁詞（如 "Slayer points" 中的數字）
    return bool(LAT.search(rest))


def relevant_terms(texts, glossary, max_terms=60):
    blob = ' '.join(texts).lower()
    rel = {}
    for en, zh in sorted(glossary.items(), key=lambda kv: -len(kv[0])):
        if en.lower() in blob:
            rel[en] = zh
            if len(rel) >= max_terms:
                break
    return rel


def build_prompt(texts, glossary, rel):
    gloss = '\n'.join(f'{en} translates to {zh}' for en, zh in rel.items())
    block = f'\nReference translations (use these EXACT terms when they appear):\n{gloss}\n' if gloss else ''
    formatted = '\n'.join(f'{i+1}. {t}' for i, t in enumerate(texts))
    return (
        f'你是 RuneScape 2009 遊戲的台灣正體中文翻譯。\n'
        f'以下是既有譯文，其中夾雜英文，請改寫為自然流暢的台灣正體中文。{block}\n'
        f'規則：\n'
        f'- 人名、地名、重要名詞輸出為「中文 (English)」（中文在前，英文半形括號在後）。\n'
        f'- 除上述括號中的英文外，譯文中不得再出現英文單詞（材質名如精鋼/祕銀/符文必須翻成中文）。\n'
        f'- 保留所有標記（<col=...>、<br>、${"$"}${"$"}變數、!!著色??、@名稱）原樣。\n'
        f'- 只輸出編號翻譯，一行一條。\n'
        f'{formatted}'
    )


def call_llm(texts, glossary):
    rel = relevant_terms(texts, glossary)
    prompt = build_prompt(texts, glossary, rel)
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': 'You are a professional game translator for RuneScape 2009, translating into Traditional Chinese (Taiwan).'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.2,
    }
    resp = requests.post(API_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    content = resp.json()['choices'][0]['message']['content']
    out = {}
    for line in content.splitlines():
        line = line.strip()
        m = re.match(r'^(\d+)[\.\)]?\s*(.+)$', line)
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def quality_gate(old, new):
    """拒收仍含括號外英文或空白的譯文。"""
    if not new or not CJK.search(new):
        return False
    if is_mixed(new):
        return False
    if new == old:
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table', required=True)
    ap.add_argument('--glossary')
    ap.add_argument('--limit', type=int, default=0, help='本次最多處理條數（0=全部）')
    ap.add_argument('--min-freq', type=int, default=3, help='僅處理出現次數≥此值的待清理 key（需 --freq-map）')
    ap.add_argument('--out', help='輸出路徑（預設覆寫原表）')
    args = ap.parse_args()

    table = json.load(open(args.table, encoding='utf-8'))
    gl = load_glossary(args.glossary)
    mixed = [(k, v) for k, v in table.items() if is_mixed(v)]
    print(f'待清理中英夾雜: {len(mixed)} / {len(table)}')

    # 出現頻率（key 在對話中重複出現的相似度無從得知；改用 key 長度排序，短 key 優先）
    mixed.sort(key=lambda kv: len(kv[0]))

    target = mixed[:args.limit] if args.limit else mixed
    done = 0
    fixed = 0
    for i in range(0, len(target), BATCH):
        chunk = target[i:i + BATCH]
        keys = [k for k, _ in chunk]
        try:
            got = call_llm([v for _, v in chunk], gl)
        except Exception as e:
            print(f'  batch {i//BATCH} 失敗: {e}')
            time.sleep(3)
            continue
        for j, (k, old) in enumerate(chunk, 1):
            if j in got and quality_gate(old, got[j]):
                table[k] = got[j]
                fixed += 1
                print(f'  FIX {k[:50]!r} => {got[j][:55]!r}')
            else:
                print(f'  KEEP {k[:50]!r}（拒收/未變）')
        done += len(chunk)
        if done % 60 == 0:
            print(f'... 進度 {done}/{len(target)} 已修 {fixed}')
            json.dump(table, open(args.out or args.table, 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
    json.dump(table, open(args.out or args.table, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f'完成：處理 {done} 條，修正 {fixed} 條')


if __name__ == '__main__':
    main()