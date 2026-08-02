# 內容來源架構分析

本文記錄 2009scape 遊戲內容的實際來源，這是決定漢化策略的關鍵。

## 結論

**不是所有內容都來自伺服器。** 2009scape 的內容分佈在三個來源：

1. **本地 cache**（用戶端啟動時載入）— 佔最大宗的「靜態定義」
2. **伺服器即時傳輸**（網路封包）— 動態內容
3. **用戶端程式碼**（寫死）— 固定 UI 字串

## 1. 本地 cache（`main_file_cache.dat2`）

用戶端在 `client.java` 啟動時，透過 JS5 archives 從本地 cache 載入：

| Archive | 內容 | 載入位置 |
|---|---|---|
| 19 | 道具定義 `obj.dat` | `ObjTypeList.init` |
| 7 / 18 | NPC 定義 `npc.dat` | `NpcTypeList.init` |
| 16 / 7 | 物件定義 `loc.dat` | `LocTypeList.init` |
| 3 | 介面定義 | `InterfaceList.init` |
| 13 | 字型 | `Fonts.load` |
| 8 | 貼圖/標題/Logo | `TitleScreen.load` 等 |
| 1, 20, 0 | 動畫/序列 | `SeqTypeList.init` |

**關鍵**：道具/NPC/物件的**名稱與 examine 存在 cache 的定義檔裡**。
用戶端 `ObjType.get(id)` 直接從 `archive.fetchFile()` 讀取定義（`ObjTypeList.java:41`），
`name` 欄位由 `decode()` 的 `opcode 2` 從 cache 解析（`ObjType.java:259`）。

伺服器的 `OBJ_ADD` 封包只傳道具 **id**（`Protocol.java:257`），
用戶端用 id 查自己的 cache。**名稱不會透過網路傳輸。**

## 2. 伺服器即時傳輸（網路封包）

| 封包 | 內容 |
|---|---|
| `MESSAGE_GAME` / `MESSAGE_PRIVATE` | NPC 對話、系統訊息、公告 |
| `IF_SETTEXT2` / `IF_SETTEXT3` | 介面動態文字（對話框、商店、任務進度） |
| `OBJ_ADD` / `OBJ_REVEAL` / `OBJ_COUNT` | 世界物件放置 |
| `NPC_INFO` / `LOC_ADD` / `LOC_ANIM` | 世界實體動作 |
| `UPDATE_STAT` | 技能經驗 |

伺服器端字串編碼：`ByteBufferUtils.putString` 使用 **UTF-8**
（`core/cache/misc/buffer/ByteBufferUtils.kt`）。

## 3. 用戶端程式碼（寫死）

- `LocalizedText`：右鍵選單「攻擊/拿取/丟棄」、登入畫面「Loading」等固定字串
- 各類 `*Type.java` 中的內建選項（`LocalizedText.TAKE` 等）

## 漢化對照表

| 內容 | 來源 | 漢化方式 | 對應 Phase |
|---|---|---|---|
| 道具名稱、examine | cache `obj.dat` | 改 cache 或伺服器 `item_configs.json` 覆蓋 | Phase 2 |
| NPC 名稱、examine | cache `npc.dat` | 改 cache 或伺服器 `npc_configs.json` 覆蓋 | Phase 2 |
| 商店標題 | 伺服器 `shops.json` | 改 JSON | Phase 2 |
| NPC 對話 | 伺服器 Kotlin bytecode | 伺服器端攔截器 + 翻譯表 | Phase 3 |
| 系統訊息 | 伺服器 Kotlin bytecode | 伺服器端攔截器 + 翻譯表 | Phase 3 |
| 介面動態文字 | 伺服器 `IF_SETTEXT` | 伺服器端翻譯 | Phase 3 |
| 介面固定文字 | 用戶端 `LocalizedText` | 改用戶端程式碼 | Phase 4 |
| 聊天輸入 | 用戶端協定 | 用戶端輸入處理（後續） | 後續 |

## 對漢化工作的影響

1. **光改 JSON 不夠**：道具/NPC 名稱主要存在 cache。漢化需決定
   - 改 cache 檔案（obj.dat/npc.dat 直接換中文），或
   - 伺服器 config 覆蓋（`item_configs.json` 有 name/examine 欄位），
   - 兩者並用（cache 為主、config 補漏）
2. **伺服器端翻譯是關鍵**：對話與動態訊息都從伺服器來，攔截器是主要途徑。
3. **用戶端字串層需升級**：`JagString` 原為 ISO-8859-1 `byte[]`，無法承載中文
   （見 [jagstring-utf16.md](jagstring-utf16.md)）。
