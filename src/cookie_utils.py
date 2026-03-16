"""
Cookie 工具：从 cookies.json 加载登录态
"""
import json
import os
import logging

logger = logging.getLogger(__name__)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "..", "cookies.json")


def load_cookies() -> list:
    path = os.path.abspath(COOKIE_FILE)
    if not os.path.exists(path):
        logger.warning(f"未找到 cookie 文件：{path}，请先运行 python login.py")
        return []
    with open(path, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    logger.info(f"已加载 {len(cookies)} 条 cookie")
    return cookies
