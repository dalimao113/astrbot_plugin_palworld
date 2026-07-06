"""pytest 引导：注入 astrbot / aiohttp 的轻量 stub，并把插件包加入 sys.path。

宿主机(CI)一般没有 astrbot 运行时，也可能没有 aiohttp。用最小 stub 让插件的纯 Python
模块可被 import 测试；不 stub jinja2/playwright(需要时由测试 importorskip)。
插件目录名 astrbot_plugin_palworld 作为(命名空间)包被 import，包相对 import 正常工作。
"""
import logging
import pathlib
import sys
import tempfile
import types

_PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent
# 让 `import astrbot_plugin_palworld.<sub>` 可用（父目录进 sys.path）
sys.path.insert(0, str(_PLUGIN_ROOT.parent))


def _install_astrbot_stub():
    if "astrbot" in sys.modules:
        return
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    api.logger = logging.getLogger("astrbot-stub")

    class AstrBotConfig(dict):
        pass

    api.AstrBotConfig = AstrBotConfig

    event = types.ModuleType("astrbot.api.event")

    def _identity_decorator(*a, **k):
        def deco(fn):
            return fn
        return deco

    class _Filter:
        def __getattr__(self, name):
            return _identity_decorator

    event.filter = _Filter()

    class AstrMessageEvent:
        pass

    event.AstrMessageEvent = AstrMessageEvent

    star = types.ModuleType("astrbot.api.star")

    class Context:
        pass

    class Star:
        def __init__(self, context=None):
            self.context = context

    def register(*a, **k):
        def deco(cls):
            return cls
        return deco

    class StarTools:
        @staticmethod
        def get_data_dir(name):
            return pathlib.Path(tempfile.gettempdir()) / ("stub_" + name)

    star.Context = Context
    star.Star = Star
    star.register = register
    star.StarTools = StarTools

    comp = types.ModuleType("astrbot.api.message_components")
    astrbot.api = api
    sys.modules.update({
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
        "astrbot.api.message_components": comp,
    })


def _install_aiohttp_stub():
    try:
        import aiohttp  # noqa: F401
        return
    except ImportError:
        pass
    ah = types.ModuleType("aiohttp")
    for n in ("ClientSession", "BasicAuth", "ClientTimeout", "UnixConnector", "TCPConnector"):
        setattr(ah, n, type(n, (object,), {"__init__": lambda self, *a, **k: None}))

    class ClientError(Exception):
        pass

    ah.ClientError = ClientError
    sys.modules["aiohttp"] = ah


_install_astrbot_stub()
_install_aiohttp_stub()
