#!/usr/bin/env python3
"""內容對話/訊息 覆蓋掃描（共用）：找 content .kt/.java 裡玩家可見、但整句缺 key 的對白/訊息。
引擎已改 translatePage（整句優先→退回逐行），故需以「整句」為 key。
- --emit worklist.json : 輸出待翻整句清單
- --check --json..--tbl.. : 回報缺口數，> tolerance 退出 1
排除：console/SQL/咒語/擬聲/程式標記/含變數難匹配者（含變數另計）。
"""
import argparse, json, os, re, sys

CALL = re.compile(r'\b(npc|npcl|player|playerl|line|linel|sendMessage|sendMessages|sendDialogue|sendDialogues|sendString|sendItemMessage|item)\s*\(')
CSTR = re.compile(r'"((?:[^"\\]|\\.)*)"')
CJK = re.compile(r'[\u4e00-\u9fff]')
EX = re.compile(
    r"Can't locate|Initialized|Loaded up|Loaded |Error!|register|drop table|drop_table"
    r"|INSERT|SELECT |CREATE TABLE|DELETE FROM|UPDATE |WHERE |price_index|bot_|high_volume"
    r"|\.dat2?|\.txt|TODO|::calc|<table|getQuest|getAttribute|setAttribute|npc\.id|player\."
    r"|System\.|Exception|config length|walkable|^\W*$|%[a-z]|\$\{", re.I)
SPELL = re.compile(r'^(Veni|Sall|Sent|Snarth|Klar|Sep|Dips|Vid|Ann|Mir|Sin|Grr|Gra|Arrg|Schl'
                   r'|Schorp|Howl|Oi|Dinten|Q.ex|Ukk|Brack|Avach|Achey|Finales|Castus|Absolutus'
                   r'|Defeati|Present|With least|Holarius|Possessus|projectus|Es lem|Mi lov|Throwus'
                   r'|Dagon|Icth|Zaros|Saradomin|Guthix|Zamorak|Armadyl|Bandos|Elidinis)', re.I)

def balanced_args(src, open_paren):
    """回傳 '(' 之後、對應 ')' 之前的內容字串。"""
    i = open_paren + 1; depth = 1; in_str = False; esc = False
    start = i; out = []
    while i < len(src):
        c = src[i]
        if in_str:
            out.append(c)
            if esc: esc = False
            elif c == '\\': esc = True
            elif c == '"': in_str = False
        else:
            if c == '"': in_str = True; out.append(c)
            elif c == '(': depth += 1; out.append(c)
            elif c == ')':
                depth -= 1
                if depth == 0: break
                out.append(c)
            else: out.append(c)
        i += 1
    return ''.join(out)

def literals(args):
    return [m.group(1).replace('\\"','"').replace('\\n',' ').replace('\\t',' ').replace("\\'","'").strip()
            for m in CSTR.finditer(args)]

def looks_var(args):
    """參數是否含非字串變數拼接（簡化：有 ' + ' 且兩側非都是引號）。"""
    stripped = CSTR.sub('', args)   # 去掉所有字串
    return '+' in stripped and re.search(r'[A-Za-z_$][A-Za-z_0-9.]*', stripped)

def scan(root, cov):
    full_gaps=[]; var_gap=0; seen=set()
    for dp,_,fs in os.walk(root):
        if '/build/' in dp or '/target/' in dp: continue
        for fn in fs:
            if not fn.endswith(('.kt','.java')): continue
            sp=os.path.join(dp,fn)
            try: src=open(sp,encoding='utf-8',errors='replace').read()
            except: continue
            for m in CALL.finditer(src):
                op=src.index('(',m.start())
                args=balanced_args(src,op)
                if not args: continue
                lits=[l for l in literals(args) if l and not EX.search(l)]
                if not lits: continue
                if looks_var(args):
                    # 拼接：若所有固定字串都已翻則跳過，否則計數（另需模板）
                    if any(x not in cov and re.search(r"[A-Za-z]{3,} ", x) and not CJK.search(x) and len(x) >= 10 for x in lits):
                        var_gap+=1
                    continue
                joined=' '.join(lits).strip()
                j=joined
                j=re.sub(r'^[)\}\s]+','',j).strip()          # 剝 ${...} 閉合括弧雜訊
                j=re.sub(r'^else\s+[)}]*\s*','',j)             # 剝 else 分支前綴
                if re.match(r'^(else|return|if|null|this|new|for|while|var|val|fun)\b',j) or re.search(r'[{}]|=>',j):
                    continue
                joined=j
                if len(joined)<10 or CJK.search(joined) or not re.search(r'[A-Za-z]{3,} [A-Za-z]',joined) or SPELL.match(joined):
                    continue
                # 整句已在表 or 每個片段都在表 → OK（引擎兩者皆可命中）
                if joined in cov or all(l in cov for l in lits):
                    continue
                if joined in seen: continue
                seen.add(joined)
                full_gaps.append(joined)
    return full_gaps, var_gap

def load_cov(args):
    cov=set()
    if args.json: cov.update(json.load(open(args.json,encoding='utf-8')).keys())
    if args.tbl:
        d=open(args.tbl,'rb').read().split(b'\0')
        cov.update(d[i].decode('utf-8','replace') for i in range(0,len(d)-1,2))
    return cov

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--src',required=True)
    ap.add_argument('--json'); ap.add_argument('--tbl')
    ap.add_argument('--emit'); ap.add_argument('--check',action='store_true'); ap.add_argument('--tolerance',type=int,default=40)
    a=ap.parse_args()
    cov=load_cov(a)
    gaps,var=scan(a.src,cov)
    print(f"整句缺 key（對白/訊息）: {len(gaps)} | 含變數拼接缺模板(另計): {var}")
    if a.emit:
        json.dump([{'en':g,'zh-tw':'','source':'dialogue','status':'untranslated'} for g in gaps],
                  open(a.emit,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
        print('已輸出', a.emit)
    if a.check:
        if len(gaps) > a.tolerance:
            print(f"結果: ❌ 整句缺口 {len(gaps)} > 容差 {a.tolerance}")
            for g in gaps[:30]: print('   ',repr(g[:80]))
            raise SystemExit(1)
        print('結果: ✅ 對白/訊息覆蓋達標')
    raise SystemExit(0)

if __name__=='__main__': main()
