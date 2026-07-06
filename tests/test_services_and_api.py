"""存档服务缓存/负缓存/锁 + docker/REST 封装（需 astrbot/aiohttp stub）。"""
import asyncio
import os
import struct

from astrbot_plugin_palworld.api import docker_api, palworld_api
from astrbot_plugin_palworld.services.save_service import SaveService


class FakeP:
    def __init__(self):
        self.config = {"save_cache_ttl": 120, "docker_sock": "/", "force_save_min_interval": 15,
                       "save_neg_ttl": 45}
        self.pulls = 0
        self.fail = False

    async def _resolve_container(self, s):
        return "c"

    async def _resolve_save_dir(self, s, c):
        return "/save"

    async def _api_post(self, p, pl):
        return (True, "")

    async def _pull_save_files(self, s, c, d):
        self.pulls += 1
        return None

    def _parse_save_dir(self, tmp):
        if self.fail:
            raise RuntimeError("boom")
        return {"profiles": {"x": 1}, "guilds": []}


def test_cache_hit(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    p = FakeP()
    s = SaveService(p)
    asyncio.run(s.fetch_save_data())
    asyncio.run(s.fetch_save_data())
    assert p.pulls == 1


def test_invalidate(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    p = FakeP()
    s = SaveService(p)
    asyncio.run(s.fetch_save_data())
    s.invalidate()
    asyncio.run(s.fetch_save_data())
    assert p.pulls == 2


def test_negative_cache(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    p = FakeP()
    p.fail = True
    s = SaveService(p)
    assert asyncio.run(s.fetch_save_data()) is None
    n = p.pulls
    assert asyncio.run(s.fetch_save_data()) is None
    assert p.pulls == n   # 负缓存窗口内不再拉取


def test_lock_dedup(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    p = FakeP()
    s = SaveService(p)

    async def slow(*a):
        p.pulls += 1
        await asyncio.sleep(0.03)
        return None
    p._pull_save_files = slow

    async def go():
        await asyncio.gather(*[s.fetch_save_data() for _ in range(5)])
    asyncio.run(go())
    assert p.pulls == 1


def test_missing_sock_returns_none(monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    p = FakeP()
    assert asyncio.run(SaveService(p).fetch_save_data()) is None
    assert p.pulls == 0


def test_max_age_shortens_cache_for_personal_query(monkeypatch):
    """个人查询(max_age 小)绕过长缓存拿最新；榜单(max_age=None)沿用长缓存。"""
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    p = FakeP()
    p.config["save_cache_ttl"] = 120
    s = SaveService(p)
    asyncio.run(s.fetch_save_data())            # 首拉，pulls=1
    # 模拟 20 秒前查过（把缓存时间戳往前推 20s）
    s._cache = (s._cache[0] - 20, s._cache[1])
    # 榜单：max_age=None → ttl=120，20<120 命中缓存，不重拉
    asyncio.run(s.fetch_save_data())
    assert p.pulls == 1
    # 个人：max_age=15 → 20>15，绕过缓存重新拉最新
    asyncio.run(s.fetch_save_data(max_age=15))
    assert p.pulls == 2


def test_demux_docker_stream():
    frame = b"\x01\x00\x00\x00" + struct.pack(">I", 5) + b"hello"
    assert docker_api.demux_docker_stream(frame) == "hello"
    assert docker_api.demux_docker_stream(b"") == ""


class _Resp:
    def __init__(self, status, js=None, txt=""):
        self.status = status
        self._js = js
        self._txt = txt

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def json(self, content_type=None):
        return self._js

    async def text(self):
        return self._txt


class _Session:
    def __init__(self, resp):
        self.resp = resp

    def get(self, url, **k):
        return self.resp

    def post(self, url, **k):
        return self.resp


def test_api_get_ok_and_error():
    ok, data, st = asyncio.run(palworld_api.api_get(_Session(_Resp(200, {"a": 1})), "http://b", None, 5, "/p"))
    assert ok and data == {"a": 1} and st == 200
    ok, data, st = asyncio.run(palworld_api.api_get(_Session(_Resp(401)), "http://b", None, 5, "/p"))
    assert (not ok) and st == 401


def test_api_post_ok_and_error():
    ok, err = asyncio.run(palworld_api.api_post(_Session(_Resp(204)), "http://b", None, 5, "/p", {}))
    assert ok and err == ""
    ok, err = asyncio.run(palworld_api.api_post(_Session(_Resp(500, txt="boom")), "http://b", None, 5, "/p"))
    assert (not ok) and "500" in err
