"""任务数据与索引护栏(阶段C:1.0 任务重建)。

修正问题 #7:
- active 列表不含 `_Old` 废弃版。
- `next` 解析成目标任务中文名,不泄露内部 id、不出现字面 "None";无悬挂引用。
- `next_id` 若有必指向存在的任务 id。
- 中文名重名不静默覆盖:主键取确定性主体,候选全保留,可按 id 直查;精确重名查交候选列表。
"""
import astrbot_plugin_palworld.main as main


def _loaded():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_no_old_in_active():
    o = _loaded()
    assert not [m for m in o._missions if str(m.get("id", "")).endswith("_Old")], "active 列表不应含 _Old"


def test_next_resolved_no_dangling_no_none():
    o = _loaded()
    names = {m["name"] for m in o._missions}
    ids = {m["id"] for m in o._missions}
    for m in o._missions:
        nx = m.get("next")
        assert nx != "None", f"{m['id']} next 出现字面 None"
        if nx:
            assert nx in names, f"{m['id']} next={nx!r} 指向不存在的任务名(悬挂/内部id泄漏)"
        if m.get("next_id"):
            assert m["next_id"] in ids, f"{m['id']} next_id={m['next_id']} 悬挂"


def test_mission_name_index_dedup_and_id_lookup():
    o = _loaded()
    dup = {n: g for n, g in o._missions_by_name.items() if len(g) > 1}
    assert dup, "测试数据应含至少一组重名任务"
    for nm, group in dup.items():
        # 主键确定性(与 _mission_variant_rank 一致),候选不丢失
        assert o._mission_by_name[nm] is min(group, key=o._mission_variant_rank)
        assert len(o._missions_by_name[nm]) == len(group)
        # 每个变体都能按稳定 id 直查到
        for m in group:
            assert o._find_mission(m["id"]) is m
        # 精确重名 -> None(交候选列表消歧,不静默返回其一)
        assert o._find_mission(nm) is None


def test_variant_rank_prefers_main_and_non_replay():
    rank = main.PalworldPlugin._mission_variant_rank
    assert rank({"id": "A", "type": "主线", "order": 1}) < rank({"id": "B", "type": "支线"})
    assert rank({"id": "Sub_X", "type": "支线"}) < rank({"id": "Sub_X_Replay", "type": "支线"})
