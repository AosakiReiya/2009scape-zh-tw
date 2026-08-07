#!/usr/bin/env python3
"""
動態拼接字串 → 模板萃取工具（v2）
掃描 server 原始碼中 sendMessage/sendDialogue/sendString/setInterfaceText 的
動態拼接呼叫，把 "前綴" + expr + "後綴" + ... 轉成含 {0}/{1} 佔位符的模板。

輸出：JSON 陣列 [{"en": "...", "zh-tw": "", "source": "...", "status": "untranslated"}]

範例：
  sendMessage(player, "You need a crafting level of " + data.getLevel() + " to craft " + an + " " + name + ".")
  → "You need a crafting level of {0} to craft {1} {2}."
"""
import argparse
import json
import os
import re

# 擷取 sendXxx(... 字串 ... + ...) 整段的內容（字串 + 變數 交替）
CALL_RE = re.compile(
    r'\b(sendMessage|sendDialogue|sendString|setInterfaceText|sendMessages)'
    r'\s*\(\s*[^,)]*?\s*,\s*((?:\s*"(?:[^"\\]|\\.)*"\s*\+\s*[^,)]*)+)',
    re.MULTILINE
)
# 拆分「字串」與「變數」
SEG_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([A-Za-z_][A-Za-z0-9_.()\[\]?:<> =!&|"\'\\$]*?)')

def parse_call(body):
    """把 '... "前綴" + var + "後綴" ...' 拆成 [('s', '前綴'), ('v', 'var'), ('s', '後綴')]"""
    segs = []
    pos = 0
    for m in SEG_RE.finditer(body):
        s = m.group(1)
        v = m.group(2)
        if s is not None:
            segs.append(("s", s))
        elif v is not None and v.strip():
            v = v.strip()
            # 過濾純符號/空白
            if re.fullmatch(r'[\+\s]+', v):
                continue
            if "(" not in v and ")" not in v and not re.search(r'[a-zA-Z]', v):
                continue
            segs.append(("v", v))
    return segs

def to_template(segs):
    """把片段組合成模板。字串部分保留，變數部分變 {0}{1}..."""
    if not segs:
        return None
    out = []
    var_idx = 0
    for kind, val in segs:
        if kind == "s":
            out.append(val)
        else:
            out.append("{" + str(var_idx) + "}")
            var_idx += 1
    return "".join(out)

def extract_from_file(path):
    results = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
    except OSError:
        return results
    rel = os.path.relpath(path)
    for m in CALL_RE.finditer(src):
        body = m.group(2)
        segs = parse_call(body)
        tpl = to_template(segs)
        if tpl and len(tpl) >= 5 and "{" in tpl:
            results.append({"en": tpl, "zh-tw": "", "source": rel, "status": "untranslated"})
    return results

def main():
    ap = argparse.ArgumentParser(description="動態拼接模板萃取")
    ap.add_argument("--server-src", required=True)
    ap.add_argument("--out", default="templates.json")
    args = ap.parse_args()

    all_results = []
    for root, dirs, files in os.walk(args.server_src):
        if "/build/" in root or "/target/" in root:
            continue
        for fn in files:
            if fn.endswith((".kt", ".java")):
                all_results.extend(extract_from_file(os.path.join(root, fn)))

    seen = set()
    deduped = []
    for r in all_results:
        if r["en"] not in seen:
            seen.add(r["en"])
            deduped.append(r)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)
    print(f"萃取完成: {len(deduped)} 條模板 -> {args.out}")

if __name__ == "__main__":
    main()
