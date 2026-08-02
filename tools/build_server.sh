#!/usr/bin/env bash
# 建置漢化伺服器（2009scape-zh-tw-server）
#
# 從本機 fork 工作樹（work/2009scape-zh-tw-server，zh-tw 分支）或
# 指定 FORK_DIR 建置。使用 Gradle（替代 Maven，相容低資源環境）。
#
# 用法：
#   ./build_server.sh [--fork-dir <路徑>]
#
# 環境變數：
#   PROXY             HTTP 代理（如 http://127.0.0.1:7890）
#   FORK_DIR          漢化 fork 工作樹路徑（預設 work/2009scape-zh-tw-server）
#   JAVA_HOME         JDK 11 路徑（未設則自動下載）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WORK="$ROOT_DIR/work"
mkdir -p "$WORK"

CURL_ARGS=()
[ -n "${PROXY:-}" ] && CURL_ARGS=(-x "$PROXY")
download() { echo ">> 下載 $2 ..."; curl "${CURL_ARGS[@]}" -sL -o "$2" "$1"; }

# ---- 1. fork 工作樹 ----
FORK_DIR="${FORK_DIR:-$WORK/2009scape-zh-tw-server}"
if [ ! -d "$FORK_DIR/Server/src" ]; then
  echo ">> 找不到 fork 工作樹：$FORK_DIR" >&2
  echo "   請 clone 漢化 fork（2009scape-zh-tw-server）的 zh-tw 分支到該路徑，或指定 --fork-dir" >&2
  exit 1
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

# ---- 3. build（Gradle jar，含依賴打包）----
export PATH="$JAVA_HOME/bin:$PATH"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$WORK/.gradle-home}"
PROXY_ARGS=()
[ -n "${PROXY:-}" ] && PROXY_ARGS=(-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890)
echo ">> gradle jar ..."
(cd "$FORK_DIR/Server" && "$GRADLE" jar --console=plain "${PROXY_ARGS[@]}")

OUT="$WORK/server-zh-tw.jar"
JAR_PATH="$FORK_DIR/Server/build/libs/server-1.0.0.jar"
if [ -f "$JAR_PATH" ]; then
  cp "$JAR_PATH" "$OUT"
  echo ">> 產出: $OUT"
else
  echo ">> 未找到 $JAR_PATH，檢查 build/libs/" >&2
fi
