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


def test_habitat_spawn_coverage():
    """回归:旧 pal_spawns 每个刷新点只取到 1~2 只帕鲁,同坐标其余帕鲁全丢,导致图鉴查得到
    却 /帕鲁栖息 查不到。修复后从 spawner 组展开全部 Pal_1/2/3,覆盖数应远超旧版 137。"""
    import json
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sp = json.load(open(os.path.join(root, "data", "pal_spawns.json"), encoding="utf-8"))
    pals = {k for k in sp if k != "_meta"}
    assert len(pals) >= 240, f"栖息覆盖回退到 {len(pals)}(应 >=240)"
    # 这些常见早期帕鲁曾整只丢失,现必须有野外刷新点
    for dev in ("PinkCat", "ChickenPal", "NegativeOctopus", "SamuraiDog", "SweetsSheep"):
        e = sp.get(dev) or {}
        assert e.get("day") or e.get("night"), f"{dev} 缺主大陆野外刷新点"


def test_habitat_main_and_tree_wild_points():
    """主大陆野生帕鲁落主图并带生物群系统计;世界树野生帕鲁落世界树独立底图。"""
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    assert o._load_map(), "地图素材应加载成功"
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    # 主大陆:捣蛋猫(旧版整只丢失)
    d = o._habitat_data(o._find_pal("捣蛋猫"))
    assert d["mapimg"].endswith("MAIN") and d["map_label"] == ""
    assert d["points"] and d["regions"]   # 有热区点 + 生物群系占比
    # 纯世界树野生(凌角马 只在世界树刷、非头目) -> 世界树独立底图
    t = o._habitat_data(o._pal_by_dev.get("kirin_ice"))
    assert t["mapimg"].endswith("TREE") and t["map_label"] == "世界树"
    assert t["points"]


def test_habitat_boss_coords_priority_over_tree_wild():
    """回归:塔主/头目的具体坐标要显示出来。暴电熊 既是主图塔主、又在世界树野生,
    栖息应优先显示塔主坐标(主图),不被跨区世界树野生盖掉。"""
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    assert o._load_map()
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    d = o._habitat_data(o._pal_by_dev.get("elecpanda"))
    assert d["mapimg"].endswith("MAIN")
    assert any(k["label"] == "塔主" for k in d["kinds"])   # 塔主坐标已标出
    assert d["markers"]


def test_habitat_field_boss_from_authoritative_spots():
    """回归:云海鹿曾显示 2 个野外头目点(外部 boss_spawns.json 多编了 1 个刷新表里不存在的点)。
    野外头目坐标应只用权威 spawner 提取(FengyunDeeper 实际只有 1 个 FieldBoss，Lv.25)。"""
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    assert o._load_map()
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    d = o._habitat_data(o._pal_by_dev.get("fengyundeeper"))
    fboss = [m for m in d["markers"] if any(lg["label"] == "野外头目" for lg in d["legend"])]
    # 只有 1 个野外头目标记(不是 boss_spawns 的 2 个)
    assert sum(1 for _l, _t, k, _r in (o._pal_spawns.get("FengyunDeeper", {}).get("spots") or [])
               if k == "fboss") == 1
    assert d["markers"] and any(k["label"] == "野外头目" for k in d["kinds"])
    assert any("Lv.25" in lg["detail"] for lg in d["legend"] if lg["label"] == "野外头目")


def test_habitat_dungeon_boss_shows_coords_and_type():
    """回归:地牢限定帕鲁(炽巫猫=CatMage_Fire,樱花岛地牢)旧版 /帕鲁栖息 查不到。
    现应从 Dungeon/DungeonBoss placement 取坐标显示,并标注类型=地牢头目。"""
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    assert o._load_map()
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    d = o._habitat_data(o._pal_by_dev.get("catmage_fire"))
    assert not d["points"]           # 无野外热区
    assert d["markers"]              # 但有地牢坐标标记
    assert any(k["label"] == "地牢头目" for k in d["kinds"])   # 类型已标注
    assert d["mapimg"].endswith("MAIN")


def test_habitat_wild_pal_no_dungeon_noise():
    """有野外热区的常见帕鲁(捣蛋猫)不应被大量'地牢随机池'点污染 —— 地牢标记仅对
    无野生栖息的地牢限定帕鲁显示。"""
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    assert o._load_map()
    o._map_img = "data:image/jpeg;base64,MAIN"
    o._tree_map_img = "data:image/jpeg;base64,TREE"
    d = o._habitat_data(o._find_pal("捣蛋猫"))
    assert d["points"]                                   # 有野外热区
    assert not any(k["label"] in ("地牢", "地牢头目") for k in d["kinds"])
