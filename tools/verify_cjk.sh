#!/usr/bin/env bash
# 驗證 CJK 渲染管線：用改造後的 client jar 繪製中文字並輸出 PNG。
#
# 前置：先執行 ./build_client.sh 產出 work/client-zh-tw.jar
#
# 用法：./verify_cjk.sh [文字] [輸出.png]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
JAR="$ROOT_DIR/work/client-zh-tw.jar"
TOOLS="$SCRIPT_DIR"
OUT="${2:-$ROOT_DIR/work/cjk_raster_test.png}"
TEXT="${1:-正體中文測試}"

if [ ! -f "$JAR" ]; then
  echo "ERROR: 找不到 $JAR，請先執行 ./build_client.sh" >&2
  exit 1
fi

JAVA="${JAVA_HOME:-$(dirname "$(dirname "$(command -v java)")")}/bin/java"
if [ ! -x "$JAVA" ]; then
  JAVA="$(command -v java)"
fi

mkdir -p "$(dirname "$OUT")"
cp "$TOOLS/TestCJK.java" "$ROOT_DIR/work/TestCJK.java"
"$JAVA" -cp "$JAR" -d "$ROOT_DIR/work" "$ROOT_DIR/work/TestCJK.java" >/dev/null 2>&1 || {
  # fallback: 用 javac 編譯
  JAVA_BIN="$(dirname "$JAVA")"
  "$JAVA_BIN/javac" -cp "$JAR" -d "$ROOT_DIR/work" "$ROOT_DIR/work/TestCJK.java"
}
ABS_OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
(cd "$ROOT_DIR/work" && "$JAVA" -cp "$JAR:." TestCJK "$TEXT" "$ABS_OUT")
echo ">> 驗證完成，輸出: $ABS_OUT"
