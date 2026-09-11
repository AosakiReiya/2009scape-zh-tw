#!/usr/bin/env python3
import json,re,os,time,requests
API=os.environ.get('LLM_API_URL','http://localhost:1234/v1/chat/completions');MODEL=os.environ.get('LLM_MODEL','gemma-4-26b-a4b-it')
CJK=re.compile(r'[\u4e00-\u9fff]')
def batch(items):
    body=json.dumps({"model":MODEL,"messages":[{"role":"system","content":"你是 RuneScape 2009 台灣正體中文翻譯。句子含 {X}/{Y} 佔位符(執行期數字/名稱)，原樣保留佔位符與 <col=..> 標籤，翻成自然台灣正體中文。只輸出「編號. 譯文」。"},
      {"role":"user","content":"\n".join(f"{i+1}. {t}" for i,t in enumerate(items))}],"temperature":0.2}).encode()
    r=requests.post(API,data=body,headers={'Content-Type':'application/json'},timeout=240)
    c=r.json()['choices'][0]['message']['content'];out={}
    for line in c.splitlines():
        m=re.match(r'^(\d+)[\.\)]?\s*(.+)$',line.strip())
        if m:out[int(m.group(1))]=m.group(2).strip()
    return out
def main():
    import argparse;ap=argparse.ArgumentParser();ap.add_argument('--worklist');ap.add_argument('--table');a=ap.parse_args()
    t=json.load(open(a.table,encoding='utf-8'))
    cands=[x for x in json.load(open(a.worklist,encoding='utf-8')) if not (x['key'] in t and CJK.search(t.get(x['key'],'')))]
    print('待處理(新key):',len(cands))
    ok=0
    for i in range(0,len(cands),12):
        ch=cands[i:i+12]
        try: g=batch([c['en'] for c in ch])
        except Exception as e: print('retry',e);time.sleep(3);continue
        for j,c in enumerate(ch,1):
            zh=g.get(j)
            if not zh or not CJK.search(zh): continue
            key=c['key']
            if key.startswith('@pre:'):
                if '{X}' not in zh: continue
                val=re.sub(r'\s*\{X\}\s*',' ~~ ',zh).strip()
                if val.count('~~')!=1: continue
                t[key]=val; ok+=1
            else:
                if '{X}' not in zh or '{Y}' not in zh: continue
                val=zh.replace('{X}','$a').replace('{Y}','$b'); val=re.sub(r'\s+',' ',val).strip()
                if '$a' not in val or '$b' not in val: continue
                t[key]=val; ok+=1
    json.dump(t,open(a.table,'w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))
    print(f'寫入新模板 {ok} | 表 {len(t)} | @pre {sum(1 for k in t if k.startswith("@pre:"))} | $模板 {sum(1 for k in t if "$a" in k)}')
main()
