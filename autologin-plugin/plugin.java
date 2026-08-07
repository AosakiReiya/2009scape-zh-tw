package AutoLogin;

import plugin.Plugin;
import plugin.annotations.PluginMeta;
import plugin.api.API;
import rt4.JagString;
import rt4.LoginManager;

/**
 * 自動登入測試外掛（僅開發測試用，不入 fork repo）。
 *
 * 偵測登入畫面（component.text == "Please Log In"）後，
 * 自動填入 aosaki + 任意密碼並送出登入（DevelopmentAuthenticator 免密碼）。
 */
@PluginMeta(author="zh-tw-dev", description="Auto login for e2e test", version=1.0)
public class plugin extends Plugin {
    private boolean hasRan = false;

    public void Init() {
        hasRan = false;
    }

    @Override
    public void ComponentDraw(int componentIndex, rt4.Component component, int screenX, int screenY) {
        if (hasRan || API.IsLoggedIn()) {
            return;
        }
        if (component != null && component.text != null && "Please Log In".equals(component.text.toString())) {
            System.out.println("[AutoLogin] 偵測到登入畫面，自動登入 aosaki");
            hasRan = true;
            LoginManager.method3896(JagString.parse("aosaki"), JagString.parse("test"), 0);
        }
    }
}
