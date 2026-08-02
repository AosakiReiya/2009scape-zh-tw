#!/usr/bin/env bash
# 建置改造後的 2009scape 用戶端（rt4-client-zh-tw）
#
# 流程：
#   1. 下載上游 rt4-client 原始碼
#   2. 套用 client-zh-tw.patch
#   3. 下載 JDK 11 + Gradle 7.4.2（工具鏈，可選）
#   4. gradle build 產出 client-zh-tw.jar
#
# 用法：
#   ./build_client.sh [--no-toolchain] [--keep-src]
#
# 環境變數：
#   PROXY            HTTP 代理（如 http://127.0.0.1:7890），下載需代理時設定
#   UPSTREAM_URL     上游 tar.gz 網址（預設 GitLab rt4-client master）
#   JAVA_HOME        已安裝的 JDK 11 路徑（設了則跳過下載）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PATCH="$ROOT_DIR/patches/client/client-zh-tw.patch"

# ---- 工具鏈（本機工作目錄） ----
WORK="$(dirname "$SCRIPT_DIR")/work"
mkdir -p "$WORK"

CURL_ARGS=()
if [ -n "${PROXY:-}" ]; then
  CURL_ARGS=(-x "$PROXY")
fi

download() { # url dest
  echo ">> 下載 $2 ..."
  curl "${CURL_ARGS[@]}" -sL -o "$2" "$1"
}

# ---- 1. 上游原始碼 ----
UPSTREAM_URL="${UPSTREAM_URL:-https://gitlab.com/2009scape/rt4-client/-/archive/master/rt4-client-master.tar.gz}"
SRC_TGZ="$WORK/rt4-client-master.tar.gz"
SRC_DIR="$WORK/rt4-client-master"

if [ ! -d "$SRC_DIR" ]; then
  download "$UPSTREAM_URL" "$SRC_TGZ"
  tar xzf "$SRC_TGZ" -C "$WORK"
fi

# ---- 2. 套用 patch ----
if [ ! -f "$SRC_DIR/client/src/main/java/rt4/CJKRenderer.java" ]; then
  echo ">> 套用 client-zh-tw.patch ..."
  (cd "$SRC_DIR" && patch -p1 --forward < "$PATCH" || true)
  # 驗證
  if [ ! -f "$SRC_DIR/client/src/main/java/rt4/CJKRenderer.java" ]; then
    echo "ERROR: patch 未完整套用" >&2
    exit 1
  fi
else
  echo ">> 已套用過 patch，跳過"
fi

# ---- 3. 工具鏈 ----
KEEP_SRC=0
[ "${1:-}" = "--keep-src" ] && KEEP_SRC=1
[ "${1:-}" = "--no-toolchain" ] && [ -n "${JAVA_HOME:-}" ] && { echo ">> 使用既有 JAVA_HOME"; }

if [ -z "${JAVA_HOME:-}" ]; then
  JDK_TGZ="$WORK/jdk11.tar.gz"
  JDK_DIR="$WORK/jdk-11.0.32+9"
  if [ ! -d "$JDK_DIR" ]; then
    echo ">> 下載 Temurin JDK 11 ..."
    download "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.32%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.32_9.tar.gz" "$JDK_TGZ"
    tar xzf "$JDK_TGZ" -C "$WORK"
  fi
  export JAVA_HOME="$JDK_DIR"
fi

GRADLE="$WORK/gradle-7.4.2/bin/gradle"
if [ ! -x "$GRADLE" ]; then
  echo ">> 下載 Gradle 7.4.2 ..."
  GRADLE_ZIP="$WORK/gradle-7.4.2.zip"
  download "https://services.gradle.org/distributions/gradle-7.4.2-bin.zip" "$GRADLE_ZIP"
  python3 -c "import zipfile; zipfile.ZipFile('$GRADLE_ZIP').extractall('$WORK')"
  chmod +x "$GRADLE"
fi

# ---- 4. build ----
echo ">> gradle :client:build ..."
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$WORK/.gradle-home}"
export PATH="$JAVA_HOME/bin:$PATH"
(cd "$SRC_DIR" && "$GRADLE" :client:build -x test -x javadoc)

OUT="$ROOT_DIR/work/client-zh-tw.jar"
mkdir -p "$(dirname "$OUT")"
cp "$SRC_DIR/client/build/libs/client-1.0.0.jar" "$OUT"
echo ">> 產出: $OUT"
echo ">> 完成。"
