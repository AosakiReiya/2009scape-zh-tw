#!/usr/bin/env python3
"""P1 建權威術語庫 terms_canonical.tsv。
en \t zh \t category(proper|common) \t bilingual(yes|no) \t source
proper→雙語「zh (en)」；common→純 zh。已知錯譯用 OVERRIDE 覆蓋。"""
import json,re,os,sys
from collections import Counter
WS='/mnt/g/SelfHost/Runescape/2009scape-zh-tw-workspace'
G=WS+'/../Runescape/2009scape/singleplayer/game' if False else '/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game'
GL='translations/glossary.tsv'
KT='/mnt/g/SelfHost/Runescape/2009scape-zh-tw-workspace/2009scape-zh-tw-server/Server/src/main/core/api/Translation.kt'
QT='/mnt/g/SelfHost/Runescape/2009scape-zh-tw-workspace/2009scape-zh-tw-server/Server/src/main/content/data/Quests.kt'
OUT='translations/terms_canonical.tsv'
RPT='translations/term_conflicts.txt'

# 已知錯譯/衝突的權威定稿
OVERRIDE={
 'Runite':'符文','Adamantite':'精鋼','Mithril':'祕銀',
 'Rimmington':'瑞明頓','Taverley':'塔弗利','Taverly':'塔弗利','Rellekka':'雷萊卡',
 'Cider':'蘋果酒','Camelot':'卡美洛','Catherby':'卡瑟比','Varrock':'瓦洛克',
 'Lumbridge':'倫布里奇','Falador':'法魯多','Ardougne':'阿爾多內','Yanille':'亞尼爾',
 'Canifis':'卡尼菲斯','Burthorpe':'伯索普','Edgeville':'艾吉村','Draynor':'卓奈爾',
 'Keldagrim':'凱爾達格林','Sophanem':'索法內姆','Pollnivneach':'波利尼夫內赫',
 'Phasmatys':'phasmatys','Zanaris':'札納里斯','Dorgesh-Kaan':'多吉舒恩',
 'Saradomin':'薩拉多明','Zamorak':'札莫拉克','Guthix':'古希斯','Armadyl':'阿瑪迪爾',
 'Bandos':'班多斯','Zaros':'扎羅斯','Elidinis':'艾利迪尼斯','Seren':'瑟倫',
}
# 專有名詞 whitelist（地名/神/種族/群系）
PLACE=set("""Lumbridge Varrock Falador Edgeville Draynor Catherby Camelot Ardougne Yanille Canifis Burthorpe Taverley Taverly Rellekka Keldagrim Sophanem Pollnivneach Zanaris Rimmington Brimhaven Crandor Entrana Miscellania Jatizso Neitiznot Lletya Piscatoris Hemenster Asgarnia Dorgeshuun Paterdomus Khazard Shantay Jiggig Isafdar Meiyerditch Karamja Morytania Misthalin Kandarin Fremennik Imcando Vyrewatch TzHaar GuTanoth""".split())
GODRACE=set("Saradomin Zamorak Guthix Armadyl Bandos Zaros Elidinis Seren Rellugosh".split())
GENERIC_NPC=set("Man Woman Guard Priest Trader Farmer Soldier Pirate Monk Knight Wizard Druid Barbarian".split())


SRVTBL='/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game/data/configs/translations_zh-tw.json'
def load_server_zh():
    import json as _j
    t=_j.load(open(SRVTBL,encoding='utf-8'))
    out={}
    for en,zh in t.items():
        if en==en.strip() and re.search(r'[\u4e00-\u9fff]',zh) and not re.search(r'<col|<str|\$',en):
            # 取中文主體（去尾隨 "(English)"）
            out.setdefault(en, re.sub(r'\s*\(([^()]*)\)\s*$','',zh).strip())
    return out

def load_glossary():
    d={}
    for line in open(GL,encoding='utf-8'):
        p=line.rstrip('\n').split('\t')
        if len(p)>=2 and p[0] and p[1] and p[0].lower()!='en':
            d[p[0]]=(p[1], p[2] if len(p)>2 else '')
    return d
