#!/usr/bin/env python3
"""翻譯 content_dialogue_scan 抽出的整句對白/訊息缺口，寫回翻譯表。
本地模型（OpenAI 相容端點）+ 品質閘：仍含括號外英文、或譯文==原文 → 拒收。"""
import argparse, json, os, re, time
import requests
API=os.environ.get('LLM_API_URL','http://localhost:1234/v1/chat/completions')
MODEL=os.environ.get('LLM_MODEL','gemma-4-26b-a4b-it')
BATCH=int(os.environ.get('BATCH','12'))
CJK=re.compile(r'[\u4e00-\u9fff]')
LAT=re.compile(r'[A-Za-z]{2,}')
ALLOWED=re.compile(r'<[^>]+>|\$\{[^}]*\}|\$[A-Za-z_][A-Za-z_0-9]*|@[a-zA-Z]+(\[[^\]]*\])?|%[A-Za-z]+|!![^?]*\?\?|H\.A\.M\.?|NPC|XP|GP|ID|PIN|GE|Tokkul|TzHaar|RuneScape|Jagex|Scape|Team-\d')
def clean(s):
    s=re.sub(r'^[)\}\s]+','',s).strip()
    if re.match(r'^(else|return|if|null|this|new|for|while|var|val|fun|void|private|public|static)\b',s): return ''
    if re.search(r'[{}]|=>|^\W{3,}',s): return ''
    return s
LOWLAT=re.compile(r'[a-z]{4,}')   # 小寫英文詞=真的未翻；大寫專名交給 NAME_BI，允許
def residual_english(zh):
    t=re.sub(r'\([^()]*\)|（[^()]*）',' ',zh); t=ALLOWED.sub(' ',t); t=re.sub(r'[A-Za-z]{1,3}\b',' ',t)  # 放行短縮寫
    return bool(LOWLAT.search(t))
def load_gloss(p):
    g={}
    if p and os.path.exists(p):
        for line in open(p,encoding='utf-8'):
            q=line.rstrip('\n').split('\t')
            if len(q)>=2 and q[0] and q[1] and q[0].lower()!='en': g[q[0]]=q[1]
    return g
def build(texts,gloss):
    blob=' '.join(texts).lower()
    rel=[(e,z) for e,z in sorted(gloss.items(),key=lambda k:-len(k[0])) if e.lower() in blob][:50]
    gb=('\nUse EXACTLY these term translations: '+'; '.join(f'{e}={z}' for e,z in rel)+'\n') if rel else ''
    fmt='\n'.join(f'{i+1}. {t}' for i,t in enumerate(texts))
    return (f'你是 RuneScape 2009 遊戲的台灣正體中文翻譯。翻譯以下遊戲內对白/訊息為自然流暢的台灣正體中文。{gb}'
            f'規則：保留 <col=..>、<br>、$變數、@name、!!著色??、%顏色碼 等標記原樣；'
            f'人名/地名不必加括號重複英文（另有系統處理）；只翻語意。只輸出「編號. 譯文」每行一條。\n{fmt}')
def call(texts,gloss):
    r=requests.post(API,json={'model':MODEL,'messages':[{'role':'system','content':'You translate RuneScape dialogue into Traditional Chinese (Taiwan).'},{'role':'user','content':build(texts,gloss)}],'temperature':0.2},timeout=240)
    r.raise_for_status(); c=r.json()['choices'][0]['message']['content']
    out={}
    for line in c.splitlines():
        m=re.match(r'^(\d+)[\.\)]?\s*(.+)$',line.strip())
        if m: out[int(m.group(1))]=m.group(2).strip()
    return out
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--worklist',required=True); ap.add_argument('--table',required=True)
    ap.add_argument('--glossary'); ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args()
    tbl=json.load(open(a.table,encoding='utf-8'))
    gloss=load_gloss(a.glossary)
    items=[]
    for x in json.load(open(a.worklist,encoding='utf-8')):
        c=clean(x['en'])
        if c and c not in tbl and len(c)>=10: items.append(c)
    if a.limit: items=items[:a.limit]
    print('待翻整句:',len(items))
    done=fixed=0
    for i in range(0,len(items),BATCH):
        chunk=items[i:i+BATCH]
        try: got=call(chunk,gloss)
        except Exception as e: print('  batch err',e); time.sleep(3); continue
        for j,src in enumerate(chunk,1):
            zh=got.get(j)
            if zh and CJK.search(zh) and zh!=src and not residual_english(zh):
                tbl[src]=zh; fixed+=1
            else:
                done_skip=1
        done+=len(chunk)
        if done%60==0:
            json.dump(tbl,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
            print(f'  進度 {done}/{len(items)} 已寫 {fixed}')
    json.dump(tbl,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
    print(f'完成：處理 {done} 寫入 {fixed} 拒收 {done-fixed} | 表 {len(tbl)}')
if __name__=='__main__': main()
