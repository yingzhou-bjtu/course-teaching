#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ghfast —— 不开 VPN 访问 / 加速 GitHub 的一体化工具。

设计原则
--------
1. **零第三方依赖**：只用 Python 标准库（3.8+），拷到任何机器都能跑，
   所以「打包依赖」这件事被消解掉了——没有依赖需要装。
2. **不写死镜像**：所有镜像 / IP 都只是候选，运行期真实探测（DNS-over-HTTPS
   解析 → TCP 握手 → TLS+SNI 握手 → HTTP 状态码），取当前最快且可用的。
3. **只做三件事**：修 DNS（hosts）、绕 CDN（镜像）、配工具链（git/pip）。

子命令
------
  doctor      诊断 GitHub 及各 CDN 域名的真实可用性
  hosts      多源解析 + 实测，生成/写入最优 IP 的 hosts 记录
  mirrors    探测公共 GitHub 反代镜像的实时延迟与可用性
  download   多镜像自动回退下载（release / raw / archive）
  clone      多镜像自动回退 git clone
  git        可选：url.insteadOf 让 git 全局走镜像（会破坏 push，可一键撤销）
  pip        配置 PyPI 国内镜像
  install    安装自身到 ~/.local/bin
  selftest   离线自检

典型用法
--------
  python3 ghfast.py doctor                 # 先看看被卡在哪一层
  python3 ghfast.py hosts                  # 只打印，不改系统
  sudo python3 ghfast.py hosts --apply     # 写 /etc/hosts（自动备份、可还原）
  python3 ghfast.py download <github-url> -O out.bin
  python3 ghfast.py clone https://github.com/pytorch/pytorch -d pytorch

注意：hosts 只能解决 **DNS 污染**；如果 ISP 对 TLS SNI 做了阻断（表现为
TCP 通、TLS 握手失败），必须走 mirrors / download / clone 的镜像通道。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "1.0.1"
UA = "ghfast/%s (+python-stdlib)" % VERSION

HOSTS_BEGIN = "# >>> ghfast managed block >>>"
HOSTS_END = "# <<< ghfast managed block <<<"

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "ghfast")
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")

# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #

_COLOR = (not os.environ.get("NO_COLOR")) and (
    os.environ.get("GHFAST_COLOR") == "always"
    or (hasattr(sys.stdout, "isatty") and sys.stdout.isatty())
)


def _c(code: str, text: str) -> str:
    return "\033[%sm%s\033[0m" % (code, text) if _COLOR else text


def ok(msg: str) -> None:
    print("%s %s" % (_c("32", "✓"), msg))


def bad(msg: str) -> None:
    print("%s %s" % (_c("31", "✗"), msg))


def warn(msg: str) -> None:
    print("%s %s" % (_c("33", "!"), msg))


def info(msg: str) -> None:
    print("%s %s" % (_c("36", "·"), msg))


def head(msg: str) -> None:
    print("\n" + _c("1;36", msg))


def die(msg: str, code: int = 1) -> "None":
    bad(msg)
    raise SystemExit(code)


def width(s: str) -> int:
    """东亚宽字符按 2 列计算，用于对齐表格。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s: str, n: int) -> str:
    return s + " " * max(0, n - width(s))


def human_size(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return ("%.0f %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0
    return "%.1f GiB" % n


def human_ms(ms: Optional[float]) -> str:
    if ms is None:
        return "-"
    return ("%.0f ms" % ms) if ms >= 10 else ("%.1f ms" % ms)


# --------------------------------------------------------------------------- #
# 常量：域名、静态 IP 兜底、镜像候选
# --------------------------------------------------------------------------- #

# 需要修正 A 记录的域名（hosts 模式）
HOSTS_DOMAINS = [
    "github.com",
    "api.github.com",
    "codeload.github.com",
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
    "objects.githubusercontent.com",
    "media.githubusercontent.com",
    "user-images.githubusercontent.com",
    "avatars.githubusercontent.com",
    "camo.githubusercontent.com",
    "github.githubassets.com",
    "collector.github.com",
    "github.io",
]

# 只用于「DNS 全挂」时的兜底候选；是否采用由 TCP/TLS 实测决定。
_F = ["185.199.108.133", "185.199.109.133", "185.199.110.133", "185.199.111.133"]
_FP = ["185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"]
STATIC_IPS: Dict[str, List[str]] = {
    "github.com": [
        "20.27.177.113", "20.205.243.166", "140.82.112.3", "140.82.113.3",
        "140.82.114.3", "4.237.22.38", "20.200.245.247", "20.233.83.145",
    ],
    "api.github.com": ["20.27.177.116", "20.205.243.168", "140.82.112.6", "140.82.113.6"],
    "codeload.github.com": ["20.27.177.114", "20.205.243.165", "140.82.112.9", "140.82.113.9"],
    "raw.githubusercontent.com": _F,
    "gist.githubusercontent.com": _F,
    "objects.githubusercontent.com": _F,
    "media.githubusercontent.com": _F,
    "user-images.githubusercontent.com": _F,
    "avatars.githubusercontent.com": _F,
    "camo.githubusercontent.com": _F,
    "github.githubassets.com": ["185.199.108.154", "185.199.109.154", "185.199.110.154"],
    "collector.github.com": ["20.27.177.113", "20.205.243.166"],
    "github.io": _FP,
}

# DoH：JSON 接口优先（无需依赖 dnspython）
DOH_RESOLVERS: List[Tuple[str, str]] = [
    ("alidns", "https://dns.alidns.com/resolve?name={name}&type=A"),
    ("alidns-ip", "https://223.5.5.5/resolve?name={name}&type=A"),
    ("dnspod", "https://doh.pub/dns-query?name={name}&type=A"),
    ("dnspod-ip", "https://1.12.12.12/dns-query?name={name}&type=A"),
    ("cloudflare", "https://cloudflare-dns.com/dns-query?name={name}&type=A"),
    ("cloudflare-ip", "https://1.1.1.1/dns-query?name={name}&type=A"),
    ("google", "https://dns.google/resolve?name={name}&type=A"),
]

# 反代式镜像：把 "https://github.com/x" 拼成 "<prefix>https://github.com/x"
MIRROR_PREFIXES = [
    "https://ghproxy.net/",
    "https://gh-proxy.com/",
    "https://ghfast.top/",
    "https://ghproxy.cc/",
    "https://cf.ghproxy.cc/",
    "https://github.moeyy.xyz/",
    "https://gh.llkk.cc/",
    "https://ghp.ci/",
    "https://ghproxy.cn/",
    "https://hub.gitmirror.com/",
    "https://ghproxy.1888866.xyz/",
]

# jsDelivr 系 CDN：可直出 raw.githubusercontent 的文件
JSDELIVR_BASES = [
    "https://cdn.jsdelivr.net/gh/",
    "https://fastly.jsdelivr.net/gh/",
    "https://gcore.jsdelivr.net/gh/",
    "https://testingcf.jsdelivr.net/gh/",
]

# raw 域名替换式镜像
RAW_HOST_MIRRORS = ["https://raw.gitmirror.com/"]

# 用于探测镜像是否真的能取到文件（这个仓库长期存在且文件极小）
PROBE_RAW_URL = "https://raw.githubusercontent.com/octocat/Hello-World/master/README"

PYPI_MIRRORS = {
    "tuna": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc": "https://mirrors.ustc.edu.cn/pypi/simple",
    "tencent": "https://mirrors.cloud.tencent.com/pypi/simple",
}

_CTX = ssl.create_default_context()


def setup_console() -> None:
    """Windows 控制台默认不是 UTF-8、也不解析 ANSI；这里统一处理，失败不影响功能。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        for handle_id in (-11, -12):  # STDOUT / STDERR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT processing
    except Exception:
        pass


