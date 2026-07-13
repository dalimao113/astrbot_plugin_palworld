"""在线地图多地图归类护栏(增量2:去 clamp)。

主大陆与世界树是独立坐标系。世界坐标必须按各自仿射变换归到所属地图,
**不得 clamp 到 0–100** 把世界树玩家压到主图边缘;都不落在任何地图内 -> 'unknown'。
坐标取自真实 /players 实测(live-main)与各图变换中心(tree)。
"""
import astrbot_plugin_palworld.main as main


def _plugin():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    assert o._load_map(), "地图素材应加载成功"
    return o


def test_live_main_player_on_main():
    o = _plugin()
    mid, left, top = o._classify_map(-347243, 263804)   # 实测在线玩家 青天如墨
    assert mid == "main"
    assert 0 <= left <= 100 and 0 <= top <= 100
    assert round(left) == 68 and round(top) == 48


def test_tree_coords_go_to_tree_not_clamped():
    o = _plugin()
    if not o._tree_mu:
        return   # 无世界树素材则跳过
    mid, left, top = o._classify_map(518000, -647000)   # 世界树变换中心
    assert mid == "tree", "世界树坐标必须归世界树,不能压到主图"
    assert 0 <= left <= 100 and 0 <= top <= 100


def test_out_of_bounds_is_unknown_not_edge():
    o = _plugin()
    mid, left, top = o._classify_map(5_000_000, 5_000_000)
    assert mid == "unknown", "越界坐标应标 unknown,不得 clamp 到边缘"
    assert left is None and top is None


def test_main_and_tree_ranges_dont_overlap():
    o = _plugin()
    if not o._tree_mu:
        return
    # 主图玩家不应被误判进世界树,反之亦然
    assert o._classify_map(-347243, 263804)[0] == "main"
    assert o._classify_map(518000, -647000)[0] == "tree"
