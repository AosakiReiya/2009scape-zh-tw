# JagString UTF-16 升級

用戶端全部字串由 `rt4.JagString` 承載。原設計為 **ISO-8859-1 `byte[]`**，
`charAt()` 只回傳 0-255，中文字元（>255）在結構上無法承載。
這是比字型更底層的障礙——若不升級，任何中文字串都會在 `parse()` 時被截斷或變亂碼。

## 設計：並行 `char[] unicode` 分流

不把 `byte[] chars` 整個換掉（那會影響 73 個依賴類別），而是**新增一個並行的 `char[] unicode` 欄位**：

```java
public byte[] chars;      // 既有：Latin-1 位元組（0-255 相容）
public char[] unicode;    // 新增：UTF-16 字元（含 CJK）
public int length;        // 字元數（兩者共用語義）
```

規則：
- `unicode == null` → 純 Latin-1，走 `chars`，行為與上游完全一致
- `unicode != null` → 含 CJK，所有讀取方法改用 `unicode`
- `charAt()` 回傳真正的 Unicode code unit（0-65535），可觸發渲染層的 CJK 分支

## 改造範圍

來源：`client/src/main/java/rt4/JagString.java`（1,388 行）

### 建構/入口
| 方法 | 改動 |
|---|---|
| `parse(String)` | 偵測 `>255` 字元 → 改用 `unicode = arg0.toCharArray()` |
| `of(String)` | 同上 |
| `decodeString(byte[],...)` | 偵測 `>0x7F` → 以 UTF-8 解碼成 unicode（伺服器送 UTF-8） |
| `method2355` / `concatenate` | 任一含 unicode 時改用 StringBuilder 串接 |

### 讀取/比較
`charAt`、`strEquals`、`equalsIgnoreCase`、`method3142`、`startsWith`、
`endsWith`、`indexOf(JagString,int)`、`indexOf(int,int)`、`method3139`（compare）、
`compare`、`getHash`、`longHashCode` — 全數增加 unicode 分支。

### 字串操作
`substring`、`trim`、`split`、`replaceSlashWithSpace`、`toLowerCase`、
`toTitleCase`、`method3124`（reverse）、`method3140`（replace）—
unicode 時改用 `char[]` 或 `String` 操作。

### 序列化
`encodeString`、`method3148`、`method3156`、`toString`、`print`、
`stringWidth`、`drawString`、`method3107/3127`（URL）、`method3134`、`browserControlCall` —
unicode 時以 UTF-8 / String 輸出。

### 安全停用
`encodeMessage`、`encode37`、`method3141`（isInt）、`parseHexString` —
純英文/數字功能，unicode 時直接回傳安全預設值（避免 `chars` 為 null 時 NPE）。

## 相容性

- **外部 73 個依賴類別**：只使用公開 API（`charAt`/`length`/`substring`/`strEquals` 等），
  語義不變，無需修改。
- **唯一直接操作 `chars` 欄位的例外**：`Base37.java:32`（`local88.chars = local48`），
  產出的是 0-36 的 byte，unicode 為 null，相容。

## 驗證

```bash
# 單元模擬測試（見 tools/verify_cjk.sh 或 TestCJK）
# 確認：UTF-16 版可完整承載中文、charAt 回傳 >255 觸發 CJK 分支
```
