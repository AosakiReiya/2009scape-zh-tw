# 2009scape 正體中文漢化 (2009scape-zh-tw)

將 2009scape（RuneScape 2009 模擬器）單機版正體中文化的工具、翻譯表與文件。

## 專案架構（三個 repo）

漢化以 fork 形式維護，本 repo 為「門戶」，串接兩個 fork：

```
GitHub / GitLab
├── rt4-client-zh-tw          ← 官方 GitLab 2009scape/rt4-client 的 fork
│   └── zh-tw 分支：JagString UTF-16 + CJKRenderer + Font 改造（用戶端）
├── 2009scape-zh-tw-server    ← 官方 GitLab 2009scape/2009scape 的 fork
│   └── zh-tw 分支：Translation 攔截器（伺服器）
└── 2009scape-zh-tw           ← 本 repo：翻譯表、工具、文件（門戶）
```

| repo | 基底 | 內容 |
|---|---|---|
| `rt4-client-zh-tw` | 官方 GitLab `2009scape/rt4-client` master | 用戶端原始碼 + zh-tw 改造 |
| `2009scape-zh-tw-server` | 官方 GitLab `2009scape/2009scape` master | 伺服器原始碼 + zh-tw 攔截器 |
| `2009scape-zh-tw` | - | 翻譯表、術語表、萃取/建置工具、文件 |

## 本機工作區佈局

三個 repo 平級放在同一工作區資料夾（如 `2009scape-zh-tw-workspace/`），
與遊戲目錄分開：

```
2009scape-zh-tw-workspace/
├── 2009scape-zh-tw/          ← 本 repo（門戶）
├── rt4-client-zh-tw/         ← 用戶端 fork（zh-tw 分支）
└── 2009scape-zh-tw-server/   ← 伺服器 fork（zh-tw 分支）
```

工具腳本預設從 `../rt4-client-zh-tw`、`../2009scape-zh-tw-server` 建置。

## 授權

AGPL-3.0（與上游一致）。三個 repo 皆繼承上游授權。

## 翻譯內容來源

2009scape 的遊戲內容來自三個來源，漢化需對應處理：

| 內容 | 來源 | 漢化方式 |
|---|---|---|
| 道具/NPC/物件名稱、examine | 本地 cache（obj.dat/npc.dat） | 改 cache 或伺服器 config 覆蓋 |
| NPC 對話、系統訊息 | 伺服器即時傳輸 | 伺服器端攔截器 + 翻譯表 |
| 介面固定文字、右鍵選單 | 用戶端程式碼（LocalizedText） | 改用戶端程式碼 |
| 介面動態文字 | 伺服器 IF_SETTEXT 封包 | 伺服器端翻譯 |

詳細分析見 [docs/architecture.md](docs/architecture.md)。

## 快速開始

### 建置用戶端（rt4-client-zh-tw）

```bash
./tools/build_client.sh
```

產出：`work/client-zh-tw.jar`

### 建置伺服器（2009scape-zh-tw-server）

```bash
./tools/build_server.sh
```

產出：`work/server-zh-tw.jar`

### 驗證 CJK 渲染

```bash
./tools/verify_cjk.sh
```

### 翻譯流程

```bash
# 1. 萃取伺服器字串 → 翻譯表骨架
./tools/extract_strings.py --server-src <fork>/Server/src --configs <game>/data/configs --out translations/zh-tw/strings.json

# 2. LLM 批次翻譯（斷點續傳）
./tools/translate_batch.py translations/zh-tw/strings.json --glossary translations/glossary.tsv
```

## 技術重點

- **JagString UTF-16 升級**：用戶端字串層原為 ISO-8859-1 `byte[]`，中文字元在結構上無法承載。透過並行 `char[] unicode` 分流。→ [docs/jagstring-utf16.md](docs/jagstring-utf16.md)
- **CJK 渲染**：`CJKRenderer` 用 AWT 將中文字元繪入 `SoftwareRaster.pixels`。→ [docs/cjk-rendering.md](docs/cjk-rendering.md)
- **協定 UTF-8**：伺服器 UTF-8 傳輸，用戶端讀寫 UTF-8 感知。→ [docs/protocol-utf8.md](docs/protocol-utf8.md)
- **伺服器攔截器**：`Translation` 在對話/訊息/介面文字出口查翻譯表。→ [docs/translation-guide.md](docs/translation-guide.md)

## 開發流程

上游改版時，各 fork 以 git rebase 同步：

```bash
cd rt4-client-zh-tw
git fetch origin
git rebase origin/master   # 在 zh-tw 分支同步上游
```

## 狀態

- [x] Phase 1：可行性驗證（用戶端顯示中文，登入畫面實測成功）
- [x] 用戶端 fork：JagString UTF-16 + CJKRenderer + Font 改造
- [x] 伺服器 fork：Translation 攔截器（Gradle 建置成功，端到端載入翻譯表驗證通過）
- [ ] 翻譯作業進行中（萃取 40,699 條 → LLM 批次翻譯）
- [ ] 道具/NPC 名稱漢化（cache/config 途徑）
