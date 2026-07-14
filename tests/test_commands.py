"""命令注册表：别名不重复、handler 命名、token 一致性、handler 签名与 pass_args 匹配。"""
import inspect

from astrbot_plugin_palworld.commands import router


def test_handler_arity_matches_pass_args():
    """回归护栏:每个 handler 能被 _dispatch 用 (event[, args], *extra) 正确调用。
    防"handler 带 args 却没 pass_args"(=> 运行时 TypeError => 指令报错)这类 bug。"""
    import astrbot_plugin_palworld.main as main
    bad = []
    for s in router.COMMANDS:
        fn = getattr(main.PalworldPlugin, s.handler, None)
        assert fn is not None, f"{s.canonical}: handler {s.handler} 缺失"
        params = list(inspect.signature(fn).parameters.values())[1:]   # 去 self
        pos = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        has_var = any(p.kind == p.VAR_POSITIONAL for p in params)
        required = sum(1 for p in pos if p.default is inspect._empty)
        dispatched = 1 + (1 if s.pass_args else 0) + len(s.extra)       # event + args? + extra
        upper = 10 ** 9 if has_var else len(pos)
        if not (required <= dispatched <= upper):
            bad.append(f"{s.canonical}/{s.handler}: 必填{required} 派发{dispatched} 上限{upper}")
    assert not bad, "handler 签名与 pass_args/extra 不匹配(会导致指令报错):\n" + "\n".join(bad)


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
    # 回归护栏：改动别名时提醒同步（当前 395，含批准绑定/拒绝绑定 + 小队进度/勾选/重置 + 据点体检 + 我的战力 + 养成 + 材料路线 + 种属 + 科技树 + 牧场 + 用途 + 地图收集）
    assert len(router.COMMAND_TOKENS) == 395
