"""
历史记录存储模块
每次扫描结果写入 data/YYYY-MM-DD.jsonl，每行一条 SKU 记录
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from .config import load_config

logger = logging.getLogger(__name__)


def _data_dir() -> str:
    cfg = load_config()
    base = os.path.join(os.path.dirname(__file__), "..", cfg["output"]["data_dir"])
    os.makedirs(base, exist_ok=True)
    return os.path.abspath(base)


def save_results(price_results: List[Dict], violated: List[Dict]):
    """将本次扫描结果追加写入当天的 jsonl 文件"""
    now = datetime.now()
    filename = os.path.join(_data_dir(), f"{now.strftime('%Y-%m-%d')}.jsonl")
    violated_ids = {v["sku_id"] for v in violated}

    with open(filename, "a", encoding="utf-8") as f:
        for item in price_results:
            record = {
                **item,
                "scanned_at": now.isoformat(),
                "violated": item["sku_id"] in violated_ids,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"结果已写入 {filename}，共 {len(price_results)} 条")


def cleanup_old_files():
    """删除超过 keep_days 的历史文件"""
    cfg = load_config()
    keep_days = cfg["output"]["keep_days"]
    cutoff = datetime.now() - timedelta(days=keep_days)
    data_dir = _data_dir()

    for fname in os.listdir(data_dir):
        if not fname.endswith(".jsonl"):
            continue
        try:
            file_date = datetime.strptime(fname.replace(".jsonl", ""), "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(os.path.join(data_dir, fname))
                logger.info(f"已清理过期文件: {fname}")
        except ValueError:
            pass
