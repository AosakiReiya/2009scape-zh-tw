# CJK 渲染

2009scape 用戶端的所有文字都由 `rt4.Font` 渲染。字型為點陣字形
（`SoftwareFont`，cache archive 13），字形表僅 **256 個 Latin 字元**。
中文字元（>255）在 `render()` 中索引 `spriteInnerWidths[local22]` 會越界。

## 設計：CJKRenderer

新增 `rt4.CJKRenderer`（`client/src/main/java/rt4/CJKRenderer.java`）：

- 用 AWT `java.awt.Font`（系統 CJK 字型，如 WenQuanYi Micro Hei / Noto Sans CJK TC）
  把中文字元繪製到小型 `BufferedImage`
- 將像素寫入 `SoftwareRaster.pixels`（int[] RGB 像素緩衝），含：
  - 剪裁（`clipLeft/Top/Right/Bottom`）
  - 半透明 alpha 混合
- 提供 `drawGlyph(codepoint, x, baselineY)` 與 `charWidth(codepoint)`

## Font 管線改造

`client/src/main/java/rt4/Font.java`：

| 方法 | 改動 |
|---|---|
| `render()` | 遇到 `local22 > 255` → `CJKRenderer.drawGlyph` 並推進 `arg1`，跳過點陣渲染 |
| `renderOffset()` | 同上（wave/shake 特效入口） |
| `getStringWidth()` | `>255` → `CJKRenderer.charWidth` |
| `getGlyphWidth()` | `>255` → `CJKRenderer.charWidth` |
| `splitParagraph()` | 寬度計算改用 `getGlyphWidth`，換行正確 |

OpenGL 模式（`GlRenderer.enabled`）下無 `SoftwareRaster` 可用，
CJK 字元以 `charWidth` 佔位（避免越界），完整支援需後續處理 GlFont 路徑。

## 字型選擇

`CJKRenderer` 靜態初始化時依序嘗試候選字型，`canDisplay('中')` 為 true 即採用：

```
WenQuanYi Micro Hei, Noto Sans CJK TC, Noto Sans TC,
Microsoft JhengHei, PingFang TC, Heiti TC, PMingLiU, AR PL UMing TW
```

找不到時 fallback 到 `Dialog`。

## 驗證

`TestCJK`（見 tools/）：在 `SoftwareRaster` 上繪製「正體中文測試」6 字，
輸出 PNG 並統計白色像素與字形區塊數。

遊戲內實測：將 `LocalizedText.GAME0_LOADING` 改為中文後，登入畫面實際顯示中文成功。
