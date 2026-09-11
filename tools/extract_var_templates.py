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
    out=[]; seen=set(); skip=0
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
                # 依頂層 + 切成 token 序列，標記字串/非字串(var)
                toks=re.split(r'(?<=[^"])\s*\+\s*(?=[^"])',args)  # 粗略
                segs=[]; nvar=0
                for tk in toks:
                    q=re.fullmatch(r'\s*"((?:[^"\\]|\\.)*)"\s*',tk)
                    if q: segs.append(q.group(1).replace('\\"','"').replace('\\n',' ').strip())
                    else:
                        if re.search(r'[A-Za-z_$.]',tk): segs.append('VAR'); nvar+=1
                if nvar==0 or nvar>2: skip+= (1 if nvar>2 else 0); continue
                litl=[s for s in segs if s!='VAR']
                if not all(litl) or any(EX.search(x) for x in litl): skip+=1; continue
                if any(not re.search(r'[A-Za-z]',x) for x in litl): continue
                # 佔位 pseudo：VAR 槽放 {X}/{Y}
                PH=['{X}','{Y}']; vi=0; pseudo=[]
                for seg in segs:
                    if seg=='VAR': pseudo.append(PH[vi]); vi+=1
                    else: pseudo.append(seg)
                pseudo=' '.join(pseudo).replace('  ',' ').strip()
                if nvar==1:
                    pre,suf=(segs[0] if segs[0]!='VAR' else ''), (segs[-1] if segs[-1]!='VAR' else '')
                    if len(segs)==2:  # var 在前: @pre enPre='' 會過度匹配 → 跳過
                        continue
                    if len(pre)<6 or len(suf)<3: skip+=1; continue
                    key=f'@pre:{pre}~~{suf}'
                else:
                    # 2 var: key = lit0 $a lit1 $b lit2 (僅取含 3 段字串 0VAR1VAR2)
                    if segs.count('VAR')!=2 or len(litl)!=3: skip+=1; continue
                    p0,p1,p2=litl
                    if len(p0)<5 or len(p1)<3 or len(p2)<3: skip+=1; continue
                    key=f'{p0} $a {p1} $b {p2}'
                if len(pseudo)<12 or key in seen: continue
                if re.search(r'[\u4e00-\u9fff]',pseudo): continue
                seen.add(key); out.append({'key':key,'en':pseudo})
    json.dump(out,open(a.emit,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print(f'模板候選: {len(out)} (含1變數@pre + 2變數$a/$b) | 跳過: {skip}')
main() if __name__=='__main__' else None
