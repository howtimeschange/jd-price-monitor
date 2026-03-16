"""
单 SKU 价格抓取模块
通过 Playwright 加载商品详情页，等待价格 JS 渲染后读取前台展示价
"""
import asyncio
import random
import logging
from typing import Optional, Dict, List

from playwright.async_api import async_playwright, Browser, BrowserContext

from .config import load_config
from .cookie_utils import load_cookies

logger = logging.getLogger(__name__)


async def _fetch_single_price(context: BrowserContext, sku: Dict, cfg: dict) -> Dict:
    """
    抓取单个 SKU 的前台价格
    返回原 sku dict，追加 current_price 字段（失败则为 None）
    """
    timeout = cfg["monitor"]["page_timeout_seconds"] * 1000
    delay_min = cfg["monitor"]["delay_min_seconds"]
    delay_max = cfg["monitor"]["delay_max_seconds"]
    sku_id = sku["sku_id"]
    url = sku["product_url"]

    page = await context.new_page()
    current_price = None
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        # 等待价格元素出现（京东价格通过 JS 异步填充）
        price_selector = f".J-p-{sku_id}"
        try:
            await page.wait_for_selector(price_selector, timeout=10000)
            price_text = await page.inner_text(price_selector)
            price_text = price_text.replace("￥", "").replace(",", "").strip()
            current_price = float(price_text)
        except Exception:
            # fallback：尝试通用价格选择器
            try:
                price_text = await page.inner_text(".p-price strong i", timeout=5000)
                price_text = price_text.replace(",", "").strip()
                current_price = float(price_text)
            except Exception as e2:
                logger.warning(f"SKU {sku_id} 价格读取失败: {e2}")

        await asyncio.sleep(random.uniform(delay_min, delay_max))
    except Exception as e:
        logger.warning(f"SKU {sku_id} 页面加载失败: {e}")
    finally:
        await page.close()

    return {**sku, "current_price": current_price}


async def fetch_prices(sku_list: List[Dict]) -> List[Dict]:
    """
    并发抓取所有 SKU 的前台价格，返回追加了 current_price 的列表
    """
    cfg = load_config()
    concurrency = cfg["monitor"]["concurrency"]

    results = []
    semaphore = asyncio.Semaphore(concurrency)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )
        context: BrowserContext = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        cookies = load_cookies()
        if cookies:
            await context.add_cookies(cookies)

        async def _worker(sku):
            async with semaphore:
                return await _fetch_single_price(context, sku, cfg)

        tasks = [_worker(sku) for sku in sku_list]
        total = len(tasks)
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            result = await coro
            results.append(result)
            if i % 20 == 0 or i == total:
                logger.info(f"价格抓取进度: {i}/{total}")

        await browser.close()

    return results
