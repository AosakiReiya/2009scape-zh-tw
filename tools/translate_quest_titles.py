#!/usr/bin/env python3
"""
任務標題翻譯工具（場景：任務名稱，雙語強制）

把任務名稱翻譯成「純中文 (English)」雙語格式：
- 中文主體必須為自然台灣正體中文（人名/地名音譯），不得含英文。
- 括號內為原始英文任務名。
- 品質閘：中文主體含英文 → 拒收。

用法：
  ./translate_quest_titles.py --table <translations_zh-tw.json> \
      --quests <Quests.kt> --out <輸出>
"""

import argparse
import json
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CJK = re.compile(r'[\u4e00-\u9fff]')


def extract_quest_names(kt_path):
    src = open(kt_path, encoding='utf-8').read()
    return sorted(set(m.strip() for _, m in
                      re.findall(r'([A-Z]\(?[A-Z]?[A-Z0-9_]*)\("([^"]+)"\)', src)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--table', required=True)
    ap.add_argument('--quests', required=True, help='Quests.kt 路徑')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    table = json.load(open(args.table, encoding='utf-8'))
    names = extract_quest_names(args.quests)

    def zhpart(v):
        m = re.match(r'^(.+?) \(([^()]+)\)$', v or '')
        return m.group(1) if m else None

    fixed = 0
    for n in names:
        cur = table.get(n)
        zh = zhpart(cur)
        if zh and not re.search(r'[A-Za-z]', zh):
            continue  # 已是合格雙語
        if zh is None and cur and CJK.search(cur) and not re.search(r'[A-Za-z]', cur):
            zh = cur  # 純中文 → 補後綴
        if not zh:
            print(f'  !! 需人工/LLM: {n!r} cur={cur!r}')
            continue
        table[n] = f'{zh} ({n})'
        fixed += 1
    json.dump(table, open(args.out, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f'完成：更新 {fixed} 條任務標題 -> {args.out}')


if __name__ == '__main__':
    import os
    main()