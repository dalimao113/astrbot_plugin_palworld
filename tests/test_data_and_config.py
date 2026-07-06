"""数据文件、schema、配置默认值与校验的基础测试。"""
import json
import pathlib

from astrbot_plugin_palworld import config

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_all_data_json_loads():
    files = list((ROOT / "data").glob("*.json"))
    assert files, "data/ 下应有 json"
    for f in files:
        json.loads(f.read_text(encoding="utf-8"))   # 解析失败即抛


def test_schema_loads():
    json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))


def test_defaults_match_schema():
    """DEFAULTS 必须与 _conf_schema.json 的 default 逐项相等（防两边漂移）。"""
    schema = json.loads((ROOT / "_conf_schema.json").read_text(encoding="utf-8"))
    schema_defaults = {k: v.get("default") for k, v in schema.items()}
    assert config.DEFAULTS == schema_defaults


def test_validate_good_config_has_no_issues():
    good = {**config.DEFAULTS, "admin_password": "pw", "admin_qq": ["10001"]}
    assert config.validate_config(good) == []


def test_validate_flags_bad_api_base():
    issues = config.validate_config({**config.DEFAULTS, "api_base": "palworld:8212"})
    assert any(level == "错误" for level, _ in issues)


def test_validate_flags_non_numeric_qq():
    issues = config.validate_config({**config.DEFAULTS, "admin_qq": ["abc"]})
    assert any("纯数字" in msg for _, msg in issues)


def test_get_int_applies_hard_min():
    assert config.get_int({"poll_interval": 5}, "poll_interval") == 20
    assert config.get_int({"query_cooldown": 1}, "query_cooldown") == 5


def test_get_list_strips_and_drops_empty():
    assert config.get_list({"admin_qq": [" 1 ", "", 2]}, "admin_qq") == ["1", "2"]


def test_get_bool_default():
    assert config.get_bool({}, "local_render") is False
    assert config.get_bool({}, "enable_broadcast") is True