def elevation_hint(extra: str = "") -> str:
    """给出当前系统下取得管理员权限的命令（只提示，不自动提权）。"""
    script = os.path.abspath(sys.argv[0])
    if os.name == "nt":
        return 'powershell -NoProfile -Command "Start-Process -Verb RunAs python -ArgumentList \'%s %s\'"' % (
            script, extra)
    return "sudo python3 %s %s" % (script, extra)


# --------------------------------------------------------------------------- #
# 网络基础
# --------------------------------------------------------------------------- #

def fetch(url: str, timeout: float = 10.0, headers: Optional[Dict[str, str]] = None,
          max_bytes: Optional[int] = None) -> Tuple[bytes, int, Dict[str, str]]:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
        return r.read() if max_bytes is None else r.read(max_bytes), r.status, dict(r.headers)


def doh_query(template: str, name: str, timeout: float) -> List[str]:
    url = template.format(name=urllib.parse.quote(name))
    data, _status, _h = fetch(url, timeout=timeout,
                              headers={"Accept": "application/dns-json"}, max_bytes=1 << 16)
    obj = json.loads(data.decode("utf-8", "replace"))
    ips: List[str] = []
    for ans in obj.get("Answer") or []:
        if ans.get("type") == 1:
            ip = str(ans.get("data", "")).strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) and ip not in ips:
                ips.append(ip)
    return ips


def resolve_domain(name: str, timeout: float = 6.0,
                   resolvers: Sequence[Tuple[str, str]] = DOH_RESOLVERS) -> Dict[str, List[str]]:
    """多路 DoH 并发解析，返回 {ip: [来源...]}。"""
    found: Dict[str, List[str]] = {}
    resolvers = list(resolvers)
    if not resolvers:
        return found
    with ThreadPoolExecutor(max_workers=min(8, len(resolvers))) as ex:
        futs = {ex.submit(doh_query, tpl, name, timeout): tag for tag, tpl in resolvers}
        for fut in as_completed(futs):
            tag = futs[fut]
            try:
                ips = fut.result()
            except Exception:
                continue
            for ip in ips:
                src = found.setdefault(ip, [])
                if tag not in src:
                    src.append(tag)
    return found


def system_resolve(name: str) -> List[str]:
    """系统 DNS 兜底（可能被污染，只作为候选）。"""
    out: List[str] = []
    try:
        for info in socket.getaddrinfo(name, 443, socket.AF_INET, socket.SOCK_STREAM):
            ip = info[4][0]
            if ip not in out:
                out.append(ip)
    except OSError:
        pass
    return out


def tcp_probe(ip: str, port: int = 443, timeout: float = 2.0, samples: int = 2) -> Optional[float]:
    best: Optional[float] = None
    for _ in range(max(1, samples)):
        t0 = time.perf_counter()
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                pass
        except OSError:
            return None
        dt = (time.perf_counter() - t0) * 1000.0
        best = dt if best is None else min(best, dt)
    return best


def check_https(ip: str, host: str, timeout: float = 4.0, path: str = "/") -> Tuple[Optional[str], str]:
    """对指定 IP 做真实 TLS(SNI=host) + HTTP 请求，返回 (状态码, 说明)。"""
    try:
        with socket.create_connection((ip, 443), timeout=timeout) as sock:
            with _CTX.wrap_socket(sock, server_hostname=host) as ss:
                ss.settimeout(timeout)
                ss.sendall((
                    "HEAD %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
                    "Accept: */*\r\nConnection: close\r\n\r\n" % (path, host, UA)
                ).encode())
                buf = b""
                while b"\r\n" not in buf and len(buf) < 8192:
                    chunk = ss.recv(2048)
                    if not chunk:
                        break
                    buf += chunk
        line = buf.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        m = re.match(r"HTTP/\d(?:\.\d)?\s+(\d{3})", line)
        return (m.group(1) if m else None), line
    except ssl.SSLError as e:
        return None, "TLS 失败: %s" % (str(e)[:70] or type(e).__name__)
    except socket.timeout:
        return None, "超时"
    except OSError as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:70])


