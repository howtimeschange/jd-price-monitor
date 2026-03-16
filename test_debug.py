"""
调试：截图 + 打印页面关键元素，看看京东实际渲染了什么
"""
import asyncio
from playwright.async_api import async_playwright

TEST_SKU_ID = "100012043978"

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
            locale="zh-CN",
            viewport={"width": 1440, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        page = await context.new_page()
        url = f"https://item.jd.com/{TEST_SKU_ID}.html"
        print(f"加载：{url}")

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # 截图
        await page.screenshot(path="/tmp/jd_debug.png", full_page=False)
        print("截图已保存：/tmp/jd_debug.png")

        # 打印页面 title
        print(f"页面标题：{await page.title()}")

        # 打印所有包含 price 的元素文本
        price_els = await page.evaluate("""
            () => {
                const els = document.querySelectorAll('[class*="price"], [id*="price"], [class*="Price"]');
                return Array.from(els).slice(0, 20).map(el => ({
                    tag: el.tagName,
                    cls: el.className,
                    text: el.innerText.trim().slice(0, 80)
                }));
            }
        """)
        print("\n--- 价格相关元素 ---")
        for el in price_els:
            print(f"  <{el['tag']} class='{el['cls']}'> {el['text']}")

        # 检查是否被重定向或显示验证码
        current_url = page.url
        print(f"\n当前 URL：{current_url}")

        await browser.close()

asyncio.run(main())
