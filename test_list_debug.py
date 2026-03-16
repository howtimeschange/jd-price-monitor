"""
调试：检查京东店铺列表页的商品卡片结构
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

URL = "https://mall.jd.com/advance_search-2863474-1000462158-1000462158-0-0-0-1-1-60.html"

def _load_cookies():
    path = os.path.join(os.path.dirname(__file__), "cookies.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        cookies = _load_cookies()
        if cookies:
            await context.add_cookies(cookies)
            print(f"已加载 {len(cookies)} 条 cookie")

        page = await context.new_page()
        print(f"加载：{URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        # 等待商品列表容器出现
        try:
            await page.wait_for_selector('.goods-list, .gl-warp, #goods-list, [class*="goodsList"], [class*="goods-list"], [id*="goods"]', timeout=15000)
        except Exception:
            pass
        await asyncio.sleep(3)

        print(f"页面标题：{await page.title()}")
        print(f"当前 URL：{page.url}")

        # 截图
        await page.screenshot(path="/tmp/jd_list_debug.png")
        print("截图：/tmp/jd_list_debug.png")

        # 探测商品卡片结构
        result = await page.evaluate("""
            () => {
                const selectors = [
                    '.gl-item', 'li[data-sku]', '.goods-list-item',
                    '.p-name', 'li[sku-id]', '.item-list li',
                    '[data-sku]', '[sku-id]', '.goods-item',
                    'ul.gl-warp li', '.search-content li'
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 2) {
                        return {
                            selector: sel,
                            count: els.length,
                            sample_html: els[0].outerHTML.slice(0, 1200)
                        };
                    }
                }
                return {
                    selector: 'none',
                    count: 0,
                    body_preview: document.body.innerHTML.slice(0, 6000)
                };
            }
        """)
        print(f"\n找到选择器：{result.get('selector')}，数量：{result.get('count')}")
        if result.get('sample_html'):
            print(f"\n第一个卡片 HTML 片段：\n{result['sample_html']}")
        if result.get('body_preview'):
            print(f"\nBody 预览：\n{result['body_preview']}")

        await browser.close()

asyncio.run(main())