# --------------------------------------------------------------------------- #
# 探测：域名最优 IP / 镜像可用性
# --------------------------------------------------------------------------- #

@dataclass
class IpProbe:
    host: str
    ip: str
    source: str
    tcp_ms: Optional[float] = None
    status: Optional[str] = None
    detail: str = ""

    @property
    def serves(self) -> bool:
        return self.status is not None and self.status[:1] in ("2", "3", "4")


def probe_domain(host: str, timeout: float = 4.0, samples: int = 2) -> List[IpProbe]:
    """解析 + TCP 测速 + 对最快几个做 TLS/HTTP 验证，按速度排序返回。"""
    cands = resolve_domain(host, timeout=min(timeout + 2, 8))
    for ip in STATIC_IPS.get(host, []):
        cands.setdefault(ip, ["static"])
    if len(cands) < 2:
        for ip in system_resolve(host):
            cands.setdefault(ip, ["system"])

    items = list(cands.items())
    if not items:
        return []

    probes: List[IpProbe] = []
    with ThreadPoolExecutor(max_workers=min(16, len(items))) as ex:
        futs = {ex.submit(tcp_probe, ip, 443, timeout, samples): (ip, src) for ip, src in items}
        for fut in as_completed(futs):
            ip, src = futs[fut]
            try:
                ms = fut.result()
            except Exception:
                ms = None
            if ms is not None:
                probes.append(IpProbe(host, ip, ",".join(src), tcp_ms=ms))
    probes.sort(key=lambda p: p.tcp_ms if p.tcp_ms is not None else 9e9)

    # 只验证最快的 4 个，避免把时间浪费在明显不可用的 IP 上
    top = probes[:4]
    with ThreadPoolExecutor(max_workers=max(1, len(top))) as ex:
        futs = {ex.submit(check_https, p.ip, host, timeout): p for p in top}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                st, detail = fut.result()
            except Exception as e:  # pragma: no cover - 防御
                st, detail = None, str(e)[:70]
            p.status, p.detail = st, detail
    return probes


@dataclass
class MirrorProbe:
    kind: str            # prefix / jsdelivr / rawhost
    base: str
    ms: Optional[float] = None
    status: Optional[str] = None
    note: str = ""

    @property
    def alive(self) -> bool:
        return self.status in ("200", "206")


def mirror_url(mirror: "MirrorProbe", url: str) -> str:
    if mirror.kind == "prefix":
        return mirror.base + url
    if mirror.kind == "jsdelivr":
        return _jsdelivr_url(mirror.base, url) or ""
    if mirror.kind == "rawhost":
        return _rawhost_url(mirror.base, url) or ""
    return ""


def _jsdelivr_url(base: str, url: str) -> Optional[str]:
    """https://raw.githubusercontent.com/u/r/ref/path -> <jsdelivr>u/r@ref/path"""
    p = urllib.parse.urlsplit(url)
    if p.netloc.lower() != "raw.githubusercontent.com":
        return None
    segs = [s for s in p.path.split("/") if s]
    if len(segs) < 4:
        return None
    user, repo, ref = segs[0], segs[1], segs[2]
    rest = "/".join(segs[3:])
    return "%s%s/%s@%s/%s" % (base, user, repo, ref, rest)


def _rawhost_url(base: str, url: str) -> Optional[str]:
    p = urllib.parse.urlsplit(url)
    if p.netloc.lower() != "raw.githubusercontent.com":
        return None
    return base + p.path.lstrip("/")


def probe_mirror(mirror: "MirrorProbe", timeout: float = 8.0) -> "MirrorProbe":
    """真的取一次 64 字节，验证镜像可用而不是只看首页 200。"""
    target = mirror_url(mirror, PROBE_RAW_URL)
    if not target:
        mirror.note = "不支持该 URL 形态"
        return mirror
    req = urllib.request.Request(target, headers={"User-Agent": UA, "Range": "bytes=0-63"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            body = r.read(64)
            mirror.status = str(r.status)
            mirror.ms = (time.perf_counter() - t0) * 1000.0
            if not body:
                mirror.note = "空响应"
    except urllib.error.HTTPError as e:
        mirror.status = str(e.code)
        mirror.ms = (time.perf_counter() - t0) * 1000.0
        mirror.note = "HTTP %s" % e.code
    except Exception as e:
        mirror.status = None
        mirror.note = "%s: %s" % (type(e).__name__, str(e)[:60])
    return mirror


def all_mirrors() -> List[MirrorProbe]:
    ms = [MirrorProbe("prefix", b) for b in MIRROR_PREFIXES]
    ms += [MirrorProbe("jsdelivr", b) for b in JSDELIVR_BASES]
    ms += [MirrorProbe("rawhost", b) for b in RAW_HOST_MIRRORS]
    return ms


def live_mirrors(timeout: float = 8.0, workers: int = 10) -> List[MirrorProbe]:
    mirrors = all_mirrors()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(probe_mirror, m, timeout) for m in mirrors]
        mirrors = [f.result() for f in as_completed(futs)]
    alive = [m for m in mirrors if m.alive]
    alive.sort(key=lambda m: m.ms if m.ms is not None else 9e9)
    return alive


# --------------------------------------------------------------------------- #
# hosts
# --------------------------------------------------------------------------- #

def hosts_path() -> str:
    if platform.system() == "Windows":
        root = os.environ.get("SystemRoot", r"C:\Windows")
        return os.path.join(root, "System32", "drivers", "etc", "hosts")
    return "/etc/hosts"


def read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def strip_block(text: str) -> str:
    lines = text.splitlines(True)
    out: List[str] = []
    inside = False
    for line in lines:
        if line.strip() == HOSTS_BEGIN:
            inside = True
            continue
        if line.strip() == HOSTS_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out).rstrip("\n") + "\n"


