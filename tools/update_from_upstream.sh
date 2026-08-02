#!/usr/bin/env bash
# 從上游重新產生 client-zh-tw.patch
#
# 用法：
#   ./update_from_upstream.sh --upstream-src <路徑到上游 rt4-client 原始碼根目錄> \
#       --zh-src <路徑到改造後原始碼>
#
# 產出：patches/client/client-zh-tw.patch
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PATCH_OUT="$ROOT_DIR/patches/client/client-zh-tw.patch"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

UPSTREAM_SRC=""
ZH_SRC=""

while [ $# -gt 0 ]; do
  case "$1" in
    --upstream-src) UPSTREAM_SRC="$2"; shift 2;;
    --zh-src) ZH_SRC="$2"; shift 2;;
    *) echo "未知參數: $1" >&2; exit 1;;
  esac
done

if [ -z "$UPSTREAM_SRC" ] || [ -z "$ZH_SRC" ]; then
  echo "用法: $0 --upstream-src <上游> --zh-src <改造後>" >&2
  exit 1
fi

# 在 git repo 中產生 diff（保留完整路徑）
cd "$WORK"
cp -r "$UPSTREAM_SRC" src
rm -rf src/build src/.gradle
git init -q
git add -A
git -c user.email=dev@local -c user.name=dev commit -qm base

# 覆蓋為改造版
rsync -a --delete "$ZH_SRC/" src/
rm -rf src/build src/.gradle
git add -A
git -c user.email=dev@local -c user.name=dev commit -qm zh

git diff HEAD~1 HEAD > "$PATCH_OUT"
echo ">> patch 已更新: $PATCH_OUT ($(wc -l < "$PATCH_OUT") 行)"

# 驗證可套用
git checkout -q HEAD~1
if git apply --check "$PATCH_OUT"; then
  echo ">> 驗證：patch 可乾淨套用"
else
  echo ">> 警告：patch 無法乾淨套用到 base（可能上游變動）" >&2
fi
