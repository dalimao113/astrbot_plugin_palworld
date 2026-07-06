"""输入长度限制 / 控制字符清洗（安全增强 §8）。"""
from astrbot_plugin_palworld.utils import security as s


def test_clip_truncates():
    assert s.clip("abcdef", 3) == "abc"
    assert s.clip(None, 5) == ""


def test_clip_strips_control_chars_keeps_tab_newline():
    assert s.clip("a\x00b\x07c", 10) == "abc"
    assert s.clip("hi\tok\nyes", 50) == "hi\tok\nyes"     # \t \n 保留
    assert s.clip("x\ry", 50) == "xy"                     # \r 去除


def test_clamp_args_limits_length_and_count():
    assert s.clamp_args(["x" * 300], per=200) == ["x" * 200]
    assert len(s.clamp_args(["a"] * 50, maxn=20)) == 20
    assert s.clamp_args([]) == []
    assert s.clamp_args(["a\x01b"]) == ["ab"]
