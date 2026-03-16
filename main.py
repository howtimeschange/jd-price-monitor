"""
主监控入口
支持两种运行方式：
  1. python main.py            # 立即执行一次并退出
  2. python main.py --loop     # 按 config.yaml 的 interval_minutes 循环运行
"""
import asyncio
import argparse
import logging
import os
import sys
import time
from datetime import datetime

# 将 src 加入模块路径
sys.path.insert(0, os.path.dirname(__file__))

from src.config import load_config
from src.sku_fetcher import fetch_sku_list
from src.price_fetcher import fetch_prices
from src.checker import check_violations
from src.dingtalk import send_alert, send_heartbeat
from src.storage import save_results, cleanup_old_files


def setup_logging():
    cfg = load_config()
    log_dir = os.path.join(os.path.dirname(__file__), cfg["output"]["log_dir"])
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


async def run_once():
    """执行一次完整的价格巡检"""
    logger = logging.getLogger("main")
    start = time.time()
    cfg = load_config()

    logger.info("=" * 60)
    logger.info(f"开始价格巡检 | {cfg['shop']['shop_name']}")
    logger.info("=" * 60)

    # Step 1: 抓取 SKU 列表
    logger.info("【Step 1/3】抓取店铺 SKU 列表...")
    try:
        sku_list = await fetch_sku_list()
    except Exception as e:
        logger.error(f"SKU 列表抓取失败: {e}", exc_info=True)
        return

    if not sku_list:
        logger.warning("未抓取到任何 SKU，请检查店铺 ID 或网络环境")
        return
    logger.info(f"共获取 {len(sku_list)} 个 SKU")

    # Step 2: 抓取前台价格
    logger.info("【Step 2/3】抓取前台价格...")
    try:
        price_results = await fetch_prices(sku_list)
    except Exception as e:
        logger.error(f"价格抓取失败: {e}", exc_info=True)
        return

    success_count = sum(1 for r in price_results if r.get("current_price") is not None)
    logger.info(f"价格抓取完成：{success_count}/{len(price_results)} 个成功")

    # Step 3: 破价检测 + 告警
    logger.info("【Step 3/3】破价检测...")
    violated = check_violations(price_results)
    elapsed = time.time() - start

    if violated:
        logger.warning(f"发现 {len(violated)} 个破价 SKU！")
        for v in violated:
            logger.warning(
                f"  [{v['sku_id']}] {v['name'][:30]} "
                f"吊牌价¥{v.get('original_price', 'N/A')} → "
                f"前台价¥{v.get('current_price', 'N/A')} "
                f"({v['ratio'] * 100:.1f}%)"
            )
        send_alert(violated)
    else:
        logger.info("未发现破价 SKU ✅")

    # 保存记录 & 清理
    save_results(price_results, violated)
    cleanup_old_files()

    # 可选心跳（把 send_heartbeat 调用注释掉即可关闭）
    # send_heartbeat(len(price_results), len(violated), elapsed)

    logger.info(f"巡检完成，共耗时 {elapsed:.1f} 秒")
    logger.info("=" * 60)


def main():
    setup_logging()
    logger = logging.getLogger("main")

    parser = argparse.ArgumentParser(description="京东价格监控")
    parser.add_argument(
        "--loop", action="store_true", help="循环运行（按 config.yaml 中的 interval_minutes）"
    )
    args = parser.parse_args()

    if args.loop:
        cfg = load_config()
        interval = cfg["monitor"]["interval_minutes"] * 60
        logger.info(f"循环模式启动，每 {cfg['monitor']['interval_minutes']} 分钟执行一次")
        while True:
            asyncio.run(run_once())
            logger.info(f"等待 {cfg['monitor']['interval_minutes']} 分钟后下次执行...")
            time.sleep(interval)
    else:
        asyncio.run(run_once())


if __name__ == "__main__":
    main()
