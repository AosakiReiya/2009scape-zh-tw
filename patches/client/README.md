# client-zh-tw.patch

2009scape 用戶端（rt4-client）正體中文支援 patch。

## 上游來源

- 專案：https://gitlab.com/2009scape/rt4-client
- 分支：master
- 取得方式：`curl -L -o rt4-client.tar.gz "https://gitlab.com/2009scape/rt4-client/-/archive/master/rt4-client-master.tar.gz"`

## 內容

| 檔案 | 改動 |
|---|---|
| `client/src/main/java/rt4/JagString.java` | 新增 `char[] unicode` 分流，30+ 方法支援 Unicode（見 `docs/jagstring-utf16.md`） |
| `client/src/main/java/rt4/Font.java` | `render`/`renderOffset`/`getStringWidth`/`getGlyphWidth`/`splitParagraph` 對 `>255` 字元走 CJKRenderer（見 `docs/cjk-rendering.md`） |
| `client/src/main/java/rt4/CJKRenderer.java` | 新增：AWT 中文字元渲染器，寫入 `SoftwareRaster.pixels` |

## 套用

```bash
# 解壓上游原始碼後，在專案根目錄執行
patch -p1 < patches/client/client-zh-tw.patch
```

## 更新方式

上游改版時：

1. 重新下載上游原始碼
2. 重新套用本 patch（若有衝突手動合併）
3. 更新本 patch：在 git repo 中重新產生 `git diff`
   （見 `tools/update_from_upstream.sh`）
