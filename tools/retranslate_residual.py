#!/usr/bin/env python3
"""P3 重翻「仍含未翻一般詞」的譯文（括號外有小寫英文詞者），用本地模型 + 權威術語庫。
品質閘：譯後括號外不得再有一般英文詞、須含中文、須不等原文、須保留標籤/佔位符。"""
import json,re,os,sys,time
import requests
API=os.environ.get('LLM_API_URL','http://localhost:1234/v1/chat/completions');MODEL=os.environ.get('LLM_MODEL','gemma-4-26b-a4b-it')
BATCH=int(os.environ.get('BATCH','10'))
CJK=re.compile(r'[\u4e00-\u9fff]');LL=re.compile(r'[a-z]{3,}')
TERM='translations/terms_canonical.tsv'
def load_terms():
    common={};proper={}
    for line in open(TERM,encoding='utf-8'):
        if line.startswith('en\t'):continue
        p=line.rstrip('\n').split('\t')
        if len(p)<3 or not p[1]:continue
        (proper if p[2]=='proper' else common)[p[0]]=p[1]
    return common,proper
COMMON,PROPER=load_terms()
def parenless(v):
    t=re.sub(r'\([^()]*\)|（[^()]*）',' ',v)
    t=re.sub(r'<[^>]+>|\$\{?[^}\s]*\}?|@[a-zA-Z]+(\[[^\]]*\])?|!![^?]*\?\?|[-–—/.,:;!?…\x27\"“”\u3001\u3002\uff0c\uff1a\uff01\uff1f()\[\]]|\b\d+\b|%%?\w*',' ',t)
    return t
def residual(v):
    return bool(LL.search(parenless(v)))
def relevant(texts):
    blob=' '.join(texts).lower(); rel=[]
    for en,zh in sorted(COMMON.items(),key=lambda k:-len(k[0])):
        if en.lower() in blob: rel.append((en,zh))
        if len(rel)>=40: break
    return rel
def build(texts):
    rel=relevant(texts)
    gb=('\nUse EXACT terms: '+'; '.join(f'{e}={z}' for e,z in rel)+'\n') if rel else ''
    fmt='\n'.join(f'{i+1}. {t}' for i,t in enumerate(texts))
    return ('你是 RuneScape 2009 台灣正體中文翻譯。以下譯文仍夾雜未翻的英文(多為材質/食物/物品/一般詞)，'
            '請改寫為全中文(专有名词若已是「中文 (English)」則保留括號內英文)，語意流暢。'+gb+
            '保留 <col=..>、$var、@name、!!..??、%色碼 標記；括號外不得再有英文單詞。只輸出「編號. 譯文」。\n'+fmt)
def call(texts):
    r=requests.post(API,json={'model':MODEL,'messages':[{'role':'system','content':'Translate residual English into full Traditional Chinese (Taiwan).'},{'role':'user','content':build(texts)}],'temperature':0.2},timeout=240)
    r.raise_for_status();c=r.json()['choices'][0]['message']['content'];out={}
    for line in c.splitlines():
        m=re.match(r'^(\d+)[\.\)]?\s*(.+)$',line.strip())
        if m:out[int(m.group(1))]=m.group(2).strip()
    return out
def gate(old,new):
    if not new or new==old or not CJK.search(new): return False
    if residual(new): return False
    return True
def main():
    ap=os.path; import argparse;pa=argparse.ArgumentParser();pa.add_argument('--table',required=True);pa.add_argument('--limit',type=int,default=0);a=pa.parse_args()
    t=json.load(open(a.table,encoding='utf-8'))
    keys=[k for k,v in t.items() if CJK.search(v) and residual(v) and not k.startswith('@pre:') and '~~' not in k and '$a' not in k]
    keys.sort(key=len)
    if a.limit: keys=keys[:a.limit]
    print('待重翻:',len(keys))
    done=fix=0
    for i in range(0,len(keys),BATCH):
        ch=keys[i:i+BATCH]
        try:g=call([t[k] for k in ch])
        except Exception as e:print('retry',e);time.sleep(3);continue
        for j,k in enumerate(ch,1):
            nz=g.get(j)
            if nz and gate(t[k],nz): t[k]=nz;fix+=1
        done+=len(ch)
        if done%50==0: json.dump(t,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'));print(f'  {done}/{len(keys)} 修 {fix}')
    json.dump(t,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
    print(f'完成 {done} 修 {fix}')
main()
