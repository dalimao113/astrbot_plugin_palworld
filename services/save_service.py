"""存档拉取 + 缓存/负缓存/强制存盘 编排服务。

职责边界（重构第一阶段）：
- `palwork/palsave.py` 只管“解析”（纯解析 Oodle/GVAS，无缓存/业务逻辑）。
- 本服务管“拉取(经 plugin 的 docker archive)、强制存盘节流、TTL 缓存、失败负缓存、
  调用解析、组织返回结果”。
- 具体 docker/API/容器与存档目录解析仍由 plugin 方法承担（`_resolve_container` 被 12
  处复用），本服务经 plugin 引用调用；待 api/docker 层拆分后再切到 api 层，行为不变。

逻辑与原 main.py `_fetch_save_data`/`_do_fetch_save` 完全一致，仅把有状态的缓存/负缓存/
强制存盘计时从散落的 plugin 字段收敛到本服务内。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from typing import Optional

from astrbot.api import logger

from ..constants import LOG_PREFIX


class SaveService:
    def __init__(self, plugin):
        self.plugin = plugin
        self._cache: Optional[tuple] = None   # (timestamp, data) | None
        self._neg_until: float = 0.0          # 负缓存窗口结束时间
        self._lock: Optional[asyncio.Lock] = None  # 惰性创建
        self._last_forced_save: float = 0.0   # 上次成功强制存盘时间(节流)
        self._generation: int = 0             # 主动失效代次，阻止进行中的旧拉档回填缓存

    def invalidate(self):
        """使成功与失败缓存立即失效，外部状态变化后允许下一次查询立刻重试。"""
        self._generation += 1
        self._cache = None
        self._neg_until = 0.0

    async def note_successful_save(self) -> None:
        """记录外部已成功强存：失效旧结果，等写盘稳定，并避免下一次查询重复强存。"""
        self.invalidate()
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            await asyncio.sleep(1.0)
            self._last_forced_save = time.time()

    def cache_entry(self) -> Optional[tuple]:
        """返回当前缓存 (timestamp, data) 或 None，供后台预热判断是否临期。"""
        return self._cache

    async def fetch_save_data(self, force_save: bool = True,
                              max_age: Optional[int] = None) -> Optional[dict]:
        """返回 {'profiles':{playerId:档案}, 'guilds':[公会]}。失败/未挂 docker.sock 返回 None。
        加锁：多人同时触发时只让一个真正拉档强制存盘，其余等待后复用缓存。

        max_age：本次查询可接受的缓存年龄上限(秒)。个人自助查询(我/背包/队伍/箱/据点/公会)
        传较小值(≈强存节流)，让玩家游戏内刚获取的物品/帕鲁/天赋点尽快查到最新；榜单类聚合
        查询不传，沿用 save_cache_ttl(默认 120s)。刷新出的新档对所有人共享。"""
        p = self.plugin
        ttl = max(int(p.config.get("save_cache_ttl", 120)), 20)
        if max_age is not None:
            ttl = min(ttl, max(int(max_age), 0))
        now = time.time()
        if self._cache and now - self._cache[0] < ttl:
            return self._cache[1]
        # 负缓存：上次拉取/解析失败后的短窗口内直接返回 None，不再强制存盘+全量拉取，
        # 避免游戏更新后每条存档指令都触发“强存→拉档→再失败”把服务器打爆(自伤式 DoS)。
        if now < self._neg_until:
            return None
        sock = str(p.config.get("docker_sock", "/var/run/docker.sock"))
        if not os.path.exists(sock):
            return None
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            # 二次检查：等锁期间可能已有人填好缓存 / 已进入负缓存窗口
            now = time.time()
            if self._cache and now - self._cache[0] < ttl:
                return self._cache[1]
            if now < self._neg_until:
                return None
            generation = self._generation
            return await self._do_fetch(force_save, sock, now, generation)

    async def fetch_profiles(self, force_save: bool = True,
                             max_age: Optional[int] = None) -> Optional[dict]:
        d = await self.fetch_save_data(force_save, max_age)
        return d.get("profiles") if d else None

    async def fetch_guilds(self, force_save: bool = True,
                           max_age: Optional[int] = None) -> Optional[list]:
        d = await self.fetch_save_data(force_save, max_age)
        return d.get("guilds") if d else None

    async def _do_fetch(self, force_save: bool, sock: str, now: float,
                        generation: int) -> Optional[dict]:
        p = self.plugin
        container = await p._resolve_container(sock)
        save_dir = await p._resolve_save_dir(sock, container)
        # 强制存盘节流：距上次成功强存 <min_gap 秒就跳过 POST /save，直接拉当前档，
        # 避免多人高频刷存档指令时不停向服务器发强制存盘请求。
        if force_save:
            min_gap = max(int(p.config.get("force_save_min_interval", 15)), 0)
            if now - self._last_forced_save >= min_gap:
                try:
                    ok, err = await p._api_post("/v1/api/save", {})   # 先落盘，拿到最新数据
                    if ok:
                        await asyncio.sleep(1.0)             # 给服务器写盘留点时间
                        self._last_forced_save = time.time()
                    else:
                        logger.warning(f"{LOG_PREFIX} 强制存盘失败(仍尝试拉当前档): {err}")
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"{LOG_PREFIX} 强制存盘失败(仍尝试拉当前档): {e}")
        tmp = None
        try:
            tmp = await p._pull_save_files(sock, container, save_dir)
            data = await asyncio.to_thread(p._parse_save_dir, tmp)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"{LOG_PREFIX} 拉取/解析存档失败: {e}")
            data = None
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
        if generation != self._generation:
            # 拉档期间发生了重启/恢复/回档/主动存档等外部状态变化；本次结果属于旧代次，
            # 既不能回填缓存，也不能用失败结果重新建立负缓存。
            logger.debug(f"{LOG_PREFIX} 拉档结果因缓存已主动失效而丢弃")
            return None
        if data is not None:
            self._cache = (now, data)
            self._neg_until = 0   # 成功即清除负缓存窗口
        else:
            # 失败写短 TTL 负缓存，窗口内不再重复拉取/强存(默认 45s，可配)
            neg_ttl = max(int(p.config.get("save_neg_ttl", 45)), 10)
            self._neg_until = time.time() + neg_ttl
        return data
