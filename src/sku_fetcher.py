"""
SKU 列表抓取模块
从京东店铺商品列表页爬取所有 SKU ID 和吊牌价（original_price）
接口：https://search.jd.com/search?keyword=&enc=utf-8&shopId=XXXX&page=1
"""
import asyncio
import random
import logging
import re
import json
from typing import List, Dict

from playwright.async_api import async_playwright, Page

from .config import load_config
from .cookie_utils import load_cookies

logger = logging.getLogger(__name__)


async def _scroll_to_bottom(page: Page):
    """缓慢滚动到底部，触发懒加载"""
    prev_height = 0
    for _ in range(20):
        height = await page.evaluate("document.body.scrollHeight")
        if height == prev_height:
            break
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.8)
        prev_height = height


async def fetch_sku_list() -> List[Dict]:
    """
    返回列表，每项：
      {
        "sku_id": "100012043978",
        "name": "ASICS亚瑟士跑步鞋...",
        "original_price": 999.0,   # 吊牌价/划线价，可能为 None
        "product_url": "https://item.jd.com/100012043978.html"
      }
    """
    cfg = load_config()
    shop_id = cfg["shop"]["shop_id"]
    delay_min = cfg["monitor"]["delay_min_seconds"]
    delay_max = cfg["monitor"]["delay_max_seconds"]

    skus: Dict[str, Dict] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
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
        # 注入反检测脚本
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        cookies = load_cookies()
        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        page_no = 1

        while True:
            url = (
                f"https://search.jd.com/search?enc=utf-8"
                f"&shopId={shop_id}&page={page_no}&s=1&click=0"
            )
            logger.info(f"抓取商品列表第 {page_no} 页：{url}")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(delay_min, delay_max))
                await _scroll_to_bottom(page)
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"页面加载失败 page={page_no}: {e}")
                break

            # 解析商品卡片
            items = await page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('.gl-item, li[data-sku]');
                    return Array.from(cards).map(el => {
                        const skuId = el.getAttribute('data-sku') || el.getAttribute('sku-id') || '';
                        const nameEl = el.querySelector('.p-name a em, .p-name a');
                        const name = nameEl ? nameEl.innerText.trim() : '';
                        // 吊牌价（划线价）
                        const opEl = el.querySelector('.p-price-op, .p-op-price, del');
                        const opText = opEl ? opEl.innerText.replace(/[^0-9.]/g, '') : '';
                        // 当前展示价
                        const priceEl = el.querySelector('.p-price strong i, .p-price i');
                        const priceText = priceEl ? priceEl.innerText.replace(/[^0-9.]/g, '') : '';
                        return { skuId, name, opText, priceText };
                    });
                }
            """)

            new_count = 0
            for item in items:
                sku_id = item.get("skuId", "").strip()
                if not sku_id:
                    continue
                if sku_id in skus:
                    continue
                original_price = None
                try:
                    if item.get("opText"):
                        original_price = float(item["opText"])
                except ValueError:
                    pass
                skus[sku_id] = {
                    "sku_id": sku_id,
                    "name": item.get("name", ""),
                    "original_price": original_price,
                    "product_url": f"https://item.jd.com/{sku_id}.html",
                }
                new_count += 1

            logger.info(f"第 {page_no} 页新增 {new_count} 个 SKU，累计 {len(skus)} 个")

            if new_count == 0:
                logger.info("没有新 SKU，已到最后一页")
                break

            # 检查是否有下一页
            has_next = await page.evaluate("""
                () => {
                    const next = document.querySelector('.pn-next, a.fp-next');
                    return next && !next.classList.contains('disabled');
                }
            """)
            if not has_next:
                break

            page_no += 1
            await asyncio.sleep(random.uniform(delay_min + 0.5, delay_max + 1))

        await browser.close()

    result = list(skus.values())
    logger.info(f"共抓取 {len(result)} 个 SKU")
    return result
