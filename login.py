"""
京东登录辅助脚本
运行后会打开一个真实浏览器窗口，手动扫码登录后按回车，
脚本自动保存 cookie 到 cookies.json 供监控脚本复用
"""
import asyncio
import json
from playwright.async_api import async_playwright

COOKIE_FILE = "cookies.json"

async def main():
    async with async_playwright() as pw:
        # 有头模式，方便手动扫码
        browser = await pw.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
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

        page = await context.new_page()
        print("正在打开京东登录页，请扫码登录...")
        await page.goto("https://passport.jd.com/new/login.aspx", wait_until="domcontentloaded")

        print("\n请在浏览器窗口中完成登录（扫码或账号密码）")
        print("登录成功后，回到此终端按回车键继续...")
        input()

        # 验证是否登录成功
        await page.goto("https://home.jd.com/", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        title = await page.title()
        print(f"当前页面标题：{title}")

        if "登录" in title:
            print("❌ 似乎未登录成功，请重试")
        else:
            # 保存 cookie
            cookies = await context.cookies()
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"✅ 登录成功！Cookie 已保存到 {COOKIE_FILE}（共 {len(cookies)} 条）")

        await browser.close()

asyncio.run(main())
