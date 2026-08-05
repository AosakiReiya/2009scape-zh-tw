#!/usr/bin/env python3
"""
2009scape 任務內容字串萃取工具
解析 quest 檔的 sendString/line/sendDialogue 等表達式，代入 Quest 顏色常數、
還原「完整執行期字串」（含 <col> 標籤），供翻譯後加入伺服器翻譯表。

用法：
  ./extract_quest_strings.py --server-src <Server/src/main> --out quest_strings.json
"""
import argparse
import json
import os
import re

# Quest 類顏色常數（quest 檔通常 import core.game.node.entity.player.link.quest.Quest）
COLORS = {
    "RED": "<col=8A0808>",
    "BRIGHT_RED": "<col=FF0000>",
    "BLUE": "<col=08088A>",
    "BLACK": "<col=000000>",
    "GREEN": "<col=66ff33>",
    "ORANGE": "<col=ff6600>",
    "PURPLE": "<col=cc00ff>",
    "YELLOW": "<col=ffff00>",
    "WHITE": "<col=ffffff>",
}
# Globals.kt 顏色（部分檔案用）
GLOBALS_COLORS = {
    "RED": "<col=ff0000>",
    "ORANGE": "<col=ff6600>",
    "YELLOW": "<col=ffff00>",
    "GREEN": "<col=66ff33>",
    "BLUE": "<col=3366ff>",
    "PURPLE": "<col=cc00ff>",
}

# 呼叫模式：sendString(EXPR, ...) / line(player, EXPR, ...) / sendDialogue(EXPR) ...
CALL_RE = re.compile(r'\b(sendString|line|sendDialogue|sendDialogue2|sendPlainMessage|sendItemMessage|sendItemDialogue|sendDoubleItemDialogue)\(', re.S)


def extract_call_args(src, start):
    """從 src[start]（'(' 位置）依序取全部參數（平衡括號、字串、Color 常數）。"""
    args = []
    i = start
    assert src[i] == '('
    depth = 1
    in_str = False
    esc = False
    arg_start = start + 1
    while i < len(src):
        i += 1
        if i >= len(src):
            break
        c = src[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    args.append(src[arg_start:i])
                    break
            elif c == ',' and depth == 1:
                args.append(src[arg_start:i])
                arg_start = i + 1
    return args, i


def parse_expr(expr):
    """解析表達式：回傳 (parts, has_variable)。parts 為已解析的字串片段。"""
    parts = []
    has_var = False
    # 切分 +（不在字串內）
    tokens = []
    cur = []
    in_str = False
    esc = False
    for c in expr:
        if in_str:
            cur.append(c)
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
                cur.append(c)
            elif c == '+':
                tokens.append(''.join(cur))
                cur = []
            else:
                cur.append(c)
    tokens.append(''.join(cur))
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if tok in COLORS:
            parts.append(COLORS[tok])
        elif tok in GLOBALS_COLORS:
            parts.append(GLOBALS_COLORS[tok])
        elif tok.startswith('Quest.') and tok.split('.')[1] in COLORS:
            parts.append(COLORS[tok.split('.')[1]])
        elif (tok.startswith('"') and tok.endswith('"')) or (tok.startswith('"') and len(tok) > 1):
            # 字串字面值（可能含中文/特殊字元）
            inner = tok[1:]
            if inner.endswith('"'):
                inner = inner[:-1]
            inner = inner.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
            parts.append(inner)
        else:
            # 變數 / 方法呼叫 / ${...}
            has_var = True
            parts.append('{%s}' % tok[:20])
    return parts, has_var


def resolve_quest_expr(expr, is_line):
    """還原 sendString/line 的完整執行期字串。含變數回傳 None。"""
    parts, has_var = parse_expr(expr)
    if has_var:
        return None
    s = ''.join(parts)
    if is_line:
        # line() helper：前置 BLUE + 替換
        s = '<col=08088A>' + s.replace('<n>', '<br><br>').replace('<blue>', '<col=08088A>').replace('<red>', '<col=8A0808>')
        s = s.replace('!!', '<col=8A0808>').replace('??', '<col=08088A>').replace('%%', '<col=FF0000>').replace('&&', '<col=08088A>')
    return s


def looks_sentence(s):
    """像句子的字串（剝標籤後含空格 + 字母）。"""
    if '$' in s or '{' in s or '}' in s:
        return False  # 含變數（Kotlin 模板 / 佔位符）
    plain = re.sub(r'<[^>]+>', '', s)
    if not re.search(r'[a-z]', plain):
        return False
    if not re.search(r'[a-z] [a-z]', plain):
        return False
    if len(plain) < 12:
        return False
    return True


def extract_file(path):
    results = []
    try:
        src = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return results
    rel = os.path.relpath(path)
    for m in CALL_RE.finditer(src):
        fn = m.group(1)
        args, end = extract_call_args(src, m.end() - 1)
        # line(player, EXPR, ...) 第 1 參數是 player；sendString(EXPR, ...) 第 1 參數是字串
        expr = args[1] if fn == 'line' and len(args) > 1 else (args[0] if args else '')
        is_line = fn == 'line'
        resolved = resolve_quest_expr(expr, is_line)
        if resolved and looks_sentence(resolved):
            results.append({"en": resolved, "zh-tw": "", "source": rel,
                            "status": "untranslated", "method": fn})
    return results


def main():
    ap = argparse.ArgumentParser(description="2009scape 任務內容字串萃取")
    ap.add_argument("--server-src", required=True)
    ap.add_argument("--out", default="quest_strings.json")
    args = ap.parse_args()

    all_results = []
    seen = set()
    for root, dirs, files in os.walk(args.server_src):
        if '/build/' in root or '/target/' in root:
            continue
        for fn in files:
            if fn.endswith(('.kt', '.java')) and not fn.endswith('Test.kt'):
                path = os.path.join(root, fn)
                for r in extract_file(path):
                    if r['en'] not in seen:
                        seen.add(r['en'])
                        all_results.append(r)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"萃取完成: {len(all_results)} 條 -> {args.out}")


if __name__ == "__main__":
    main()