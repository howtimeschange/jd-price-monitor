"""
快速验证：抓取单个京东商品的前台价格
用法：python test_single.py
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright

TEST_SKU_ID = "100012043978"  # 随便一个亚瑟士商品

def _load_cookies():
    path = os.path.join(os.path.dirname(__file__), "cookies.json")
    if not os.path.exists(path):
        print("⚠️  未找到 cookies.json，请先运行 python login.py")
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
        url = f"https://item.jd.com/{TEST_SKU_ID}.html"
        print(f"正在加载：{url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # 等待价格元素
        price_selector = f".J-p-{TEST_SKU_ID}"
        try:
            await page.wait_for_selector(price_selector, timeout=12000)
            price = await page.inner_text(price_selector)
            print(f"✅ 前台价格：¥{price.strip()}")
        except Exception:
            # fallback
            try:
                price = await page.inner_text(".p-price strong i", timeout=5000)
                print(f"✅ 前台价格（fallback）：¥{price.strip()}")
            except Exception as e:
                print(f"❌ 价格读取失败：{e}")

        # 顺便看看商品名
        try:
            name = await page.inner_text(".sku-name", timeout=3000)
            print(f"商品名：{name.strip()[:60]}")
        except Exception:
            pass

        await browser.close()

asyncio.run(main())
