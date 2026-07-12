"""版本号一致性护栏：metadata.yaml / pyproject.toml / main.py @register /
README 徽章 / CHANGELOG 最新条目 必须相同。

防止“改了一处忘了另一处”导致的版本漂移（历史上 pyproject 曾停在 1.1.2，
README 徽章与 CHANGELOG 曾停在 1.2.2 而实际到 1.8.4）。
"""
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _metadata_version() -> str:
    txt = (ROOT / "metadata.yaml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version:\s*"([^"]+)"', txt)   # ^version: 避免误匹配 astrbot_version
    assert m, "metadata.yaml 未找到 version"
    return m.group(1)


def _pyproject_version() -> str:
    txt = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', txt)
    assert m, "pyproject.toml 未找到 version"
    return m.group(1)


def _register_version() -> str:
    """main.py 的 @register(name, author, desc, version, repo) 第 4 个参数。"""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "register":
                for a in dec.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and _SEMVER.match(a.value):
                        return a.value
    raise AssertionError("main.py 未找到 @register 的版本号")


def _readme_badge_version() -> str:
    txt = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"badge/version-(\d+\.\d+\.\d+)", txt)
    assert m, "README.md 未找到 version 徽章"
    return m.group(1)


def _changelog_latest_version() -> str:
    """CHANGELOG 里第一个(最新) ## [X.Y.Z] 条目。"""
    txt = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"(?m)^##\s*\[(\d+\.\d+\.\d+)\]", txt)
    assert m, "CHANGELOG.md 未找到版本条目"
    return m.group(1)


def test_versions_consistent():
    m, p, r = _metadata_version(), _pyproject_version(), _register_version()
    rd, cl = _readme_badge_version(), _changelog_latest_version()
    assert m == p == r == rd == cl, (
        f"版本号不一致: metadata={m} pyproject={p} @register={r} "
        f"README徽章={rd} CHANGELOG最新={cl}")


def test_version_is_semver():
    assert _SEMVER.match(_metadata_version()), "版本号应为 X.Y.Z 语义化格式"
