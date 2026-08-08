#!/usr/bin/env bash
# 漢化一鍵驗證：規則驗證 + 完整性驗證，全部 0 違規才算通過。
# 用法：./run_validation.sh
set -u
cd "$(dirname "$0")/.."

GAME=${GAME:-/mnt/g/SelfHost/Runescape/2009scape/singleplayer/game}
SERVER_SRC=${SERVER_SRC:-../2009scape-zh-tw-server/Server/src/main}
NAME_SRC=${NAME_SRC:-../rt4-client-zh-tw/client/src/main/java/rt4/NameTranslation.java}
GLOSSARY=${GLOSSARY:-translations/glossary.tsv}

echo "========================================="
echo " 漢化驗證（規則 + 完整性）"
echo "========================================="

echo ""
echo "[1/2] 規則驗證（0 違規才算通過）..."
python3 tools/validate_rules.py \
  --json "$GAME/data/configs/translations_zh-tw.json" \
  --tbl "$GAME/translations_client.tbl" \
  --glossary "$GLOSSARY" \
  --name "$NAME_SRC" \
  --report /tmp/validate_rules_report.txt
RULES=$?

echo ""
echo "[2/2] 完整性驗證（0 漏翻才算通過）..."
python3 tools/validate_completeness.py \
  --server-src "$SERVER_SRC" \
  --json "$GAME/data/configs/translations_zh-tw.json" \
  --tbl "$GAME/translations_client.tbl" \
  --name "$NAME_SRC" \
  --report /tmp/validate_completeness_report.txt
COMPLETE=$?

echo ""
echo "========================================="
if [ $RULES -eq 0 ] && [ $COMPLETE -eq 0 ]; then
  echo " ✅ 漢化驗證通過：規則 0 違規 + 完整性 0 漏翻"
  exit 0
else
  echo " ❌ 未通過：規則=$([ $RULES -eq 0 ] && echo OK || echo FAIL) 完整性=$([ $COMPLETE -eq 0 ] && echo OK || echo FAIL)"
  echo "    報告：/tmp/validate_rules_report.txt、/tmp/validate_completeness_report.txt"
  echo "    修繕後重跑本腳本直至通過。"
  exit 1
fi