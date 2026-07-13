"""累计排行榜护栏(增量G:本周/今日/总榜 + 统计起点)。

- _rank_list(scope) 三口径分别读 week / day / total,过期周/日不计入。
- _rank_scope 把「今日/总榜/累计」解析成 scope 并给出标题;本周用模板默认。
- tracking_started_at:全新 state 从今天起算;历史 state(已有 totals 无起点)标 None(不臆断)。
"""
import astrbot_plugin_palworld.main as main


def _plugin(totals=None, online=None, started="2026-07-01"):
    o = main.PalworldPlugin.__new__(main.PalworldPlugin)
    o.state = {"totals": totals or {}, "online": online or {}, "tracking_started_at": started}
    return o


def _totals():
    wk = main.PalworldPlugin._week_id_of(main.datetime.now())
    today = main.datetime.now().strftime("%Y-%m-%d")
    return {
        "U1": {"name": "阿肝", "total": 100000, "week": 7000, "week_id": wk, "day": 3600, "day_id": today},
        "U2": {"name": "咸鱼", "total": 500000, "week": 200, "week_id": wk, "day": 100, "day_id": today},
        "U3": {"name": "上周的", "total": 9999, "week": 8888, "week_id": "2000-W01", "day": 0, "day_id": "2000-01-01"},
    }


def test_week_scope_excludes_stale_week():
    o = _plugin(_totals(), online={"U1": {}})
    rows = o._rank_list(10, "week")
    names = [r["name"] for r in rows]
    assert "上周的" not in names, "过期周不应计入本周榜"
    assert names[0] == "阿肝" and rows[0]["sec"] == 7000
    assert rows[0]["online"] is True and rows[1]["online"] is False


def test_today_scope_reads_day_field():
    o = _plugin(_totals())
    rows = o._rank_list(10, "today")
    assert [r["name"] for r in rows] == ["阿肝", "咸鱼"]
    assert rows[0]["sec"] == 3600


def test_total_scope_uses_cumulative():
    o = _plugin(_totals())
    rows = o._rank_list(10, "total")
    assert rows[0]["name"] == "咸鱼" and rows[0]["sec"] == 500000   # 总榜咸鱼反超
    assert [r["name"] for r in rows] == ["咸鱼", "阿肝", "上周的"]


def test_rank_scope_keywords():
    o = _plugin(started="2026-07-01")
    assert o._rank_scope([])[0] == "week"
    assert o._rank_scope(["本周"])[0] == "week"
    assert o._rank_scope(["今日"])[0] == "today"
    assert o._rank_scope(["TODAY"])[0] == "today"
    sc, title, sub = o._rank_scope(["总榜"])
    assert sc == "total" and "累计" in title and "2026-07-01" in sub


def test_total_label_when_start_unknown():
    o = _plugin(started=None)
    _sc, _t, sub = o._rank_scope(["累计"])
    assert "未记录" in sub, "历史起点未知时不得臆断日期"
