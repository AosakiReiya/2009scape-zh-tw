# 協定層 UTF-8

2009scape 的網路字串傳輸原本以 byte 為單位（單字節，ISO-8859-1 語義）。
要傳遞中文，兩端必須支援多字節 UTF-8。

## 伺服器端（已原生支援）

`Server/src/main/core/cache/misc/buffer/ByteBufferUtils.kt`：

```kotlin
fun putString(s: String, buffer: ByteBuffer) {
    buffer.put(s.toByteArray(StandardCharsets.UTF_8)).put(0.toByte())
}
```

伺服器送出字串本就以 **UTF-8** 編碼。因此伺服器端只需確保送出的是中文字串即可。

## 用戶端（需改造）

`rt4.JagString`（見 [jagstring-utf16.md](jagstring-utf16.md)）：

| 方法 | 改動 |
|---|---|
| `decodeString(byte[]...)` | 偵測 `>0x7F` 位元組 → 以 UTF-8 解碼成 `unicode` |
| `encodeString(...)` | `unicode != null` 時以 UTF-8 輸出 |
| `method3148()` | 同上（輸出位元組） |

`rt4.Buffer` 的讀寫端（`gjstr`/`gjstr2`/`pjstr`）不需改動，
因為它們分別委派給 `JagString.decodeString` 與 `JagString.encodeString`，
已涵蓋 UTF-8 處理。

## 雙向流程

```
伺服器送出中文（UTF-8 bytes）
  → 用戶端 Buffer.gjstr() 讀 byte[]
  → JagString.decodeString() 偵測多字節 → UTF-8 解碼 → unicode char[]
  → Font.render() 遇 >255 字元 → CJKRenderer AWT 渲染
```
