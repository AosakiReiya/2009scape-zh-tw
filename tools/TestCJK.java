import rt4.SoftwareRaster;
import rt4.CJKRenderer;

/**
 * CJK 渲染管線驗證工具。
 * 在 SoftwareRaster 上繪製中文字，輸出 PNG 並統計白色像素。
 *
 * 用法：java -cp <client-zh-tw.jar>:<此目錄> TestCJK [文字] [輸出.png]
 * 預設文字：正體中文測試
 */
public class TestCJK {
    public static void main(String[] args) throws Exception {
        String text = args.length > 0 ? args[0] : "正體中文測試";
        String outFile = args.length > 1 ? args[1] : "cjk_raster_test.png";
        int w = 800, h = 120;
        int[] pixels = new int[w * h];
        SoftwareRaster.setSize(pixels, w, h);
        for (int i = 0; i < pixels.length; i++) pixels[i] = 0xFF000000;
        int x = 10;
        for (int i = 0; i < text.length(); ) {
            int cp = text.codePointAt(i);
            x += CJKRenderer.drawGlyph(cp, x, 80);
            i += Character.charCount(cp);
        }
        java.awt.image.BufferedImage img = new java.awt.image.BufferedImage(w, h, java.awt.image.BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < h; y++)
            for (int xx = 0; xx < w; xx++) {
                int p = pixels[y * w + xx];
                img.setRGB(xx, y, p | 0xFF000000);
            }
        javax.imageio.ImageIO.write(img, "png", new java.io.File(outFile));
        System.out.println("wrote " + outFile + "; white pixel count=" + countWhite(pixels));
    }
    static int countWhite(int[] px) {
        int c = 0;
        for (int p : px) {
            int r = (p >> 16) & 0xFF, g = (p >> 8) & 0xFF, b = p & 0xFF;
            if (r > 200 && g > 200 && b > 200) c++;
        }
        return c;
    }
}
