#!/usr/bin/env python3
"""
2009scape 客戶端 cache 字串萃取工具
從 main_file_cache（530 格式）提取介面（archive 3）與 CS2 腳本（archive 12）字串，
扣除已存在於 CacheTranslation.java 與伺服器翻譯表的 key，輸出翻譯表骨架。

用法：
  ./dump_cache_strings.py --cache <cache_dir> --client-src <CacheTranslation.java> \
     --server-table <translations_zh-tw.json> --out <table.json>

輸出格式（translate_batch.py 相容）：
  [{"en": "...", "zh-tw": "", "source": "iface", "status": "untranslated"}, ...]
"""

import argparse
import bz2
import gzip
import json
import os
import re


def read_container(idx_data, dat_file, file_id):
    """讀取一個 container（530 格式：520-byte sector，8-byte header + 512 data）。"""
    e = idx_data[file_id * 6:file_id * 6 + 6]
    if len(e) < 6:
        return None
    length = int.from_bytes(e[0:3], 'big')
    sector = int.from_bytes(e[3:6], 'big')
    if length == 0 or sector == 0:
        return None
    out = bytearray()
    part = 0
    while len(out) < length:
        dat_file.seek(520 * sector)
        hdr = dat_file.read(8)
        if len(hdr) < 8:
            break
        cpart = int.from_bytes(hdr[2:4], 'big')
        next_sector = int.from_bytes(hdr[4:7], 'big')
        chunk = dat_file.read(512)
        out += chunk[:min(512, length - len(out))]
        if cpart != part:
            break
        if len(out) >= length:
            break
        part += 1
        sector = next_sector
        if sector == 0:
            break
    return bytes(out)


def uncompress(raw):
    typ = raw[0]
    ln = int.from_bytes(raw[1:5], 'big')
    if typ == 0:
        return raw[5:5 + ln]
    if typ == 1:
        return bz2.decompress(raw[9:9 + ln])
    return gzip.decompress(raw[9:9 + ln])


def gjstr(data, off):
    end = off
    while end < len(data) and data[end] != 0:
        end += 1
    raw = data[off:end]
    if any(b > 0x7F for b in raw):
        try:
            s = raw.decode('utf-8')
        except UnicodeDecodeError:
            s = raw.decode('latin1')
    else:
        s = raw.decode('latin1')
    return s, end + 1


def parse_script(data):
    """解析 CS2 ClientScript，回傳 (name, [stringOperands])。"""
    L = len(data)
    if L < 14:
        return None, []
    trailer_len = int.from_bytes(data[L - 2:], 'big')
    trailer_pos = L - trailer_len - 12 - 2
    if trailer_pos < 0 or trailer_pos >= L:
        return None, []
    instructions = int.from_bytes(data[trailer_pos:trailer_pos + 4], 'big')
    pos = trailer_pos + 4 + 8  # intLocals,stringLocals,intArgs,stringArgs
    if pos >= L:
        return None, []
    switches = data[pos]
    pos += 1
    for _ in range(switches):
        if pos + 2 > L:
            return None, []
        cases = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2 + cases * 8
    pos = 0
    if pos >= L:
        return None, []
    if data[pos] == 0:
        name = None
        pos += 1
    else:
        name, pos = gjstr(data, pos)
    strs = []
    while trailer_pos > pos and pos < L:
        cases = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
        if cases == 3:
            s, pos = gjstr(data, pos)
            strs.append(s)
        elif cases >= 100 or cases in (21, 38, 39):
            pos += 1
        else:
            pos += 4
    return name, strs


def ascii_strs(data, minlen=2):
    """掃出所有可讀 ASCII 字串（用於介面 archive）。"""
    out = []
    cur = bytearray()
    for b in data:
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= minlen:
                out.append(cur.decode('latin1'))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append(cur.decode('latin1'))
    return out


