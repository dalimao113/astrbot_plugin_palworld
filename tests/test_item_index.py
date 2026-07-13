"""物品名称索引护栏(增量D:ID 主键 + 重名不静默丢弃)。

items.json 有 150 组中文重名(武器品阶 _2.._5 + _NPC 共享一个显示名)。
- 名称主键必须确定性优先"本体"(item_id 无 _2.._9 品阶、无 _NPC 后缀),不按文件顺序取首个。
- 同名各变体不得静默丢弃:_items_by_name 保留全部,可按 item_id 直查到具体品阶。
"""
import astrbot_plugin_palworld.main as main


def _loaded():
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o._load_paldex()
    return o


def test_variant_rank_prefers_base():
    rank = main.PalworldPlugin._item_variant_rank
    assert rank({"item_id": "GatlingGun"}) < rank({"item_id": "GatlingGun_3"})
    assert rank({"item_id": "GatlingGun"}) < rank({"item_id": "GatlingGun_NPC"})
    assert rank({"item_id": "Katana"}) < rank({"item_id": "Katana_5"})


def test_name_index_picks_base_variant():
    o = _loaded()
    for cn, base in (("加特林机枪", "GatlingGun"), ("太刀", "Katana"), ("激光步枪", "LaserRifle")):
        it = o._item_by_name.get(cn)
        assert it is not None and it.get("item_id") == base, f"{cn} 应取本体 {base},实为 {it and it.get('item_id')}"


def test_variants_not_silently_dropped():
    o = _loaded()
    group = o._items_by_name.get("加特林机枪", [])
    ids = {x.get("item_id") for x in group}
    assert {"GatlingGun", "GatlingGun_2", "GatlingGun_NPC"} <= ids, "重名品阶/NPC 变体不得丢弃"
    # 变体可按 item_id 精确直查到
    assert o._item_by_id.get("GatlingGun_3", {}).get("name") == "加特林机枪"
