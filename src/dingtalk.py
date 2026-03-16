"""
钉钉机器人告警模块
支持普通 Webhook 和加签（HMAC-SHA256）两种模式
"""
import time
import hmac
import hashlib
import base64
import urllib.parse
import json
import logging
from typing import List, Dict, Optional
import urllib.request

from .config import load_config

logger = logging.getLogger(__name__)


def _sign(secret: str, timestamp: int) -> str:
    """生成钉钉加签字符串"""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code))


def _build_url() -> str:
    cfg = load_config()
    webhook = cfg["dingtalk"]["webhook_url"]
    secret = cfg["dingtalk"].get("secret", "")
    if secret:
        ts = int(time.time() * 1000)
        sign = _sign(secret, ts)
        return f"{webhook}&timestamp={ts}&sign={sign}"
    return webhook


def send_alert(violated: List[Dict]) -> bool:
    """
    发送破价告警到钉钉
    violated: 破价 SKU 列表，每项包含 sku_id / name / current_price / original_price / ratio
    """
    if not violated:
        return True

    cfg = load_config()
    shop_name = cfg["shop"]["shop_name"]
    threshold = cfg["monitor"]["price_ratio_threshold"]
    at_mobiles = cfg["dingtalk"].get("at_mobiles", [])
    at_all = cfg["dingtalk"].get("at_all", False)

    # 构建消息正文（Markdown）
    header = (
        f"## ⚠️ 破价预警 | {shop_name}\n\n"
        f"> 监控阈值：吊牌价 **{int(threshold * 100)}折**\n"
        f"> 本次发现 **{len(violated)}** 个 SKU 疑似破价\n\n"
        "---\n\n"
    )

    rows = []
    for item in violated:
        ratio_pct = f"{item['ratio'] * 100:.1f}%" if item.get("ratio") else "N/A"
        op = f"¥{item['original_price']:.2f}" if item.get("original_price") else "未知"
        cur = f"¥{item['current_price']:.2f}" if item.get("current_price") else "未知"
        rows.append(
            f"**{item['name'][:30]}**\n"
            f"- SKU: `{item['sku_id']}`\n"
            f"- 吊牌价: {op} → 前台价: **{cur}** ({ratio_pct})\n"
            f"- [商品链接]({item['product_url']})\n"
        )

    # 钉钉单条消息有字符限制，超过 20 条分批发送
    batch_size = 15
    batches = [rows[i: i + batch_size] for i in range(0, len(rows), batch_size)]

    url = _build_url()
    success = True
    for idx, batch in enumerate(batches, 1):
        title = f"破价预警 ({idx}/{len(batches)})" if len(batches) > 1 else "破价预警"
        body_text = header + "\n".join(batch)

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": body_text,
            },
            "at": {
                "atMobiles": at_mobiles,
                "isAtAll": at_all,
            },
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if result.get("errcode") != 0:
                    logger.error(f"钉钉发送失败: {result}")
                    success = False
                else:
                    logger.info(f"钉钉告警发送成功 (batch {idx})")
        except Exception as e:
            logger.error(f"钉钉请求异常: {e}")
            success = False

    return success


def send_heartbeat(total: int, violated_count: int, elapsed: float) -> bool:
    """可选：每次扫描结束发一条摘要（正常时也发，便于确认脚本在运行）"""
    cfg = load_config()
    shop_name = cfg["shop"]["shop_name"]
    webhook = cfg["dingtalk"]["webhook_url"]
    if not webhook or "YOUR_TOKEN" in webhook:
        return True

    status = "✅ 一切正常" if violated_count == 0 else f"⚠️ 发现 {violated_count} 个破价"
    text = (
        f"**{shop_name} 价格巡检完成**\n\n"
        f"- 状态：{status}\n"
        f"- 扫描 SKU：{total} 个\n"
        f"- 耗时：{elapsed:.1f} 秒\n"
    )

    payload = {
        "msgtype": "markdown",
        "markdown": {"title": "价格巡检摘要", "text": text},
        "at": {"isAtAll": False},
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _build_url(),
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("errcode") == 0
    except Exception as e:
        logger.warning(f"心跳发送失败: {e}")
        return False
