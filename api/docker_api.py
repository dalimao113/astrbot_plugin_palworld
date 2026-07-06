"""Docker Engine API 操作（经 unix docker.sock 的协议封装）。

⚠️⚠️ 安全 / 权限风险说明 ⚠️⚠️
挂载 docker.sock 进容器 ≈ 赋予该容器近乎宿主机 root 的能力。本模块的写操作都是高危：
  - container_action(stop/start/restart)：可停/启宿主上的容器
  - docker_exec：在运行容器内执行任意命令
  - run_helper：创建一次性容器，VolumesFrom 挂载主容器的卷来读写存档
这些**必须**由上层的管理员白名单(_is_admin) + 二次确认(_pending/「帕鲁 确认」)保护，
严禁向普通群友开放。本层只做 HTTP/协议封装，不做任何鉴权——鉴权在 commands 分发层。
读操作(container_stats/image_of)相对安全，但同样经 docker.sock，权限等级一致。

统一约定：每次操作用 aiohttp.UnixConnector(path=sock) 独立短连接；每个请求带显式
ClientTimeout；失败抛异常交由调用方(plugin 薄包装/service)处理。逻辑与原 main.py 一致。
"""
from __future__ import annotations

import io
import os
import tarfile
import tempfile
import time
from typing import Optional, Tuple
from urllib.parse import quote

import aiohttp

from astrbot.api import logger

from ..constants import LOG_PREFIX


def demux_docker_stream(raw: bytes) -> str:
    """Docker 多路复用流：每帧 8 字节头(类型1B+保留3B+长度4B大端)。解出纯文本。"""
    if not raw:
        return ""
    if raw[0] in (0, 1, 2):
        out = bytearray()
        i, n = 0, len(raw)
        while i + 8 <= n:
            size = int.from_bytes(raw[i + 4:i + 8], "big")
            i += 8
            out += raw[i:i + size]
            i += size
        return out.decode("utf-8", "replace")
    return raw.decode("utf-8", "replace")


async def container_stats(sock: str, container: str) -> Optional[dict]:
    """[只读] 读容器 CPU/内存。失败返回 None。调用方应先确认 docker.sock 已挂载。"""
    try:
        conn = aiohttp.UnixConnector(path=sock)
        async with aiohttp.ClientSession(connector=conn) as s:
            url = f"http://docker/containers/{container}/stats?stream=false"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return None
                d = await r.json()
        cs, pcs = d["cpu_stats"], d["precpu_stats"]
        cpu_delta = cs["cpu_usage"]["total_usage"] - pcs["cpu_usage"]["total_usage"]
        sys_delta = cs.get("system_cpu_usage", 0) - pcs.get("system_cpu_usage", 0)
        # CPU%：占整机全部核心的百分比(100%=所有核心跑满)，与 1Panel/宿主视角一致。
        # 不要再 ×核心数，否则会变成 docker stats「单核=100%」口径，多核机上数字虚高 N 倍。
        cpu = round(cpu_delta / sys_delta * 100, 1) if sys_delta > 0 else 0.0
        mem = d.get("memory_stats", {})
        usage = mem.get("usage", 0) - (mem.get("stats", {}) or {}).get("inactive_file", 0)
        limit = mem.get("limit", 0)
        mem_pct = round(usage / limit * 100, 1) if limit else 0.0
        used_mb = usage / 1048576
        mem_text = f"{used_mb / 1024:.1f}GB" if used_mb >= 1024 else f"{round(used_mb)}MB"
        return {"cpu": cpu, "cpu_bar": min(cpu, 100), "mem_text": mem_text,
                "mem_pct": mem_pct, "mem_bar": min(mem_pct, 100)}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"{LOG_PREFIX} 读取容器资源失败: {e}")
        return None


async def pull_save_files(sock: str, container: str, save_dir: str) -> str:
    """[只读] 经 docker archive API 把 Level.sav + Players/ 拉到本地临时目录，返回目录路径。

    安全：tar 解包用 filter='data'(Py3.12+)；旧版手动拒绝绝对路径/.. 穿越与 symlink/hardlink，
    防止恶意存档写出临时目录之外。"""
    tmp = tempfile.mkdtemp(prefix="palsave_")
    conn = aiohttp.UnixConnector(path=sock)
    async with aiohttp.ClientSession(connector=conn) as s:
        for sub in (f"{save_dir}/Level.sav", f"{save_dir}/Players"):
            url = f"http://docker/containers/{container}/archive?path={quote(sub)}"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    raise Exception(f"archive {sub} HTTP {r.status}")
                data = await r.read()
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                try:
                    tf.extractall(tmp, filter="data")
                except TypeError:        # Python<3.12 无 filter 参数，手动做等价的安全过滤
                    base = os.path.realpath(tmp)
                    for m in tf.getmembers():
                        # 拒绝绝对路径 / .. 穿越：解析后必须仍在 tmp 内
                        target = os.path.realpath(os.path.join(tmp, m.name))
                        if not (target == base or target.startswith(base + os.sep)):
                            continue
                        # 拒绝链接类条目(symlink/hardlink 可指向外部)
                        if m.issym() or m.islnk():
                            continue
                        tf.extract(m, tmp)
    return tmp


