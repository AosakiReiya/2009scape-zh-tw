#!/usr/bin/env python3
"""
從翻譯表（translate_batch.py 輸出）生成客戶端 CacheTranslationExt.java。
把 key\\0value 對打包成多個 Java string 常數（每個 < 65535 bytes 常數池限制），
並提供 translate() / translateIgnoreCase() 查詢 helper。

用法：
  ./gen_cache_ext.py --table cache_strings.json --out CacheTranslationExt.java
"""
import argparse
import json
import re
import os

# 每個常數最多條目數（每條約 30-40 bytes，65535 上限取安全值）
CHUNK = 1000


def java_escape(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '\n':
            out.append('\\n')
        elif o < 32 or o == 127:
            out.append('\\u%04x' % o)
        else:
            out.append(ch)
    return ''.join(out)


def main():
    ap = argparse.ArgumentParser(description="生成 CacheTranslationExt.java")
    ap.add_argument("--table", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name-translation", default=None,
                    help="NameTranslation.java 路徑：排除已在其中的 key（由 NameTranslation fallback 提供一致翻譯）")
    args = ap.parse_args()

    table = json.load(open(args.table, encoding='utf-8'))
    # 排除已在 NameTranslation 的 key（物品/NPC/Loc 名由 NameTranslation 提供，避免 LLM 的不一致譯名覆蓋）
    nt_keys = set()
    if args.name_translation and os.path.exists(args.name_translation):
        nt = open(args.name_translation, encoding='utf-8').read()
        for m in re.finditer(r'static final String D\w*\s*=\s*"((?:[^"\\]|\\.)*)"', nt, re.S):
            data = m.group(1).replace('\\u0000', '\u0000')
            parts = data.split('\u0000')
            for i in range(0, len(parts) - 1, 2):
                nt_keys.add(parts[i])
    entries = [(e["en"], e["zh-tw"]) for e in table if e.get("zh-tw") and e["zh-tw"] != e["en"] and e["en"] not in nt_keys]
    seen = set()
    uniq = []
    for en, zh in entries:
        if en in seen:
            continue
        seen.add(en)
        uniq.append((en, zh))
    print(f"有效翻譯: {len(uniq)}（排除 NameTranslation 既有 {len(entries) - len(uniq)} 條）")

    # 切成多個 chunk
    chunks = [uniq[i:i + CHUNK] for i in range(0, len(uniq), CHUNK)]
    lines = []
    lines.append("package rt4;")
    lines.append("")
    lines.append("/**")
    lines.append(" * 自動產生的額外翻譯表（來源：介面 archive 3 + CS2 archive 12 字串）。")
    lines.append(" * 由 tools/gen_cache_ext.py 產生，勿手動編輯。")
    lines.append(" */")
    lines.append("public final class CacheTranslationExt {")
    lines.append("")
    for i, chunk in enumerate(chunks, 1):
        # 每個 chunk 切成多個單行 string literal（Java 字串不能含換行），用 + 串接
        # 只在完整條目（含 \u0000 結尾）邊界分行，避免切斷 \uXXXX escape
        lines.append(f"\tprivate static final String D{i} =")
        parts = []
        cur = ""
        for en, zh in chunk:
            entry = java_escape(en) + "\\u0000" + java_escape(zh) + "\\u0000"
            if len(cur) + len(entry) > 100 and cur:
                parts.append(cur)
                cur = entry
            else:
                cur += entry
        if cur:
            parts.append(cur)
        # 對齊 + 與引號（最後一行以 ; 結尾）
        for k, part in enumerate(parts):
            if k == 0:
                lines.append("\t\t\"" + part + "\"")
            elif k == len(parts) - 1:
                lines.append("\t\t+ \"" + part + "\";")
            else:
                lines.append("\t\t+ \"" + part + "\"")
        lines.append("")
    lines.append("\tprivate static final String[] DATAS = {" + ", ".join(f"D{i}" for i in range(1, len(chunks) + 1)) + "};")
    lines.append("")
    lines.append("\t/** 精確查詢；未命中回傳 null。 */")
    lines.append("\tpublic static String translate(String s) {")
    lines.append("\t\tString needle = \"\\u0000\" + s + \"\\u0000\";")
    lines.append("\t\tfor (String d : DATAS) {")
    lines.append("\t\t\tint idx = d.indexOf(needle);")
    lines.append("\t\t\tif (idx < 0) continue;")
    lines.append("\t\t\tint start = idx + needle.length();")
    lines.append("\t\t\tint end = d.indexOf(\"\\u0000\", start);")
    lines.append("\t\t\tif (end < 0) end = d.length();")
    lines.append("\t\t\treturn d.substring(start, end);")
    lines.append("\t\t}")
    lines.append("\t\treturn null;")
    lines.append("\t}")
    lines.append("")
    lines.append("\t/** 大小寫不敏感查詢；未命中回傳 null。 */")
    lines.append("\tpublic static String translateIgnoreCase(String s) {")
    lines.append("\t\tString lowerNeedle = \"\\u0000\" + s.toLowerCase() + \"\\u0000\";")
    lines.append("\t\tfor (String d : DATAS) {")
    lines.append("\t\t\tint idx = d.toLowerCase().indexOf(lowerNeedle);")
    lines.append("\t\t\tif (idx < 0) continue;")
    lines.append("\t\t\tint start = idx + lowerNeedle.length();")
    lines.append("\t\t\tint end = d.indexOf(\"\\u0000\", start);")
    lines.append("\t\t\tif (end < 0) end = d.length();")
    lines.append("\t\t\treturn d.substring(start, end);")
    lines.append("\t\t}")
    lines.append("\t\treturn null;")
    lines.append("\t}")
    lines.append("}")
    lines.append("")

    with open(args.out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"已寫入 {args.out}（{len(chunks)} chunks）")


if __name__ == "__main__":
    main()