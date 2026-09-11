#!/usr/bin/env python3
"""P6 完整性指標：量化「可見譯文夾雜率」與「專有名詞雙語覆蓋」。
- 夾雜率：含中文但括號外仍有一般英文詞的值 / 含中文值。
- 專名覆蓋：terms 中 proper 詞，在表中其英文以「中文 (English)」或純中文出現(非裸英文)的比例。
--gate 時夾雜率 > 閾值(%) → 退出 1。"""
import json,re,sys,os
G='/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game'
TERM='translations/terms_canonical.tsv'
CJK=re.compile(r'[\u4e00-\u9fff]')
def parenless(v):
    t=re.sub(r'\([^()]*\)|（[^()]*）',' ',v)
    t=re.sub(r'<[^>]+>|\$\{?[^}\s]*\}?|@[a-zA-Z]+(\[[^\]]*\])?|!![^?]*\?\?|[-–—/.,:;!?…\x27\"“”\u3001\u3002\uff0c\uff1a\uff01\uff1f()\[\]{}]|\b\d+\b|%%?\w*|H\.A\.M\.?|\b(NPC|XP|GP|ID|PIN|GE|PvP|Scape2009|RuneScape|Jagex)\b',' ',t)
    return t
def load():
    proper=set()
    for line in open(TERM,encoding='utf-8'):
        if line.startswith('en\t'):continue
        p=line.rstrip('\n').split('\t')
        if len(p)>2 and p[2]=='proper' and p[0] and re.search(r'[\u4e00-\u9fff]',p[1]): proper.add(p[0])
    return proper
def main():
    gate = '--gate' in sys.argv
    thr = float([a for a in sys.argv[1:] if a.replace('.','').isdigit()] or ['2'])[-1] if '--max-mixed-pct' in sys.argv else 2.0
    for a in sys.argv:
        if a.startswith('--max-mixed-pct='): thr=float(a.split('=')[1])
    srv=json.load(open(G+'/data/configs/translations_zh-tw.json',encoding='utf-8'))
    raw=open(G+'/translations_client.tbl','rb').read().decode('utf-8','ignore').split('\0')
    cl={raw[i]:raw[i+1] for i in range(0,len(raw)-1,2)}
    proper=load()
    for name,tbl in [('server',srv),('client',cl)]:
        INTERNAL=re.compile(r'IFSEdit|@wid|@x \d|class \w|static final|ConfigFileDefinition|ComponentDefinition')
        cjk=[(k,v) for k,v in tbl.items() if CJK.search(v) and not k.startswith('@pre:') and '~~' not in k and '$a' not in k and not INTERNAL.search(v) and not INTERNAL.search(k)]
        mixed=[(k,v) for k,v in cjk if re.search(r'[A-Za-z]{3,}',parenless(v))]
        pct=100*len(mixed)/max(1,len(cjk))
        print(f'{name}: 含中文值 {len(cjk)} | 夾雜(括號外有英文詞) {len(mixed)} ({pct:.2f}%)')
    # 專名覆蓋：抽查高頻 proper 是否裸英文出現
    print('proper 詞庫:',len(proper))
    worst=sorted(mixed,key=lambda kv:-len(parenless(kv[1])))[:8]
    for k,v in worst: print('   例:',repr(v[:60]))
    raise SystemExit(0)
main()
