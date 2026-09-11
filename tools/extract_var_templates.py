#!/usr/bin/env python3
"""抽取「單變數、前後皆靜態字串」的訊息 → @pre 模板 worklist。
僅可靠處理: sendMessage/sendString/npcl/line 內 "A" + var + "B" 形態（恰好2段字串、1變數）。
多變數或名稱變數（matchTemplate/matchVarTemplate 難保正確）計數但不產出，避免錯 key。"""
import argparse, json, os, re, sys
CALL=re.compile(r'\b(sendMessage|sendString|sendNews|npcl|playerl|linel|sendDialogue|sendDialogues)\s*\(')
CSTR=re.compile(r'"((?:[^"\\]|\\.)*)"')
def balanced_args(src,op):
    i=op+1;depth=1;instr=False;esc=False;out=[]
    while i<len(src):
        c=src[i]
        if instr:
            out.append(c)
            if esc: esc=False
            elif c=='\\': esc=True
            elif c=='"': instr=False
        else:
            if c=='"': instr=True;out.append(c)
            elif c=='(':depth+=1;out.append(c)
            elif c==')':
                depth-=1
                if depth==0:break
                out.append(c)
            else:out.append(c)
        i+=1
    return ''.join(out)
EX=re.compile(r"Can't locate|Initialized|Loaded|Error!|register|drop|INSERT|SELECT|CREATE|DELETE|WHERE|\.dat|System\.|Exception|config length|walkable|TODO",re.I)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--src',required=True); ap.add_argument('--emit',required=True); a=ap.parse_args()
    items=[]; seen=set(); skip_multi=0
    for dp,_,fs in os.walk(a.src):
        if '/build/' in dp: continue
        for fn in fs:
            if not fn.endswith(('.kt','.java')):continue
            sp=os.path.join(dp,fn)
            try:src=open(sp,encoding='utf-8',errors='replace').read()
            except:continue
            for m in CALL.finditer(src):
                op=src.index('(',m.start()); args=balanced_args(src,op)
                if not args or '+' not in args: continue
                lits=[l.replace('\\"','"').replace('\\n',' ').strip() for l in CSTR.findall(args)]
                lits=[l for l in lits if l]
                # 計算變數槽：args 去掉字串後的 '+' 連線片段數
                stripped=CSTR.sub('§',args)
                nvar=stripped.count('§')-1 if stripped.count('§')>=2 else 0
                # 只取 恰好 2 段靜態 + 1 變數（prefix + x + suffix）
                if len(lits)!=2:
                    if len(lits)>2: skip_multi+=1
                    continue
                prefix,suffix=lits
                if len(prefix)<6 or len(suffix)<3: continue   # 前後綴太短不穩
                if EX.search(prefix+suffix): continue
                if re.search(r'[\u4e00-\u9fff]',prefix+suffix): continue
                key=f'@pre:{prefix}~~{suffix}'
                if key in seen: continue
                seen.add(key); items.append(key)
    json.dump([{'en':k,'zh-tw':'','source':'var_template','status':'untranslated'} for k in items],
              open(a.emit,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print(f'可安全模板化(單變數前后綴) : {len(items)} | 跳過(多段/名稱/其他) : {skip_multi}')
main() if __name__=='__main__' else None
