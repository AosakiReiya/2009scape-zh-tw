#!/usr/bin/env python3
"""
翻譯覆蓋率驗證工具
掃描 client cache（介面 archive 3 + CS2 archive 12）與 server 翻譯表，
比對所有翻譯表（CacheTranslation / CacheTranslationExt / NameTranslation / server table），
輸出未翻譯字串清單，供定期檢查避免漏譯。

用法：
  ./verify_translation.py --cache <cache_dir> [--ext <CacheTranslationExt.java>] [--name <NameTranslation.java>] [--server <translations_zh-tw.json>]
"""

import argparse
import bz2
import gzip
import json
import os
import re
import sys


def read_container(idx_data, dat_file, file_id):
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
        return raw[9:9 + ln]
    if typ == 1:
        return bz2.decompress(raw[9:9 + ln])
    if typ == 2:
        return gzip.decompress(raw[9:9 + ln])
    return None


def ascii_strs(data):
    res = []
    cur = []
    for b in data:
        if 32 <= b < 127:
            cur.append(chr(b))
        else:
            if len(cur) >= 4:
                res.append(''.join(cur))
            cur = []
    if len(cur) >= 4:
        res.append(''.join(cur))
    return res


def is_junk(s):
    if len(s) < 4:
        return True
    if not re.search(r'[A-Za-z]{3}', s):
        return True
    if re.fullmatch(r'[A-Za-z]{4,}', s) and s.isalpha() and s == s.lower() and len(s) <= 12:
        return True
    if re.fullmatch(r'[A-Za-z]+[0-9]+|[0-9]+[A-Za-z]+', s):
        return True
    return False


def load_java_keys(path):
    """從 Java 原始碼擷取 String literal 內的 en\u0000zh 對 English key。"""
    if not path or not os.path.exists(path):
        return set()
    src = open(path, encoding='utf-8').read()
    keys = set()
    for m in re.findall(r'"([^"]*)"', src):
        parts = m.split('\\u0000')
        for i in range(0, len(parts) - 1, 2):
            if parts[i]:
                keys.add(parts[i].strip())
    return keys


def load_server_keys(path):
    if not path or not os.path.exists(path):
        return set()
    return set(json.load(open(path, encoding='utf-8')).keys())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True, help="cache 目錄（含 main_file_cache.*）")
    ap.add_argument("--ext", help="CacheTranslationExt.java 路徑")
    ap.add_argument("--name", help="NameTranslation.java 路徑")
    ap.add_argument("--server", help="translations_zh-tw.json 路徑")
    ap.add_argument("--no-iface", action="store_true")
    ap.add_argument("--no-cs2", action="store_true")
    args = ap.parse_args()

    existing = set()
    existing |= load_java_keys(args.ext)
    existing |= load_java_keys(args.name)
    existing |= load_server_keys(args.server)
    print(f"既有 key（含 Ext/Name/Server）: {len(existing)}")

    idx3 = open(os.path.join(args.cache, 'main_file_cache.idx3'), 'rb').read()
    idx12 = open(os.path.join(args.cache, 'main_file_cache.idx12'), 'rb').read()
    dat = open(os.path.join(args.cache, 'main_file_cache.dat2'), 'rb')

    missing = []
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
            if not data:
                continue
            for s in ascii_strs(data):
                if is_junk(s) or s in existing or s in seen:
                    continue
                seen.add(s)
                missing.append(("iface", s))
                n += 1
        print(f"介面 archive3 未翻譯: {n}")

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
            if not data:
                continue
            for s in ascii_strs(data):
                if is_junk(s) or s in existing or s in seen:
                    continue
                seen.add(s)
                missing.append(("cs2", s))
                n += 1
        print(f"CS2 archive12 未翻譯: {n}")

    print(f"\n總共未翻譯: {len(missing)}")
    for src, s in missing[:200]:
        print(f"  [{src}] {s}")
    if len(missing) > 200:
        print(f"  ... 其餘 {len(missing)-200} 條")


if __name__ == "__main__":
    main()