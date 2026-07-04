import pytest
from src.kimi_proxy.config.loader import get_log_watcher_config, LogWatcherConfig

def test_get_log_watcher_config_defaults_when_absent():
    config = {}
    cfg = get_log_watcher_config(config)
    assert isinstance(cfg, LogWatcherConfig)
    assert cfg.enabled is False

def test_get_log_watcher_config_loads_value():
    config = {"log_watcher": {"enabled": True}}
    cfg = get_log_watcher_config(config)
    assert cfg.enabled is True

def test_get_log_watcher_config_handles_invalid_type():
    config = {"log_watcher": "not_a_dict"}
    cfg = get_log_watcher_config(config)
    assert cfg.enabled is False
