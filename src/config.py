import yaml
import os

_cfg = None
_cfg_path = None


def get_config_path() -> str:
    global _cfg_path
    if _cfg_path is None:
        _cfg_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        )
    return _cfg_path


def load_config(path: str = None) -> dict:
    global _cfg
    if _cfg is not None:
        return _cfg
    if path is None:
        path = get_config_path()
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
    return _cfg


def save_config(cfg: dict, path: str = None) -> None:
    """将配置写回 yaml 文件，并刷新缓存"""
    global _cfg
    if path is None:
        path = get_config_path()
    with open(os.path.abspath(path), "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    _cfg = cfg


def reload_config() -> dict:
    """强制重新从磁盘读取配置"""
    global _cfg
    _cfg = None
    return load_config()