def build_block(entries: Sequence[Tuple[str, str]]) -> str:
    lines = [HOSTS_BEGIN]
    for ip, host in entries:
        lines.append("%-16s %s" % (ip, host))
    lines.append(HOSTS_END)
    return "\n".join(lines) + "\n"


def flush_dns() -> None:
    system = platform.system()
    cmds: List[List[str]] = []
    if system == "Windows":
        cmds = [["ipconfig", "/flushdns"]]
    elif system == "Darwin":
        cmds = [["dscacheutil", "-flushcache"], ["killall", "-HUP", "mDNSResponder"]]
    else:
        if shutil.which("resolvectl"):
            cmds.append(["resolvectl", "flush-caches"])
        if shutil.which("systemd-resolve"):
            cmds.append(["systemd-resolve", "--flush-caches"])
    for cmd in cmds:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            pass


def restore_hosts() -> int:
    path = hosts_path()
    text = read_text(path)
    if HOSTS_BEGIN not in text:
        info("hosts 中没有 ghfast 记录，无需还原。")
        return 0
    new = strip_block(text)
    if not _is_admin():
        warn("需要管理员权限，请执行：")
        print("    " + elevation_hint("hosts --restore"))
        return 2
    bak = path + ".ghfast.bak"
    shutil.copy2(path, bak)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    flush_dns()
    ok("已移除 ghfast 记录（备份：%s）" % bak)
    return 0


