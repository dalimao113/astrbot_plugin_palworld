"""配种数据护栏(阶段F:#10 重生成 + build id)。

- `_meta.steam_build_id` 必须是真实 build(非 "unknown"),带 source/child_count。
- 组合表:父母/子代编号有效、A+B=B+A 对称(同一子代下不出现互为镜像的重复对)、无重复组合。
- 概率不出现在数据里(配种概率游戏未公开,本表仅组合→子代映射)。
"""
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _breeding():
    with open(os.path.join(_ROOT, "data", "breeding.json"), encoding="utf-8") as f:
        return json.load(f)


def _paldex_indices():
    with open(os.path.join(_ROOT, "data", "paldex.json"), encoding="utf-8") as f:
        return {p["pal_index"] for p in json.load(f)}


def test_meta_has_real_build_id():
    meta = _breeding()["_meta"]
    assert meta["steam_build_id"] not in ("", "unknown", None), "配种 _meta 必须写真实 build id(#10)"
    assert meta["steam_build_id"].isdigit()
    assert meta.get("source") and meta.get("child_count")
    assert "未公开" in meta["source"], "须声明配种概率游戏未公开"


def test_all_indices_valid_and_no_dup():
    b = _breeding()
    valid = _paldex_indices()
    for child, pairs in b.items():
        if child == "_meta":
            continue
        assert child in valid, f"子代编号无效: {child}"
        seen = set()
        for a, bb in pairs:
            assert a in valid and bb in valid, f"父母编号无效: {a}+{bb}->{child}"
            key = frozenset([a, bb])
            assert key not in seen, f"同一子代下重复组合(含 A+B=B+A): {a}+{bb}->{child}"
            seen.add(key)


def test_child_count_matches_meta():
    b = _breeding()
    children = [k for k in b if k != "_meta"]
    assert len(children) == b["_meta"]["child_count"]


def test_breeding_graph_closed_full_coverage():
    """配种图闭合:出现为父母的帕鲁集合 == 子代集合(每只可配种帕鲁都能被配出)。
    守护未来重生成/新帕鲁:新可配种帕鲁若只当父母不当子代(或反之)会被抓到。"""
    b = _breeding()
    children = {k for k in b if k != "_meta"}
    parents = {x for k, pairs in b.items() if k != "_meta" for pair in pairs for x in pair}
    assert parents == children, f"配种图不闭合:仅父母={parents - children} 仅子代={children - parents}"
    assert len(children) == b["_meta"]["parent_count"]
