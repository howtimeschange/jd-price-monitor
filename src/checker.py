"""
破价检测逻辑
"""
from typing import List, Dict, Optional
from .config import load_config


def check_violations(price_results: List[Dict]) -> List[Dict]:
    """
    对比前台价与吊牌价，返回破价 SKU 列表
    只有 original_price 和 current_price 都存在时才做判断
    """
    cfg = load_config()
    threshold = cfg["monitor"]["price_ratio_threshold"]

    violated = []
    for item in price_results:
        op = item.get("original_price")
        cp = item.get("current_price")
        if op is None or cp is None or op <= 0:
            continue
        ratio = cp / op
        if ratio < threshold:
            violated.append({**item, "ratio": ratio})

    return violated
