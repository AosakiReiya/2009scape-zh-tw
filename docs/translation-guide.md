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

- 伺服器端：翻譯表掛載到攔截器（Phase 3，待實作）
- JSON config：`tools/translate_jsons.py` 回寫
- cache：需 cache 編輯工具（Phase 2 待決定方向）

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
