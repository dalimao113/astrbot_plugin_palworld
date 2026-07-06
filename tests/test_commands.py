"""命令注册表：别名不重复、handler 命名、token 一致性。"""
from astrbot_plugin_palworld.commands import router


def test_no_duplicate_aliases():
    # build_alias_map 遇重复别名会抛 ValueError
    router.build_alias_map(router.COMMANDS)


def test_alias_map_covers_all_tokens():
    total = sum(len(s.tokens) for s in router.COMMANDS)
    assert len(router.COMMAND_TOKENS) == total   # 无重复 => 数量相等


def test_handlers_and_tokens_wellformed():
    for s in router.COMMANDS:
        assert s.handler.startswith("_cmd_"), s.handler
        assert s.canonical
        assert all(t.strip() for t in s.tokens), s.canonical
        if s.extra:
            assert s.pass_args, f"{s.canonical} 有 extra 但未 pass_args"


def test_expected_token_count():
    # 回归护栏：改动别名时提醒同步（当前 292）
    assert len(router.COMMAND_TOKENS) == 292