async def docker_exec(sock: str, container: str, cmd: list, timeout: int = 20) -> Tuple[int, str]:
    """[高危] 在运行中的容器内执行命令，返回 (exit_code, 输出)。仅限管理员+确认后调用。"""
    conn = aiohttp.UnixConnector(path=sock)
    async with aiohttp.ClientSession(connector=conn) as s:
        async with s.post(
            f"http://docker/containers/{container}/exec",
            json={"AttachStdout": True, "AttachStderr": True, "Cmd": cmd},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status != 201:
                raise Exception(f"exec create HTTP {r.status}")
            eid = (await r.json())["Id"]
        async with s.post(
            f"http://docker/exec/{eid}/start",
            json={"Detach": False, "Tty": False},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as r:
            out = demux_docker_stream(await r.read())
        # 读取失败不能默认成功：默认 -1（未知/失败），仅当成功读到 ExitCode 才采信。
        # ExitCode 为 None（进程仍在跑/缺字段）同样按失败处理，避免误报成功。
        code = -1
        try:
            async with s.get(f"http://docker/exec/{eid}/json",
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                ec = (await r.json()).get("ExitCode", None)
            code = -1 if ec is None else int(ec)
        except Exception:  # noqa: BLE001
            code = -1
        return code, out


async def container_action(sock: str, container: str, action: str, timeout: int = 90) -> None:
    """[高危] 对容器执行 stop / start / restart。仅限管理员+确认后调用。"""
    q = "?t=30" if action in ("stop", "restart") else ""
    conn = aiohttp.UnixConnector(path=sock)
    async with aiohttp.ClientSession(connector=conn) as s:
        async with s.post(
            f"http://docker/containers/{container}/{action}{q}",
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as r:
            if r.status not in (204, 304):
                raise Exception(f"{action} HTTP {r.status} {(await r.text())[:80]}")


async def image_of(sock: str, container: str) -> str:
    """[只读] 取容器所用镜像名（用于起同镜像的一次性 helper 容器）。"""
    conn = aiohttp.UnixConnector(path=sock)
    async with aiohttp.ClientSession(connector=conn) as s:
        async with s.get(f"http://docker/containers/{container}/json",
                         timeout=aiohttp.ClientTimeout(total=10)) as r:
            d = await r.json()
    return (d.get("Config", {}) or {}).get("Image") \
        or "thijsvanloef/palworld-server-docker:latest"


async def inspect_container(sock: str, container: str) -> Optional[dict]:
    """[只读] GET 容器详情 json，200 返回 dict；否则(含异常/未找到)返回 None。"""
    try:
        conn = aiohttp.UnixConnector(path=sock)
        async with aiohttp.ClientSession(connector=conn) as s:
            async with s.get(f"http://docker/containers/{container}/json",
                             timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return None
                return await r.json()
    except Exception:  # noqa: BLE001
        return None


async def list_containers(sock: str) -> list:
    """[只读] GET 全部容器列表（用于自动探测帕鲁服容器）。失败/非200 返回 []。"""
    try:
        conn = aiohttp.UnixConnector(path=sock)
        async with aiohttp.ClientSession(connector=conn) as s:
            async with s.get("http://docker/containers/json",
                             timeout=aiohttp.ClientTimeout(total=5)) as r:
                return await r.json() if r.status == 200 else []
    except Exception:  # noqa: BLE001
        return []


async def run_helper(sock: str, image: str, src_container: str,
                     cmd: list, timeout: int = 120) -> Tuple[int, str]:
    """[高危] 起一个一次性容器，共享 src_container 的卷(VolumesFrom)执行 cmd，回收后返回 (code, 输出)。
    用于在主容器停机时安全地备份/清理存档。仅限管理员+确认后调用。NetworkMode=none 无网络。"""
    conn = aiohttp.UnixConnector(path=sock)
    name = f"palworld_reset_{int(time.time())}"
    async with aiohttp.ClientSession(connector=conn) as s:
        body = {
            "Image": image, "Entrypoint": cmd, "Cmd": None,
            "HostConfig": {"VolumesFrom": [src_container],
                           "AutoRemove": False, "NetworkMode": "none"},
        }
        async with s.post(f"http://docker/containers/create?name={name}", json=body,
                          timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status not in (200, 201):
                raise Exception(f"helper create HTTP {r.status} {(await r.text())[:120]}")
            cid = (await r.json())["Id"]
        try:
            async with s.post(f"http://docker/containers/{cid}/start",
                              timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status not in (204, 304):
                    raise Exception(f"helper start HTTP {r.status} {(await r.text())[:120]}")
            async with s.post(f"http://docker/containers/{cid}/wait",
                              timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                code = (await r.json()).get("StatusCode", -1)
            out = ""
            try:
                async with s.get(f"http://docker/containers/{cid}/logs?stdout=1&stderr=1",
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
                    out = demux_docker_stream(await r.read())
            except Exception:  # noqa: BLE001
                pass
            return int(code), out
        finally:
            try:
                async with s.delete(f"http://docker/containers/{cid}?force=1",
                                    timeout=aiohttp.ClientTimeout(total=20)):
                    pass
            except Exception:  # noqa: BLE001
                pass
