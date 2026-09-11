#!/usr/bin/env python3
"""
客戶端快取字串覆蓋驗證：補 validate_completeness 不掃客戶端的盲區。
掃描 cache 介面(archive3)+CS2(archive12) 的「玩家可見英文顯示字串」，
比對 全部客戶端字典（server json ∪ client tbl ∪ NameTranslation ∪
CacheTranslation DATA/Ext），回報未覆蓋者。

用法：
  ./validate_client_names.py --cache <cache_dir> --client-src <rt4 client src dir> \
      --json <translations_zh-tw.json> --tbl <translations_client.tbl> [--tolerance 6]
退出碼：未覆蓋(多詞可翻句) > tolerance 時 1。
"""
import argparse, bz2, gzip, json, os, re, sys

def read_container(idx, dat, fid):
    e = idx[fid*6:fid*6+6]
    if len(e) < 6: return None
    ln = int.from_bytes(e[0:3],'big'); sec = int.from_bytes(e[3:6],'big')
    if not ln or not sec: return None
    out=bytearray(); part=0
    while len(out)<ln:
        dat.seek(520*sec); h=dat.read(8)
        if len(h)<8: break
        cp=int.from_bytes(h[2:4],'big'); nx=int.from_bytes(h[4:7],'big')
        out+=dat.read(512)[:min(512,ln-len(out))]
        if cp!=part or len(out)>=ln: break
        part+=1; sec=nx
        if not sec: break
    raw=bytes(out); t=raw[0]; l=int.from_bytes(raw[1:5],'big')
    try:
        if t==0: return raw[5:5+l]
        if t==1: return bz2.decompress(raw[9:9+l])
        return gzip.decompress(raw[9:9+l])
    except Exception:
        return None

def ascii_strs(d, ml=4):
    out=[]; c=bytearray()
    for b in d:
        if 32<=b<127: c.append(b)
        else:
            if len(c)>=ml: out.append(c.decode('latin1'))
            c=bytearray()
    if len(c)>=ml: out.append(c.decode('latin1'))
    return out

JUNK=[re.compile(r'^[A-Za-z0-9_]{1,3}$'), re.compile(r'^[^a-zA-Z]+$'),
      re.compile(r'^[a-z]{1,2}\d+$'), re.compile(r'^(<[^>]+>[ \t]*)+$'),
      re.compile(r'^\w+[:_]\w+$'), re.compile(r'^(lj|qj|obj|if)[a-z]?\d+$', re.I),
      re.compile(r'^\d')]
MARK=re.compile(r'@|\\|\$|%[A-Za-z]|\{|\}|\bIF\b|\.png|\.model|\.anim|\.base')
SENT=re.compile(r'[A-Za-z]{3,}[ \-][A-Za-z0-9]')

def load_covered(args):
    cov=set()
    if args.json:
        cov.update(json.load(open(args.json,encoding='utf-8')).keys())
    if args.tbl:
        d=open(args.tbl,'rb').read().split(b'\0')
        cov.update(d[i].decode('utf-8','replace') for i in range(0,len(d)-1,2))
    cs=args.client_src
    for fn in ['NameTranslation.java','CacheTranslation.java','CacheTranslationExt.java']:
        p=os.path.join(cs,'rt4',fn)
        if not os.path.exists(p): continue
        src=open(p,encoding='utf-8',errors='replace').read()
        for m in re.finditer(r'String\s+\w+\s*=\s*"((?:[^"\\]|\\.)*)"',src,re.S):
            parts=m.group(1).replace('\\u0000','\u0000').split('\u0000')
            for i in range(0,len(parts)-1,2): cov.add(parts[i].strip())
        # 也解析 String[] name = { "k","v", ... } 陣列字面值（如 NameTranslation.extra）
        for am in re.finditer(r'String\[\]\s+\w+\s*=\s*\{(.*?)\};',src,re.S):
            toks=re.findall(r'"((?:[^"\\]|\\.)*)"',am.group(1))
            for i in range(0,len(toks)-1,2): cov.add(toks[i].strip())
    return cov

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cache',required=True)
    ap.add_argument('--client-src',required=True)
    ap.add_argument('--json'); ap.add_argument('--tbl')
    ap.add_argument('--tolerance',type=int,default=6)
    a=ap.parse_args()
    cov=load_covered(a)
    idx3=open(os.path.join(a.cache,'main_file_cache.idx3'),'rb').read()
    idx12=open(os.path.join(a.cache,'main_file_cache.idx12'),'rb').read()
    dat=open(os.path.join(a.cache,'main_file_cache.dat2'),'rb')
    miss={}
    for idx in (idx3,idx12):
        for gid in range(len(idx)//6):
            d=read_container(idx,dat,gid)
            if not d: continue
            for s in ascii_strs(d):
                s=s.strip()
                if any(r.match(s) for r in JUNK) or not SENT.search(s) or MARK.search(s): continue
                if s in cov: continue
                if not re.search(r'[A-Z][a-z]{2,}',s): continue   # 至少一個專名/詞
                if s not in miss: miss[s]='1'
    n=len(miss)
    print(f"客戶端字典 key: {len(cov)} | 介面/CS2 未覆蓋多詞顯示字串: {n}")
    for s in sorted(miss)[:40]:
        print('   ',repr(s[:70]))
    if n> a.tolerance:
        print(f"結果: ❌ 未覆蓋 {n} > 容差 {a.tolerance}")
        raise SystemExit(1)
    print("結果: ✅ 客戶端覆蓋達標")
    raise SystemExit(0)

if __name__=='__main__':
    main()
