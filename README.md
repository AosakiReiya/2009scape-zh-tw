# 2009scape 正體中文漢化 (Traditional Chinese Localization)

將 2009scape（RuneScape 2009 模擬器）單機版正體中文化的工具、patch 與文件。

- **上游用戶端**：[2009scape/rt4-client](https://gitlab.com/2009scape/rt4-client) (Java, AGPL-3.0)
- **上游伺服器**：[2009scape/2009scape](https://gitlab.com/2009scape/2009scape) (Kotlin, AGPL-3.0)
- **授權**：AGPL-3.0（與上游一致）

## 這是什麼

本專案以 **patch + 工具 + 文件** 的形式提供 2009scape 正體中文化的完整方案，
使用者自行下載上游原始碼並套用 patch 後即可建置出能顯示中文的用戶端與伺服器。

## 目錄結構

```
_dev_translate/
├── docs/          # 技術文件與翻譯指南
├── patches/       # 對上游原始碼的 patch（可重現）
├── tools/         # 萃取、翻譯、建置、驗證腳本
└── translations/  # 翻譯表與術語表
```

## 快速開始

```bash
# 1. 建置改造後的用戶端（自動下載上游原始碼 + 套用 patch + gradle build）
./tools/build_client.sh

# 2. 驗證 CJK 渲染管線
./tools/verify_cjk.sh

# 3. 萃取伺服器字串建立翻譯表骨架
./tools/extract_strings.py
```

詳細步驟見 [docs/translation-guide.md](docs/translation-guide.md)。

## 漢化範圍與內容來源

**重要架構事實**：2009scape 的遊戲內容來自三個不同來源，漢化需對應處理：

| 內容 | 來源 | 漢化方式 |
|---|---|---|
| 道具/NPC/物件名稱、examine | 本地 cache（obj.dat/npc.dat） | 改 cache 或伺服器 config 覆蓋 |
| NPC 對話、系統訊息 | 伺服器即時傳輸 | 伺服器端攔截器 + 翻譯表 |
| 介面固定文字、右鍵選單 | 用戶端程式碼（LocalizedText） | 改用戶端程式碼 |
| 介面動態文字 | 伺服器 IF_SETTEXT 封包 | 伺服器端翻譯 |

詳細架構分析見 [docs/architecture.md](docs/architecture.md)。

## 技術重點

- **JagString 升級 UTF-16**：用戶端字串層原為 ISO-8859-1 `byte[]`（`charAt` 僅 0-255），
  中文字元在結構上無法承載。透過新增並行 `char[] unicode` 欄位分流，73 個依賴類別相容。
  → [docs/jagstring-utf16.md](docs/jagstring-utf16.md)
- **CJK 渲染**：新增 `CJKRenderer`，用 AWT 將中文字元繪製進 `SoftwareRaster.pixels`。
  → [docs/cjk-rendering.md](docs/cjk-rendering.md)
- **協定 UTF-8**：伺服器以 UTF-8 傳輸字串，用戶端讀寫改為 UTF-8 感知。
  → [docs/protocol-utf8.md](docs/protocol-utf8.md)

## 狀態

- [x] Phase 1：可行性驗證（用戶端已能顯示中文，登入畫面實測成功）
- [ ] Phase 2：JSON 資料翻譯（道具/NPC/商店）
- [ ] Phase 3：伺服器端攔截器 + 翻譯萃取
- [ ] Phase 4：用戶端 UI 字串注入
- [ ] Phase 5：包裝與維護
