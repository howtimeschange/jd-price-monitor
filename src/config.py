import yaml
import os

_cfg = None

def load_config(path: str = None) -> dict:
    global _cfg
    if _cfg is not None:
        return _cfg
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
    return _cfg
