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


def test_tree_boss_position_not_flipped():
    """回归:v1.26 曾把世界树变换 X 轴翻转,导致 tree boss 上下颠倒。
    红菇娘世界坐标必须落在 (36%,32%) 一带(游戏实测),而非翻转后的 68%。"""
    o = _plugin()
    if not o._tree_mu:
        return
    mid, left, top = o._classify_map(458095, -694560)   # 红菇娘(MushroomLady)
    assert mid == "tree"
    assert round(left) == 36 and round(top) == 32, f"tree 位置翻转了: {left},{top}"


def test_worldtree_bosses_in_spawns():
    """回归:v1.26 regen 曾把 3 个世界树 boss 从 boss_spawns 删掉,导致栖息/boss 查不到。"""
    import json
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bs = json.load(open(os.path.join(root, "data", "boss_spawns.json"), encoding="utf-8"))
    tree = [k for k, v in bs.items() if v.get("region") == "tree"]
    assert {"MushroomLady", "KabukiMan", "DomeArmorDragon"} <= set(tree)


def test_habitat_worldtree_boss_uses_tree_map():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    o._map_mu = o._map_mv = None  # 不需要主图变换(世界树 boss 无主图刷新点)
    p = o._find_pal("红菇娘")
    d = o._habitat_data(p)
    assert d["map_label"] == "世界树" and d["mapimg"].endswith("TREE")
    assert d["boss_points"]   # 有 boss 位置点
