"""提取工具链护栏(阶段A:tools/game_data/)。

只测不依赖游戏文件的纯逻辑:compare_data 差异报告(list[dict] 与 DataTable 导出结构)、
provenance 采集在缺文件时不崩且如实标 exists=False(不臆造)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "game_data"))

import compare_data  # noqa: E402


def test_compare_list_of_dict():
    old = [{"item_id": "A", "price": 10}, {"item_id": "B"}]
    new = [{"item_id": "A", "price": 12}, {"item_id": "C"}]
    d = compare_data.diff(old, new)
    assert d["key"] == "item_id"
    assert d["added"] == ["C"] and d["removed"] == ["B"]
    assert d["changed"] == [("A", ["price"])]


def test_compare_datatable_export_structure():
    # 导出器输出形如 [{...,"Rows":{key:record}}]
    old = [{"Name": "DT", "Rows": {"R1": {"HP": 100}, "R2": {"HP": 5}}}]
    new = [{"Name": "DT", "Rows": {"R1": {"HP": 120}, "R3": {"HP": 9}}}]
    d = compare_data.diff(old, new, key="RowName")
    assert d["added"] == ["R3"] and d["removed"] == ["R2"]
    assert d["changed"] == [("R1", ["HP"])]
    assert "R3" in compare_data.report(d)


def test_compare_detect_key_falls_back():
    d = compare_data.diff([{"pal_dev_name": "X"}], [{"pal_dev_name": "X"}, {"pal_dev_name": "Y"}])
    assert d["key"] == "pal_dev_name" and d["added"] == ["Y"]


def test_provenance_missing_files_not_fabricated(monkeypatch):
    import game_env
    monkeypatch.setattr(game_env, "USMAP", "/no/such/usmap")
    monkeypatch.setattr(game_env, "PAK_DIR", "/no/such/dir")
    monkeypatch.setattr(game_env, "APPMANIFEST", "/no/such/acf")
    prov = game_env.collect_provenance()
    assert prov["usmap"]["exists"] is False
    assert prov["pak"]["exists"] is False
    assert prov["steam_build_id"] == ""   # 读不到不臆造
