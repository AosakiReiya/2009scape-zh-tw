# zh-tw 翻譯表

本目錄存放正體中文翻譯表。

## strings.json

由 `tools/extract_strings.py` 產生，**為生成物，不入 git**（見 .gitignore）。
格式範例見 `example.strings.json`：

```json
[
  {
    "en": "Ho Ho Ho!",
    "zh-tw": "呵呵呵！",
    "source": "content/.../SantaHolidayRandomDialogue.kt",
    "status": "translated"
  }
]
```

- `en`：原文（不可改）
- `zh-tw`：正體中文翻譯（空字串 = 未翻譯）
- `source`：來源檔案（萃取時定位用）
- `status`：`untranslated` / `translated`

## 翻譯流程

```bash
# 1. 萃取（可重跑更新骨架）
python3 ../tools/extract_strings.py \
  --server-src <2009scape-server>/Server/src \
  --configs <game>/data/configs \
  --out strings.json --dedupe

# 2. 批次翻譯（LLM，斷點續傳）
python3 ../tools/translate_batch.py strings.json --glossary ../glossary.tsv

# 3. 人工審校後，回寫 JSON config
python3 ../tools/translate_jsons.py --table strings.json \
  --configs <game>/data/configs
```

## 更新注意

- 上游伺服器改版 → 重新萃取（`--dedupe` 保留已翻譯條目）
- 翻譯表為唯一定稿來源，原始碼/JSON 皆由其產出
