#!/usr/bin/env python3
"""P2 一致化重寫 server json + client tbl 的譯文值：
(1) KNOWN_FIXES：已知錯譯/變體 → 權威譯（精確替換）
(2) 專有名詞 paren-aware 雙語化：括號外出現的 proper 英文詞補成「zh (English)」
"""
import json,re,sys
from collections import Counter
G='/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game'
TERM='translations/terms_canonical.tsv'
TBL=G+'/data/configs/translations_zh-tw.json'
TBLT=G+'/translations_client.tbl'
# 已知錯譯/變體統一（左→右），只在含中文值裡做完整詞替換
KNOWN_FIXES=[
 ('里明頓','瑞明頓'),('林明頓','瑞明頓'),
 ('符文金屬','符文'),('符文金属','符文'),
 ('西der','蘋果酒'),
 ('阿爾卡里德','阿爾卡裡德'),
]
def load_terms():
    proper={};common={}
    for line in open(TERM,encoding='utf-8'):
        if line.startswith('en\t'):continue
        p=line.rstrip('\n').split('\t')
        if len(p)<3 or not p[1]:continue
        if p[2]=='proper':proper[p[0]]=p[1]
        elif p[2]=='common':common[p[0]]=p[1]
    return proper,common
CJK=re.compile(r'[\u4e00-\u9fff]')
PAREN=re.compile(r'(\([^()]*\)|（[^()]*）)')
def proper_regex(proper):
    keys=sorted(proper,key=len,reverse=True)
    big='|'.join(re.escape(k) for k in keys)
    return re.compile(r'(?<![A-Za-z])('+big+r')(?![A-Za-z])')
def bilingualize_outside(value, proper, rx):
    # 分段：括號內容保持原樣，只處理括號外
    parts=PAREN.split(value); 
    def fix(seg, is_paren):
        if is_paren or not seg: return seg
        return rx.sub(lambda m: f'{proper[m.group(1)]} ({m.group(1)})', seg)
    out=[]
    for i,seg in enumerate(parts):
        is_paren = (i%2==1)
        out.append(fix(seg,is_paren))
    return ''.join(out)
COMMON_RX=None
COMMON={}
def build_common_rx(common):
    keys=sorted([k for k in common if k[0].isalpha()],key=len,reverse=True)
    pat='|'.join(re.escape(k) for k in keys)
    return re.compile(r'(?<![A-Za-z])('+pat+r')(?![A-Za-z])') if keys else None
def common_replace(value,common,rx):
    if not rx: return value
    parts=PAREN.split(value);out=[]
    for i,seg in enumerate(parts):
        if i%2==1 or not seg: out.append(seg);continue
        out.append(rx.sub(lambda m: common[m.group(1)], seg))
    return ''.join(out)
def known_fix(value):
    for a,b in KNOWN_FIXES:
        if a in value: value=value.replace(a,b)
    return value
def dedup_bilingual(value):
    # 修「zh (zh (en))」或重複 "(en) (en)"
    value=re.sub(r'\(([^()]*?) \(([^()]+)\)\)', r'(\2)', value)
    return value
def process(tbl, proper, rx, label):
    global COMMON_RX, COMMON
    chg=0
    for k in list(tbl.keys()):
        v=tbl[k]
        if not isinstance(v,str) or not v: continue
        nv=v
        if CJK.search(nv):
            nv=known_fix(nv); nv=common_replace(nv,COMMON,COMMON_RX); nv=bilingualize_outside(nv,proper,rx); nv=dedup_bilingual(nv)
        if nv!=v: tbl[k]=nv; chg+=1
    print(f'{label}: 改寫 {chg} 條值')
    return tbl
def main():
    proper,common=load_terms(); rx=proper_regex(proper);
    globals()['COMMON_RX']=build_common_rx(common); globals()['COMMON']=common
    print(f'proper 詞數: {len(proper)}')
    srv=json.load(open(TBL,encoding='utf-8'))
    srv=process(srv,proper,rx,'server json')
    json.dump(srv,open(TBL,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
    raw=open(TBLT,'rb').read().decode('utf-8','ignore').split('\0')
    cl={raw[i]:raw[i+1] for i in range(0,len(raw)-1,2)}
    order=[raw[i] for i in range(0,len(raw)-1,2)]
    cl=process(cl,proper,rx,'client tbl')
    open(TBLT,'wb').write('\0'.join(f'{k}\0{cl[k]}' for k in order).encode('utf-8'))
    print('P2 完成')
main() if __name__=='__main__' else None
