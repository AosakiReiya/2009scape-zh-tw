#!/usr/bin/env python3
"""翻譯 @pre:前~~後 模板：把前後綴以 {X} 佔位符合成完整一句一次翻譯，再把 {X} 換回 ~~。
品質閘：輸出須含 {X}（保留佔位符）且含中文、無括號外殘留英文。"""
import json,re,os,time,requests
API=os.environ.get('LLM_API_URL','http://localhost:1234/v1/chat/completions'); MODEL=os.environ.get('LLM_MODEL','gemma-4-26b-a4b-it')
CJK=re.compile(r'[\u4e00-\u9fff]'); LAT=re.compile(r'[A-Za-z]{3,}')
ALLOWED=re.compile(r'<[^>]+>|\{X\}|H\.A\.M\.?|NPC|XP|GP|ID|GE')
def batch(items):
    body=json.dumps({"model":MODEL,"messages":[{"role":"system","content":"你是 RuneScape 2009 台灣正體中文翻譯。每行含一個 {X} 佔位符（代表執行期插入的數字/名稱），翻譯整句但必須原樣保留 {X}（前後各留一空格）。保留 <col=..> 標籤。只輸出「編號. 譯文」。"},
        {"role":"user","content":"\n".join(f"{i+1}. {t}" for i,t in enumerate(items))}],"temperature":0.2}).encode()
    r=requests.post(API,data=body,headers={'Content-Type':'application/json'},timeout=240); c=r.json()['choices'][0]['message']['content']
    out={}
    for line in c.splitlines():
        m=re.match(r'^(\d+)[\.\)]?\s*(.+)$',line.strip())
        if m: out[int(m.group(1))]=m.group(2).strip()
    return out
def residual(zh):
    t=ALLOWED.sub(' ',zh); return bool(LAT.search(t))
def main():
    import argparse; ap=argparse.ArgumentParser(); ap.add_argument('--worklist'); ap.add_argument('--table'); a=ap.parse_args()
    tbl=json.load(open(a.table,encoding='utf-8'))
    tpl=[]
    for x in json.load(open(a.worklist,encoding='utf-8')):
        k=x['en']
        if '~~' not in k: continue
        pre,suf=k[5:].split('~~',1)
        pseudo=f'{pre} {{X}} {suf}'.replace('  ',' ').strip()
        tpl.append((k,pseudo))
    print('待翻模板:',len(tpl))
    ok=0
    for i in range(0,len(tpl),12):
        ch=tpl[i:i+12]
        try: g=batch([p for _,p in ch])
        except Exception as e: print('retry',e); time.sleep(3); continue
        for j,(k,pseudo) in enumerate(ch,1):
            zh=g.get(j)
            if zh and '{X}' in zh and CJK.search(zh) and not residual(zh):
                val=re.sub(r'\s*\{X\}\s*',' ~~ ',zh).strip()
                val=re.sub(r'\.{2,} ~~ ',' ~~ ',val); val=re.sub(r' ~~ \.{2,}',' ~~',val)  # 清掉佔位符旁多余的省略號
                tbl[k]=val; ok+=1
    json.dump(tbl,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
    print(f'完成：{ok}/{len(tpl)} 模板翻好寫入')
main()
