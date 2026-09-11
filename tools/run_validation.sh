#!/usr/bin/env bash
# 漢化一鍵驗證：規則驗證 + 完整性驗證，全部 0 違規才算通過。
# 用法：./run_validation.sh
set -u
cd "$(dirname "$0")/.."

GAME=${GAME:-/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game}
SERVER_SRC=${SERVER_SRC:-../2009scape-zh-tw-server/Server/src/main}
NAME_SRC=${NAME_SRC:-../rt4-client-zh-tw/client/src/main/java/rt4/NameTranslation.java}
GLOSSARY=${GLOSSARY:-translations/glossary.tsv}
CACHE=${CACHE:-/mnt/g/SelfHost/Runescape/2009scape/cache/runescape}
SERVER_SRC2=${SERVER_SRC2:-../2009scape-zh-tw-server/Server/src/main}
DLG_TOL=${DLG_TOL:-150}
CLIENT_SRC=${CLIENT_SRC:-../rt4-client-zh-tw/client/src/main/java}

TABLE=${TABLE:-$GAME/data/configs/translations_zh-tw.json}
# @pre 動態模板數量基線：低於此值即視為「清理誤刪模板」回歸（靜態完整性抓不到 @pre）。
PRE_MIN=${PRE_MIN:-50}

echo "========================================="
echo " 漢化驗證（表不變量 + 規則 + 完整性 + 客戶端覆蓋 + 對白）"
echo "========================================="

echo ""
echo "[1/5] 表不變量檢查（@pre 動態模板不被誤刪）..."
python3 - "$TABLE" "$PRE_MIN" <<'PYEOF'
import json, sys, re
table_path, pre_min = sys.argv[1], int(sys.argv[2])
s = json.load(open(table_path, encoding='utf-8'))
pre = {k: v for k, v in s.items() if k.startswith('@pre:')}
bad = [k for k in pre if '~~' not in k[5:] or '~~' not in pre[k] or '英文前綴' in k or pre[k].strip() == k.strip()]
print(f"  @pre 模板數: {len(pre)} (基線 >= {pre_min})")
if bad:
    print(f"  ❌ 壞的 @pre ({len(bad)}): " + ", ".join(repr(k[:40]) for k in bad[:10]))
if len(pre) < pre_min:
    print(f"  ❌ @pre 數量低於基線，疑似清理誤刪動態模板")
if len(pre) >= pre_min and not bad:
    print("  ✅ 通過")
    sys.exit(0)
sys.exit(1)
PYEOF
INVARIANT=$?

echo ""
echo "[2/5] 規則驗證（0 違規才算通過）..."
python3 tools/validate_rules.py \
  --json "$TABLE" \
  --tbl "$GAME/translations_client.tbl" \
  --glossary "$GLOSSARY" \
  --name "$NAME_SRC" \
  --report /tmp/validate_rules_report.txt
RULES=$?

echo ""
echo "[3/5] 完整性驗證（0 漏翻才算通過）..."
python3 tools/validate_completeness.py \
  --server-src "$SERVER_SRC" \
  --json "$TABLE" \
  --tbl "$GAME/translations_client.tbl" \
  --name "$NAME_SRC" \
  --report /tmp/validate_completeness_report.txt
COMPLETE=$?

echo ""
echo "[4/5] 客戶端快取覆蓋驗證（介面/CS2/NPC/物品名不被漏）..."
python3 tools/validate_client_names.py \
  --cache "$CACHE" \
  --client-src "$CLIENT_SRC" \
  --json "$TABLE" \
  --tbl "$GAME/translations_client.tbl" \
  --tolerance ${CLIENT_TOL:-6}
CLIENT=$?

echo ""
echo "[5/5] 對白/訊息覆蓋掃描（content 整句缺 key）..."
python3 tools/content_dialogue_scan.py \
  --src "$SERVER_SRC2" \
  --json "$TABLE" \
  --tbl "$GAME/translations_client.tbl" \
  --check --tolerance "$DLG_TOL"
DIALOG=$?

echo ""
echo "========================================="
if [ $INVARIANT -eq 0 ] && [ $RULES -eq 0 ] && [ $COMPLETE -eq 0 ] && [ $CLIENT -eq 0 ] && [ $DIALOG -eq 0 ]; then
  echo " ✅ 漢化驗證通過：表不變量 OK + 規則 0 違規 + 完整性 0 漏翻 + 客戶端覆蓋 OK + 對白達標"
  exit 0
else
  echo " ❌ 未通過：不變量=$([ $INVARIANT -eq 0 ] && echo OK || echo FAIL) 規則=$([ $RULES -eq 0 ] && echo OK || echo FAIL) 完整性=$([ $COMPLETE -eq 0 ] && echo OK || echo FAIL) 客戶端=$([ $CLIENT -eq 0 ] && echo OK || echo FAIL) 對白=$([ $DIALOG -eq 0 ] && echo OK || echo FAIL)"
  echo "    報告：/tmp/validate_rules_report.txt、/tmp/validate_completeness_report.txt"
  echo "    修繕後重跑本腳本直至通過。"
  exit 1
fi