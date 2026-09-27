# 2009scape-zh-tw

2009scape（RuneScape 2009 模擬器）正體中文漢化的工具、翻譯表與文件。

## 專案架構

漢化以 fork 形式維護。本 repo 為「門戶」，串接兩個 fork：

| repo | 基底 | 內容 | 發佈 |
|---|---|---|---|
| [rt4-client-zh-tw](https://github.com/AosakiReiya/rt4-client-zh-tw) | 官方用戶端 `zh-tw` 分支 | JagString UTF-16 + CJKRenderer + Font 改造 | [Releases](https://github.com/AosakiReiya/rt4-client-zh-tw/releases)：客戶端 jar + **一鍵離線單機包**（win/linux） |
| [2009scape-zh-tw-server](https://github.com/AosakiReiya/2009scape-zh-tw-server) | 官方伺服器 `zh-tw` 分支 | Translation 攔截器、漢化 configs | [Releases](https://github.com/AosakiReiya/2009scape-zh-tw-server/releases)：server jar + 漢化 data |
| **2009scape-zh-tw**（本 repo） | - | 翻譯表、術語表、萃取/建置工具 | 不發佈二進位檔 |

一般玩家請直接到 [rt4-client-zh-tw Releases](https://github.com/AosakiReiya/rt4-client-zh-tw/releases) 下載
`2009scape-zh-tw-singleplayer-win64.zip`（或 `linux64`）：一鍵離線單機包，內含漢化伺服器、客戶端、遊戲 cache 與 Java，
解壓後雙擊 `start-game.bat` 即玩，不用另外架伺服器或設定連線。

詞表由本地 LLM（gemma）批次翻譯、術語表約束一致性，未逐條人工審校；誤翻、漏翻、術語不一致歡迎開 issue 回報。

發佈方式：在上述兩個 fork repo 打 `v*` tag，GitHub Actions 自動編譯並建立 Release
（順序：先 server、後 client；單機包會抓取 server 的 latest release 組裝）。
基底來源為官方 <https://gitlab.com/2009scape>（rt4-client、2009scape、singleplayer/windows）。

工具腳本預設從
`../rt4-client-zh-tw`、`../2009scape-zh-tw-server` 建置。

## 功能

- 萃取伺服器字串建立翻譯表骨架（40,699 條）
- LLM 批次翻譯（斷點續傳、術語表強制）
- 建置漢化用戶端與伺服器（Gradle）
- 驗證 CJK 渲染

## 快速開始

```bash
# 建置漢化用戶端
./tools/build_client.sh            # → work/client-zh-tw.jar

# 建置漢化伺服器
./tools/build_server.sh            # → work/server-zh-tw.jar

# 驗證 CJK 渲染管線
./tools/verify_cjk.sh
```

### 翻譯流程

```bash
# 1. 萃取伺服器字串 → 翻譯表骨架
./tools/extract_strings.py \
  --server-src <fork>/Server/src \
  --configs <game>/data/configs \
  --out translations/zh-tw/strings.json

# 2. LLM 批次翻譯（斷點續傳）
./tools/translate_batch.py \
  translations/zh-tw/strings.json \
  --glossary translations/glossary.tsv
```

翻譯表回寫伺服器：見 `translations/` 目錄說明。

## 目錄

```
tools/         萃取、翻譯、建置、驗證腳本
translations/  術語表（glossary.tsv）與翻譯表範例
```

## 授權

AGPL-3.0（與上游一致）。
