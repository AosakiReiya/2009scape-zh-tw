#!/usr/bin/env bash
# 建置漢化用戶端（rt4-client-zh-tw）
#
# 從平級 fork 工作樹（rt4-client-zh-tw，zh-tw 分支）或
# 指定 FORK_DIR 建置。若無本地工作樹，自動 clone 官方基底 + 套用 zh-tw。
#
# 用法：
#   ./build_client.sh [--fork-dir <路徑>]
#
# 環境變數：
#   PROXY             HTTP 代理（如 http://127.0.0.1:7890）
#   FORK_DIR          漢化 fork 工作樹路徑（預設 ../rt4-client-zh-tw）
#   UPSTREAM_URL      官方 GitLab rt4-client master tar.gz
#   JAVA_HOME         JDK 11 路徑（未設則自動下載）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WORK="$ROOT_DIR/work"
mkdir -p "$WORK"

# 平級 fork 工作樹（工作區根的上層）
WORKSPACE_ROOT="$(dirname "$ROOT_DIR")"
DEFAULT_FORK="$WORKSPACE_ROOT/rt4-client-zh-tw"

CURL_ARGS=()
[ -n "${PROXY:-}" ] && CURL_ARGS=(-x "$PROXY")
download() { echo ">> 下載 $2 ..."; curl "${CURL_ARGS[@]}" -sL -o "$2" "$1"; }

# ---- 1. fork 工作樹 ----
FORK_DIR="${FORK_DIR:-$DEFAULT_FORK}"
if [ ! -d "$FORK_DIR/client/src" ]; then
  echo ">> 找不到 fork 工作樹，建立 $FORK_DIR ..."
  UPSTREAM_URL="${UPSTREAM_URL:-https://gitlab.com/2009scape/rt4-client/-/archive/master/rt4-client-master.tar.gz}"
  TGZ="$WORK/rt4-client-master.tar.gz"
  download "$UPSTREAM_URL" "$TGZ"
  python3 -c "import tarfile; tarfile.open('$TGZ').extractall('$WORK')"
  rm -rf "$FORK_DIR"
  cp -r "$WORK/rt4-client-master" "$FORK_DIR"
  echo ">> 注意：需手動套用 zh-tw 改造（CJKRenderer/Font/JagString）。"
  echo "   建議直接 clone 漢化 fork 的 zh-tw 分支，而非從官方基底手動套用。"
fi

# ---- 2. 工具鏈 ----
if [ -z "${JAVA_HOME:-}" ]; then
  JDK_DIR="$WORK/jdk-11.0.32+9"
  if [ ! -d "$JDK_DIR" ]; then
    download "https://github.com/adoptium/temurin11-binaries/releases/download/jdk-11.0.32%2B9/OpenJDK11U-jdk_x64_linux_hotspot_11.0.32_9.tar.gz" "$WORK/jdk11.tar.gz"
    tar xzf "$WORK/jdk11.tar.gz" -C "$WORK"
  fi
  export JAVA_HOME="$JDK_DIR"
fi

GRADLE="$WORK/gradle-7.4.2/bin/gradle"
if [ ! -x "$GRADLE" ]; then
  download "https://services.gradle.org/distributions/gradle-7.4.2-bin.zip" "$WORK/gradle-7.4.2.zip"
  python3 -c "import zipfile; zipfile.ZipFile('$WORK/gradle-7.4.2.zip').extractall('$WORK')"
  chmod +x "$GRADLE"
fi

# ---- 3. build ----
echo ">> gradle :client:build ..."
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$WORK/.gradle-home}"
export PATH="$JAVA_HOME/bin:$PATH"
(cd "$FORK_DIR" && "$GRADLE" :client:build -x test -x javadoc)

OUT="$WORK/client-zh-tw.jar"
cp "$FORK_DIR/client/build/libs/client-1.0.0.jar" "$OUT"
echo ">> 產出: $OUT"