def _is_admin() -> bool:
    if os.name == "nt":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def apply_hosts(entries: Sequence[Tuple[str, str]]) -> int:
    path = hosts_path()
    if not _is_admin():
        warn("写 hosts 需要管理员权限，请执行：")
        print("    " + elevation_hint("hosts --apply"))
        return 2
    text = read_text(path)
    bak = path + ".ghfast.bak"
    try:
        shutil.copy2(path, bak)
    except Exception:
        pass
    base = strip_block(text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(base + "\n" + build_block(entries))
    flush_dns()
    ok("已写入 %d 条记录到 %s（备份：%s）" % (len(entries), path, bak))
    info("若浏览器仍不生效：chrome://net-internals/#dns -> Clear host cache")
    return 0


# --------------------------------------------------------------------------- #
# 下载 / clone 的 URL 候选
# --------------------------------------------------------------------------- #

def _dedup(seq: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in seq:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def download_candidates(url: str, mirrors: Optional[Sequence[MirrorProbe]] = None) -> List[str]:
    """把一个 GitHub URL 展开成多条可选获取路径，按优先级排序。"""
    out: List[str] = []
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower()

    if host == "raw.githubusercontent.com":
        j = _jsdelivr_url(JSDELIVR_BASES[0], url)
        if j:
            out.append(j)
        r = _rawhost_url(RAW_HOST_MIRRORS[0], url)
        if r:
            out.append(r)

    for m in (mirrors if mirrors is not None else all_mirrors()):
        u = mirror_url(m, url)
        if u:
            out.append(u)

    out.append(url)
    return _dedup(out)


def _looks_like_proxy_error(url: str, content_type: Optional[str], body: bytes) -> bool:
    """镜像/反代会把错误页以 200 返回（content-type: text/html）。

    只要目标不是 HTML 文件、而响应声称是 HTML 且正文像 HTML，就当失败处理，
    让调用方换下一个候选。这是实测踩到的坑：新仓库在 jsDelivr 尚未索引时
    会返回 HTML 错误页，如果只看状态码就会把错误页当文件存下来。
    """
    if not body:
        return False
    path = urllib.parse.urlsplit(url).path.lower()
    if path.endswith((".html", ".htm", ".xhtml")):
        return False
    if "text/html" not in (content_type or "").lower():
        return False
    head = body.lstrip()[:64].lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def probe_download(url: str, timeout: float = 8.0, max_bytes: int = 1024) -> Optional[Tuple[str, Optional[float], Optional[int]]]:
    """返回 (url, 首字节耗时ms, 总大小) 或 None。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-%d" % (max_bytes - 1)})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            body = r.read(max_bytes)
            if not body:
                return None
            if _looks_like_proxy_error(url, r.headers.get("Content-Type"), body):
                return None
            total = r.headers.get("Content-Range", "").rsplit("/", 1)[-1]
            size = int(total) if total.isdigit() else None
            return url, (time.perf_counter() - t0) * 1000.0, size
    except Exception:
        return None


def _progress(done: int, total: Optional[int]) -> None:
    if total:
        pct = done * 100.0 / total
        bar = "#" * int(pct // 4)
        sys.stdout.write("\r  [%s%s] %5.1f%%  %s / %s" % (bar, " " * (25 - len(bar)), pct,
                                                          human_size(done), human_size(total)))
    else:
        sys.stdout.write("\r  %s" % human_size(done))
    sys.stdout.flush()


def download_to(url: str, out_path: str, timeout: float = 60.0, resume: bool = True) -> Tuple[bool, str]:
    part = out_path + ".part"
    start = 0
    if resume and os.path.exists(part):
        start = os.path.getsize(part)
    headers = {"User-Agent": UA}
    if start:
        headers["Range"] = "bytes=%d-" % start
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            if start and r.status != 206:
                start = 0  # 服务端不支持断点续传
            total = None
            cr = r.headers.get("Content-Range")
            if cr and "/" in cr:
                tail = cr.rsplit("/", 1)[-1]
                total = int(tail) + start if tail.isdigit() else None
            elif r.headers.get("Content-Length", "").isdigit():
                total = int(r.headers["Content-Length"]) + start
            first_chunk = r.read(128 * 1024)
            if _looks_like_proxy_error(url, r.headers.get("Content-Type"), first_chunk):
                return False, "镜像返回 HTML 错误页（不是目标文件）"
            done = start
            mode = "ab" if start else "wb"
            with open(part, mode) as f:
                if first_chunk:
                    f.write(first_chunk)
                    done += len(first_chunk)
                    if sys.stdout.isatty():
                        _progress(done, total)
                while True:
                    chunk = r.read(128 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if sys.stdout.isatty():
                        _progress(done, total)
            if sys.stdout.isatty():
                sys.stdout.write("\n")
            os.replace(part, out_path)
            return True, "%s (%s)" % (out_path, human_size(done))
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:120])


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# git
# --------------------------------------------------------------------------- #

def git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + list(args), capture_output=True, text=True,
                          timeout=600, check=check)


def git_available() -> bool:
    return shutil.which("git") is not None


def insteadof_pairs(prefix: str) -> List[Tuple[str, str]]:
    return [
        ("https://github.com/", prefix + "https://github.com/"),
        ("https://raw.githubusercontent.com/", prefix + "https://raw.githubusercontent.com/"),
    ]


def load_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def apply_git_mirrors(prefix: str) -> int:
    if not git_available():
        die("未找到 git")
    state = load_state()
    applied = []
    for orig, mirror in insteadof_pairs(prefix):
        r = git("config", "--global", "--replace-all", 'url."%s".insteadOf' % mirror, orig)
        if r.returncode != 0:
            bad("设置失败：%s -> %s\n%s" % (orig, mirror, r.stderr.strip()))
            return 1
        applied.append([orig, mirror])
    state["git_insteadof"] = applied
    state["git_applied_at"] = int(time.time())
    save_state(state)
    ok("git 全局镜像已启用：%s" % prefix)
    warn("副作用：git push / 私有库认证也会走镜像，可能失败。")
    info("撤销：python3 %s git --unset" % os.path.basename(sys.argv[0]))
    return 0


def unset_git_mirrors() -> int:
    if not git_available():
        die("未找到 git")
    state = load_state()
    pairs = state.get("git_insteadof") or []
    if not pairs:
        info("没有记录到 ghfast 设置过的 git 镜像。")
        return 0
    for orig, mirror in pairs:
        git("config", "--global", "--unset-all", 'url."%s".insteadOf' % mirror)
        git("config", "--global", "--remove-section", 'url."%s"' % mirror)
    state.pop("git_insteadof", None)
    save_state(state)
    ok("已撤销 %d 条 git 镜像规则" % len(pairs))
    return 0


# --------------------------------------------------------------------------- #
# pip
# --------------------------------------------------------------------------- #

def pip_config_path() -> str:
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "pip", "pip.ini")
    return os.path.join(os.path.expanduser("~"), ".config", "pip", "pip.conf")


def apply_pip(index_url: str) -> int:
    path = pip_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    host = urllib.parse.urlsplit(index_url).hostname or ""
    content = "[global]\nindex-url = %s\ntrusted-host = %s\ntimeout = 30\n" % (index_url, host)
    old = read_text(path)
    if old:
        shutil.copy2(path, path + ".ghfast.bak")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    ok("已写入 %s" % path)
    print(content)
    return 0


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #

def cmd_mirrors(args: argparse.Namespace) -> int:
    head("探测公共 GitHub 镜像（真实拉取 64 字节验证）")
    mirrors = all_mirrors()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(probe_mirror, m, args.timeout) for m in mirrors]
        results = [f.result() for f in as_completed(futs)]
    results.sort(key=lambda m: (not m.alive, m.ms if m.ms is not None else 9e9))

    print("%s %s %s %s" % (pad("类型", 10), pad("镜像", 40), pad("耗时", 10), "状态"))
    print("-" * 78)
    for m in results:
        status = _c("32", "可用") if m.alive else _c("31", "不可用")
        print("%s %s %s %s" % (pad(m.kind, 10), pad(m.base, 40), pad(human_ms(m.ms), 10),
                               status + ("  " + m.note if m.note else "")))
    alive = [m for m in results if m.alive]
    print()
    if alive:
        ok("%d/%d 个镜像可用；最快：%s (%s)" % (len(alive), len(results), alive[0].base,
                                              human_ms(alive[0].ms)))
    else:
        bad("没有可用镜像。请检查本机网络，或稍后重试（镜像随时会失效）。")
        return 1
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    head("1) DNS-over-HTTPS 是否可用")
    doh_ok = []
    for tag, tpl in DOH_RESOLVERS:
        try:
            ips = doh_query(tpl, "github.com", timeout=args.timeout)
            if ips:
                doh_ok.append((tag, ips))
                ok("%s -> %s" % (pad(tag, 14), ", ".join(ips[:3])))
            else:
                warn("%s 返回空" % tag)
        except Exception as e:
            warn("%s 不可用（%s）" % (tag, type(e).__name__))
    if not doh_ok:
        warn("全部 DoH 不可用，将退回系统 DNS（可能已被污染）")

    head("2) GitHub 域名实测（TCP 握手 + TLS-SNI + HTTP 状态）")
    print("%s %s %s %s %s" % (pad("域名", 32), pad("最优IP", 17), pad("TCP", 9), pad("状态", 14), "说明"))
    print("-" * 100)
    good = 0
    for host in args.hosts or HOSTS_DOMAINS:
        probes = probe_domain(host, timeout=args.timeout, samples=1)
        if not probes:
            print("%s %s %s %s" % (pad(host, 32), pad("-", 17), pad("-", 9),
                                   _c("31", pad("无解析结果", 14)), ""))
            continue
        best = probes[0]
        serving = next((p for p in probes if p.serves), None)
        pick = serving or best
        st = pick.status
        if st and st[:1] in ("2", "3"):
            mark, note = _c("32", pad("OK " + st, 14)), "可用"
            good += 1
        elif st:
            mark, note = _c("33", pad(st, 14)), pick.detail[:40]
        elif pick.tcp_ms is not None:
            mark, note = _c("31", pad("TLS失败", 14)), pick.detail[:60]
        else:
            mark, note = _c("31", pad("不可达", 14)), ""
        print("%s %s %s %s %s" % (pad(host, 32), pad(pick.ip, 17),
                                  pad(human_ms(pick.tcp_ms), 9), mark, note))
    print()
    if good == 0:
        warn("没有域名通过 TLS 验证：本机到 GitHub 的 443 大概率被阻断。")
        info("→ 用镜像通道：python3 %s mirrors / download / clone" % os.path.basename(sys.argv[0]))
    else:
        ok("%d 个域名可直接访问。" % good)

    head("3) 镜像通道")
    mirrors = live_mirrors(timeout=args.timeout)
    if mirrors:
        for m in mirrors[:5]:
            ok("%s (%s)" % (m.base, human_ms(m.ms)))
    else:
        bad("当前网络下没有可用镜像。")

    head("4) 本机工具")
    for tool in ("git", "curl", "pip3"):
        p = shutil.which(tool) or shutil.which(tool + ".exe")
        (ok if p else warn)("%s: %s" % (tool, p or "未安装"))
    info("Python %s / %s / hosts=%s" % (platform.python_version(), platform.system(), hosts_path()))
    return 0


def cmd_hosts(args: argparse.Namespace) -> int:
    if args.restore:
        return restore_hosts()

    path = hosts_path()
    current = read_text(path)
    info("hosts 文件：%s" % path)
    if HOSTS_BEGIN in current:
        info("检测到已存在的 ghfast 记录，将整体替换。")

    entries: List[Tuple[str, str]] = []
    head("解析并实测各域名最优 IP")
    print("%s %s %s %s" % (pad("域名", 32), pad("选用IP", 17), pad("TCP", 9), "依据"))
    print("-" * 84)
    for host in args.hosts or HOSTS_DOMAINS:
        probes = probe_domain(host, timeout=args.timeout, samples=2)
        if not probes:
            bad("%s 无解析结果，跳过" % host)
            continue
        serving = next((p for p in probes if p.serves), None)
        pick = serving or probes[0]
        why = "TLS+HTTP %s" % pick.status if serving else "仅 TCP 可达（TLS 未通过）"
        if not serving:
            why = _c("33", why)
        print("%s %s %s %s" % (pad(host, 32), pad(pick.ip, 17), pad(human_ms(pick.tcp_ms), 9), why))
        entries.append((pick.ip, host))

    if not entries:
        die("没有可用 IP，hosts 方案不适用。请改用 mirrors / download / clone。")

    block = build_block(entries)
    print()
    print(block)

    if not args.apply:
        info("以上仅为预览。写入系统： sudo python3 %s hosts --apply" % os.path.basename(sys.argv[0]))
        return 0
    return apply_hosts(entries)


def cmd_download(args: argparse.Namespace) -> int:
    url = args.url
    out = args.output or os.path.basename(urllib.parse.urlsplit(url).path.rstrip("/")) or "download.bin"
    head("查找可用来源")
    if args.direct:
        cands = [url]
    else:
        cands = download_candidates(url, live_mirrors(timeout=args.timeout))
    ok("候选 %d 条" % len(cands))

    results = []
    with ThreadPoolExecutor(max_workers=min(12, len(cands))) as ex:
        futs = [ex.submit(probe_download, c, args.timeout) for c in cands]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
    if not results:
        die("所有来源都取不到该文件。原始 URL：%s" % url)
    results.sort(key=lambda r: r[1] if r[1] is not None else 9e9)

    print("%s %s %s" % (pad("来源", 6), pad("首字节", 10), "URL"))
    print("-" * 100)
    for i, (u, ms, size) in enumerate(results):
        print("%s %s %s" % (pad("#%d" % (i + 1), 6), pad(human_ms(ms), 10), u[:110]))

    head("下载到 %s" % out)
    for u, _ms, _size in results:
        okk, msg = download_to(u, out, timeout=args.timeout * 6)
        if okk:
            ok(msg)
            info("sha256 %s" % sha256_file(out))
            return 0
        warn("失败，换下一个来源：%s" % msg)
    die("全部来源下载失败")


def cmd_clone(args: argparse.Namespace) -> int:
    if not git_available():
        die("未找到 git")
    url = args.url
    dest = args.dest or re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1])
    mirrors = live_mirrors(timeout=args.timeout)
    cands: List[str] = [m.base + url for m in mirrors if m.kind == "prefix"]

    p = urllib.parse.urlsplit(url)
    m = re.match(r"^/([^/]+)/([^/]+?)(?:\.git)?/?$", p.path)
    if p.netloc.lower() == "github.com" and m:
        cands.append("https://gitclone.com/github.com/%s/%s.git" % (m.group(1), m.group(2)))
    cands.append(url)
    cands = _dedup(cands)

    extra = list(args.git_args or [])
    if args.depth:
        extra += ["--depth", str(args.depth)]
    if args.recursive:
        extra.append("--recursive")

    head("尝试 %d 个来源 clone 到 %s" % (len(cands), dest))
    for i, c in enumerate(cands, 1):
        info("[%d/%d] %s" % (i, len(cands), c))
        r = subprocess.run(["git", "clone", c, dest] + extra)
        if r.returncode == 0:
            ok("clone 成功：%s" % c)
            return 0
        warn("失败，换下一个来源")
        if os.path.isdir(dest) and not os.listdir(dest):
            os.rmdir(dest)
    die("所有来源都 clone 失败")


def cmd_git(args: argparse.Namespace) -> int:
    if args.unset:
        return unset_git_mirrors()

    if args.direct:
        prefix_mirrors = [MirrorProbe("prefix", MIRROR_PREFIXES[0])]
    else:
        prefix_mirrors = [m for m in live_mirrors(timeout=args.timeout) if m.kind == "prefix"]
    if not prefix_mirrors:
        die("没有可用前缀镜像，无法生成 insteadOf 规则（可用 --direct 使用内置候选）")
    best = prefix_mirrors[0]

    head("git 镜像规则（前缀镜像：%s，%s）" % (best.base, human_ms(best.ms)))
    print("# 让 git 自动把 github.com 的地址改写到镜像")
    for orig, mirror in insteadof_pairs(best.base):
        print('git config --global url."%s".insteadOf %s' % (mirror, orig))

    if not args.apply:
        info("加 --apply 直接写入（注意：会同时影响 push）")
        return 0
    return apply_git_mirrors(best.base)


def cmd_pip(args: argparse.Namespace) -> int:
    name = args.mirror
    url = PYPI_MIRRORS.get(name, name)
    if url not in PYPI_MIRRORS.values() and not url.startswith("http"):
        die("未知镜像 %s，可选：%s" % (name, ", ".join(PYPI_MIRRORS)))
    head("PyPI 镜像：%s" % url)
    if not args.apply:
        print("[global]")
        print("index-url = %s" % url)
        print("trusted-host = %s" % (urllib.parse.urlsplit(url).hostname or ""))
        info("加 --apply 写入 %s" % pip_config_path())
        return 0
    return apply_pip(url)


def _install_vendor_wheels() -> None:
    """vendor/ 里放了离线 wheel 就装；本项目默认没有任何第三方依赖。"""
    vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
    req = os.path.join(vendor, "requirements.txt")
    if not os.path.isfile(req):
        return
    with open(req, "r", encoding="utf-8") as f:
        pins = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
    if not pins:
        info("vendor/requirements.txt 为空：本项目不需要任何第三方包。")
        return
    pip = shutil.which("pip3") or shutil.which("pip")
    if not pip:
        warn("vendor/ 有依赖清单但找不到 pip，跳过离线安装")
        return
    info("从 vendor/ 离线安装 %d 个依赖（无网络）" % len(pins))
    r = subprocess.run([pip, "install", "--no-index", "--find-links", vendor,
                        "-r", req], capture_output=True, text=True)
    (ok if r.returncode == 0 else bad)("离线依赖安装 %s" % ("完成" if r.returncode == 0 else "失败"))
    if r.returncode != 0:
        print((r.stdout or "")[-800:] + (r.stderr or "")[-400:])


def cmd_install(args: argparse.Namespace) -> int:
    if os.name == "nt" and args.system:
        die("Windows 没有 /usr/local/bin，请用默认的用户级安装（去掉 --system）")
    if args.system:
        target_dir = "/usr/local/bin"
        if not _is_admin():
            die("--system 需要 root：" + elevation_hint("install --system"))
    else:
        target_dir = args.dir or os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.makedirs(target_dir, exist_ok=True)

    src = os.path.abspath(__file__)
    if not os.path.isfile(src):
        die("当前以 zipapp 方式运行，无法自我安装；请在源码目录执行 install，或直接用 dist/ghfast.pyz")

    dst = os.path.join(target_dir, "ghfast.py")
    shutil.copyfile(src, dst)
    try:
        os.chmod(dst, 0o755)
    except OSError:
        pass

    if os.name == "nt":
        shim = os.path.join(target_dir, "ghfast.cmd")
        with open(shim, "w", encoding="ascii", newline="\r\n") as f:
            f.write("@echo off\r\npython \"%~dp0ghfast.py\" %*\r\n")
    else:
        shim = os.path.join(target_dir, "ghfast")
        with open(shim, "w", encoding="utf-8") as f:
            f.write('#!/bin/sh\nexec python3 "$(dirname "$0")/ghfast.py" "$@"\n')
        try:
            os.chmod(shim, 0o755)
        except OSError:
            pass
    ok("已安装：%s" % shim)

    if target_dir not in os.environ.get("PATH", "").split(os.pathsep):
        warn("%s 不在 PATH 中：" % target_dir)
        if os.name == "nt":
            print("    powershell -NoProfile -Command \"[Environment]::SetEnvironmentVariable("
                  "'Path', [Environment]::GetEnvironmentVariable('Path','User') + ';%s', 'User')\""
                  % target_dir)
            print("    然后重开终端。")
        else:
            print('    echo \'export PATH="%s:$PATH"\' >> ~/.bashrc' % target_dir)

    _install_vendor_wheels()
    info("零第三方依赖：不需要 pip install，Python %s 即可运行。" % platform.python_version())
    info("跨平台打包：python3 build.py  ->  dist/ghfast.pyz")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    passed = failed = 0

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            ok("%s%s" % (name, ("  " + extra) if extra else ""))
        else:
            failed += 1
            bad("%s%s" % (name, ("  " + extra) if extra else ""))

    raw = "https://raw.githubusercontent.com/octocat/Hello-World/master/README"
    c = download_candidates(raw, [])
    check("raw 文件生成 jsDelivr 候选", any("jsdelivr.net" in u for u in c))
    check("raw 文件生成 rawhost 候选", any("raw.gitmirror.com" in u for u in c))
    check("始终包含原始 URL", c[-1] == raw)

    rel = "https://github.com/pytorch/pytorch/releases/download/v2.0.0/x.whl"
    c2 = download_candidates(rel, [MirrorProbe("prefix", "https://ghproxy.net/")])
    check("release 资产走前缀镜像", c2[0] == "https://ghproxy.net/" + rel)

    arc = "https://github.com/git/git/archive/refs/tags/v2.0.0.tar.gz"
    check("archive 走前缀镜像", any(u.startswith("https://ghproxy.net/https://github.com/git/git/archive") for u in
                                 download_candidates(arc, [MirrorProbe("prefix", "https://ghproxy.net/")])))

    block = build_block([("1.2.3.4", "github.com")])
    check("hosts 块格式", HOSTS_BEGIN in block and HOSTS_END in block and "1.2.3.4" in block)
    text = "127.0.0.1 localhost\n" + block + "1.1.1.1 x\n"
    stripped = strip_block(text)
    check("hosts 块可剥离", HOSTS_BEGIN not in stripped and "127.0.0.1 localhost" in stripped and "1.1.1.1 x" in stripped)
    check("重复剥离幂等", strip_block(stripped) == stripped)

    pairs = insteadof_pairs("https://ghproxy.net/")
    check("insteadOf 规则", pairs[0][1] == "https://ghproxy.net/https://github.com/")

    check("东亚字符对齐", width("域名") == 4 and pad("域名", 6) == "域名  ")
    check("体积格式化", human_size(1536) == "1.5 KiB" and human_size(999) == "999 B")

    print()
    print("selftest: %d passed, %d failed" % (passed, failed))
    return 0 if failed == 0 else 1


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ghfast",
        description="免 VPN 访问 / 加速 GitHub：DNS 修复 + 镜像回退 + 工具链配置（纯标准库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  ghfast doctor                     诊断被卡在哪一层
  ghfast hosts --apply              写 hosts（需 sudo，自动备份）
  ghfast mirrors                    看当前哪些镜像活着
  ghfast download URL -O file       多镜像回退下载
  ghfast clone URL -d dir           多镜像回退 clone
  ghfast git --apply                让 git 全局走镜像（可 --unset 撤销）
""")
    p.add_argument("--version", action="version", version="ghfast " + VERSION)
    p.add_argument("--timeout", type=float, default=6.0, help="单次网络操作超时秒数（默认 6）")
    p.add_argument("--workers", type=int, default=10, help="并发度（默认 10）")
    # 让 --timeout/--workers 也能写在子命令后面：默认值 SUPPRESS 表示「未显式给出就不覆盖」。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    common.add_argument("--workers", type=int, default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", metavar="<command>")

    d = sub.add_parser("doctor", parents=[common], help="诊断 DNS / TCP / TLS / 镜像可用性")
    d.add_argument("--hosts", nargs="*", help="只检查指定域名")
    d.set_defaults(func=cmd_doctor)

    h = sub.add_parser("hosts", parents=[common], help="生成/写入 hosts 记录")
    h.add_argument("--apply", action="store_true", help="真正写入（需管理员权限）")
    h.add_argument("--restore", action="store_true", help="移除 ghfast 写入的记录")
    h.add_argument("--hosts", nargs="*", help="只处理指定域名")
    h.set_defaults(func=cmd_hosts)

    m = sub.add_parser("mirrors", parents=[common], help="探测镜像实时可用性")
    m.set_defaults(func=cmd_mirrors)

    dl = sub.add_parser("download", parents=[common], help="多镜像回退下载")
    dl.add_argument("url")
    dl.add_argument("-O", "--output", help="输出文件名")
    dl.add_argument("--direct", action="store_true", help="跳过镜像，只用原始 URL")
    dl.set_defaults(func=cmd_download)

    cl = sub.add_parser("clone", parents=[common], help="多镜像回退 git clone")
    cl.add_argument("url")
    cl.add_argument("-d", "--dest", help="目标目录")
    cl.add_argument("--depth", type=int, help="浅克隆层数")
    cl.add_argument("--recursive", action="store_true", help="递归子模块")
    cl.add_argument("rest", nargs=argparse.REMAINDER, help="透传给 git clone 的参数")
    cl.set_defaults(func=cmd_clone, git_args=None)

    g = sub.add_parser("git", parents=[common], help="配置/撤销 git 全局镜像")
    g.add_argument("--apply", action="store_true", help="写入 git 全局配置")
    g.add_argument("--unset", action="store_true", help="撤销之前的规则")
    g.add_argument("--direct", action="store_true", help="不探测，直接给规则")
    g.set_defaults(func=cmd_git)

    pi = sub.add_parser("pip", parents=[common], help="配置 PyPI 镜像")
    pi.add_argument("--mirror", default="tuna", help="tuna|aliyun|ustc|tencent|URL（默认 tuna）")
    pi.add_argument("--apply", action="store_true", help="写入 pip 配置")
    pi.set_defaults(func=cmd_pip)

    ins = sub.add_parser("install", parents=[common], help="安装自身到 PATH")
    ins.add_argument("--dir", help="目标目录（默认 ~/.local/bin）")
    ins.add_argument("--system", action="store_true", help="安装到 /usr/local/bin（需 root）")
    ins.set_defaults(func=cmd_install)

    st = sub.add_parser("selftest", parents=[common], help="离线自检")
    st.set_defaults(func=cmd_selftest)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    if getattr(args, "cmd", "") == "clone":
        args.git_args = [a for a in (args.rest or []) if a != "--"]
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print()
        warn("已中断")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