JUNK_RE = [
    re.compile(r'^[a-zA-Z0-9_]{1,3}$'),          # 短識別字
    re.compile(r'^[^a-zA-Z]+$'),                 # 無字母
    re.compile(r'^[^a-zA-Z]{1,3}[a-zA-Z]{1,2}$'),  # 符號+短字（" %n" 等）
    re.compile(r'^[a-z]{1,2}\d+$'),              # "qj104" 等
    re.compile(r'^.{0,2}$'),                     # 過短
    re.compile(r'^(<[^>]+>[ \t]*)+$'),           # 純標籤
]


def is_junk(s):
    s2 = s.strip()
    if not s2:
        return True
    for r in JUNK_RE:
        if r.match(s2):
            return True
    # 連續符號 > 4 個
    if re.fullmatch(r'[^a-zA-Z0-9 ]{5,}', s2):
        return True
    return False


def load_existing_keys(client_src, server_table):
    """收集已存在的 key。
    注意：只排除「客戶端」既有 key（base CacheTranslation）。伺服器表 EXCLUDE 會誤傷——
    skill guide 等是客戶端顯示，需要伺服器表字串也要進客戶端表。"""
    keys = set()
    if client_src and os.path.exists(client_src):
        src = open(client_src, encoding='utf-8').read()
        for m in re.finditer(r'static final String DATA\w*\s*=\s*"((?:[^"\\]|\\.)*)"', src, re.S):
            data = m.group(1).replace('\\u0000', '\u0000')
            parts = data.split('\u0000')
            for i in range(0, len(parts) - 1, 2):
                keys.add(parts[i])
    return keys


def main():
    ap = argparse.ArgumentParser(description="2009scape cache 字串萃取")
    ap.add_argument("--cache", required=True, help="cache 目錄（含 main_file_cache.*）")
    ap.add_argument("--client-src", help="CacheTranslation.java 路徑（排除既有 key）")
    ap.add_argument("--server-table", help="伺服器翻譯表 JSON（排除既有 key）")
    ap.add_argument("--out", default="cache_strings.json", help="輸出翻譯表骨架")
    ap.add_argument("--no-iface", action="store_true", help="不萃取介面 archive 3")
    ap.add_argument("--no-cs2", action="store_true", help="不萃取 CS2 archive 12")
    args = ap.parse_args()

    idx3 = open(os.path.join(args.cache, 'main_file_cache.idx3'), 'rb').read()
    idx12 = open(os.path.join(args.cache, 'main_file_cache.idx12'), 'rb').read()
    dat = open(os.path.join(args.cache, 'main_file_cache.dat2'), 'rb')

    existing = load_existing_keys(args.client_src, args.server_table)
    print(f"既有 key（排除用）: {len(existing)}")

    results = []
    seen = set()

    if not args.no_iface:
        n = 0
        for gid in range(len(idx3) // 6):
            raw = read_container(idx3, dat, gid)
            if not raw:
                continue
            try:
                data = uncompress(raw)
            except Exception:
                continue
            for s in ascii_strs(data):
                if is_junk(s) or s in existing or s in seen:
                    continue
                seen.add(s)
                results.append({"en": s, "zh-tw": "", "source": f"iface", "status": "untranslated"})
                n += 1
        print(f"介面 archive3: 新增 {n} 條")

    if not args.no_cs2:
        n = 0
        for fid in range(len(idx12) // 6):
            raw = read_container(idx12, dat, fid)
            if not raw:
                continue
            try:
                data = uncompress(raw)
            except Exception:
                continue
            name, strs = parse_script(data)
            all_s = []
            if name:
                all_s.append(name)
            all_s.extend(strs)
            for s in all_s:
                if is_junk(s) or s in existing or s in seen:
                    continue
                seen.add(s)
                results.append({"en": s, "zh-tw": "", "source": "cs2", "status": "untranslated"})
                n += 1
        print(f"CS2 archive12: 新增 {n} 條")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"萃取完成: {len(results)} 條 -> {args.out}")


if __name__ == "__main__":
    main()