def load_namebi():
    s=open(KT,encoding='utf-8',errors='replace').read()
    return {m[0]:m[1] for m in re.findall(r'"([^"]+)" to "([^"]*)"', s) if re.search(r"[\u4e00-\u9fff]", m[1])}
def load_quests():
    s=open(QT,encoding='utf-8',errors='replace').read()
    return sorted(set(x.strip() for _,x in re.findall(r'([A-Z]\(?[A-Z]?[A-Z0-9_]*)\("([^"]+)"\)', s)))

def proper_or_common(en, note, namebi, quests):
    low=en.lower()
    if en in namebi or en in quests: return 'proper'
    if en in PLACE or en in GODRACE or low in {p.lower() for p in PLACE}: return 'proper'
    if note=='npc' and en not in GENERIC_NPC and re.match(r'^[A-Z][a-z]+$',en) is None and ' ' in en:
        # 多詞具名 NPC（非泛稱）→ proper 保守；單詞具名也常見，但泛稱已排除
        pass
    if note=='npc' and en not in GENERIC_NPC:
        # 單字具名（Hans, Bob…）視為 proper；泛稱(Man/Woman)common
        return 'proper' if not re.fullmatch(r'(Man|Woman|Boy|Girl|Guard|Priest|Trader|Farmer|Soldier|Citizen|Citizens|Monk|Knight|Wizard|Druid|Barbarian|Fighter|Archer|Mage|Merchant|Servant|Slave|Gnome|Dwarf|Elf|Ogre|Imp|Goblin)', en) else 'common'
    if note=='item':
        # 具名獨有物品（含大寫專名）→proper，其餘(材質/食物/普通裝備)→common
        if re.search(r'\b(Dragon|God|Armadyl|Bandos|Saradomin|Zamorak|Ancient|Torva|Inquisitor|Seculte|Viggora|Arcane|Anima|Ursine|TzHaar|Dragonstone|Onyx|Berserker|Brawler|Venator|Warp|Occult|Purity|Eldritch|Ancestral|Necrotic|Prowler)\b', en): return 'proper'
        return 'common'
    if note in ('shop','material','gear'): return 'common'
    return 'common'

def main():
    gl=load_glossary(); nb=load_namebi(); qs=set(load_quests())
    canon={}
    # glossary 為 base
    for en,(zh,note) in gl.items():
        cat=proper_or_common(en,note,nb,qs)
        z=OVERRIDE.get(en, zh)
        canon[en]=(z,cat,note or 'glossary')
    # NAME_BI / quests 補進（若未收錄）
    for en,zh in nb.items():
        if en not in canon: canon[en]=(OVERRIDE.get(en,zh),'proper','namebi')
    for en in qs:
        if en not in canon: canon[en]=(OVERRIDE.get(en, nb.get(en,'')),'proper','quest')
    szh=load_server_zh()
    for en in list(canon):
        zh,cat,src=canon[en]
        if not re.search(r'[\u4e00-\u9fff]', zh or ''):
            alt=nb.get(en) or OVERRIDE.get(en) or szh.get(en)
            if alt and re.search(r'[\u4e00-\u9fff]',alt):
                canon[en]=(alt,cat,src)
    # 寫出
    with open(OUT,'w',encoding='utf-8') as f:
        f.write('en\tzh\tcategory\tbilingual\tsource\n')
        for en,(zh,cat,src) in sorted(canon.items()):
            bi='yes' if cat=='proper' else 'no'
            f.write(f'{en}\t{zh}\t{cat}\t{bi}\t{src}\n')
    proper=sum(1 for v in canon.values() if v[1]=='proper')
    empty=sum(1 for en,(zh,cat,src) in canon.items() if not zh)
    print(f'server: terms={len(canon)} proper={proper} common={len(canon)-proper} 缺zh={empty}')
    print('已寫', OUT)

if __name__=='__main__': main()
