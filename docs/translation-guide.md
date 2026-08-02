# 翻譯作業指南

## 翻譯範圍與來源

依 [architecture.md](architecture.md)，內容分三來源：

1. **cache**（道具/NPC/物件名稱、examine）→ 需改 cache 或伺服器 config
2. **伺服器**（對話、系統訊息、介面動態文字）→ 攔截器 + 翻譯表
3. **用戶端**（固定 UI 字串）→ 改程式碼

## 作業流程

### 1. 萃取字串（tools/extract_strings.py）

掃描伺服器 Kotlin 原始碼與 config JSON，輸出翻譯表骨架：

```bash
./tools/extract_strings.py \
  --server-src ../2009scape-master \
  --configs ../../singleplayer/game/data/configs \
  --out translations/zh-tw/strings.json
```

骨架格式：

```json
{
  "en": "Ho Ho Ho!",
  "zh-tw": "",
  "source": "content/.../SantaHolidayRandomDialogue.kt",
  "status": "untranslated"
}
```

### 2. 批次翻譯（tools/translate_batch.py）

呼叫本地 LLM API（Ollama 等）批次翻譯，保留：
- 翻譯表分離（不直接改原始碼/JSON）
- 斷點續傳（已翻譯的跳過）
- 術語表強制（`translations/glossary.tsv` 中的專有名詞統一）

```bash
./tools/translate_batch.py translations/zh-tw/strings.json
```

### 3. 人工審校

LLM 翻譯需人工審校，重點：
- 專有名詞（技能、地名、NPC 名）與術語表一致
- 對話語氣符合 RuneScape 風格
- 長度考量（中文較短，UI 排版可接受輕微差異）

### 4. 匯入

- **伺服器端（對話/訊息/介面文字）**：翻譯表已由 `Translation` 攔截器
  （`2009scape-zh-tw-server` 的 `core/api/Translation.kt`）從
  `data/configs/translations_zh-tw.json` 載入。將翻譯表轉為 en→zh-tw JSON 物件：
  ```bash
  python3 - << 'EOF'
  import json
  table = json.load(open("translations/zh-tw/strings.json"))
  out = {e["en"]: e["zh-tw"] for e in table if e.get("zh-tw")}
  json.dump(out, open("<server>/Server/data/configs/translations_zh-tw.json","w",encoding="utf-8"), ensure_ascii=False, indent=2)
  EOF
  ```
- **JSON config**：`tools/translate_jsons.py` 回寫（道具/NPC/商店名）
- **cache**：需 cache 編輯工具（Phase 2 待決定方向）

### 5. 攔截器機制

伺服器端 `Translation` 攔截三個文字出口：

| 出口 | 檔案 | 說明 |
|---|---|---|
| 對話 | `DialogueInterpreter.doSubstitutions` | NPC/玩家對話文字 |
| 系統訊息 | `PacketDispatch.sendMessage` | 遊戲訊息 |
| 介面文字 | `PacketDispatch.sendString` | 介面動態文字（多詞句才翻，避免誤翻玩家名/數量） |

翻譯規則：
- 精確命中翻譯表 → 直接替換
- 含 `<col=...>` 標籤 → 剝除後查表、翻譯後還原
- `requirePhrase=true` 時僅多詞句翻譯（過濾玩家名/數字）

## 術語表

`translations/glossary.tsv` 維護專有名詞對照，供 LLM 提示與人工審校使用：

```
en	zh-tw	備註
Attack	攻擊	
Strength	力量	技能名
Lumbridge	倫布里奇	地名
```

## 品質檢查

- 未翻譯條目比例
- 術語表違反數
- 遊戲內實測：登入、對話、道具 hover、商店
