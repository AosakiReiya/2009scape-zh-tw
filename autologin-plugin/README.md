# AutoLogin 測試外掛

自動登入測試外掛（僅開發測試用，不入任何 fork repo）。

## 用途

端到端測試時，讓用戶端自動登入 aosaki 帳號（伺服器使用 `DevelopmentAuthenticator`，免密碼）。

## 編譯

```bash
# 用改造後 client jar（含 rt4.LoginManager 等）
javac -cp <client-zh-tw.jar> -d AutoLogin AutoLogin/plugin.java

# 產出 AutoLogin/plugin.class（package 目錄需放回 AutoLogin/）
# 需有：plugin.class + plugin.properties 平放
```

## 安裝

```bash
mkdir -p <game>/singleplayer/game/plugins/AutoLogin/
cp AutoLogin/plugin.class AutoLogin/plugin.properties <game>/singleplayer/game/plugins/AutoLogin/
```

## 機制

- `ComponentDraw` 偵測登入畫面文字「Please Log In」
- 呼叫 `LoginManager.method3896(JagString.parse("aosaki"), JagString.parse("test"), 0)` 自動送出登入
- 伺服器端 `DevelopmentAuthenticator.checkLogin` 不檢查密碼 → 登入成功

## 移除

測試完後刪除 `<game>/singleplayer/game/plugins/AutoLogin/` 目錄即可。
