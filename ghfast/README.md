# ghfast —— 不开 VPN 访问 / 加速 GitHub

> 跨平台工具，**零第三方依赖**（纯 Python 标准库）。**零第三方依赖**，Python 3.8+，Windows / macOS / Linux 通用。

[![CI](https://github.com/yingzhou-bjtu/course-teaching/actions/workflows/ci.yml/badge.svg)](https://github.com/yingzhou-bjtu/course-teaching/actions/workflows/ci.yml)

---

网上的"免 VPN 访问 GitHub"教程大多有两个毛病：抄来的 hosts IP 早就过期；以及让你先 `pip install requests`——可被墙的机器上 pip 本身就要先能上网。这个项目把能自动化的部分都做了，并且**没有任何依赖**，所以不存在"装不上依赖"的死循环。

## 它做什么

| 子命令 | 作用 | 解决什么 |
|---|---|---|
| `doctor` | 分层诊断 DNS / TCP / TLS-SNI / 镜像 | 先搞清楚是被墙在哪一层，别瞎试 |
| `hosts` | 多源 DoH 解析 + 实测，生成并写入 hosts | DNS 污染 |
| `mirrors` | 实测公共反代镜像的实时延迟 | 选一个当下能用的镜像 |
| `download` | 多镜像竞速 + 自动回退 + 断点续传 | release 资产 / raw 文件 / archive 下不动 |
| `clone` | 多镜像逐个重试 | `git clone` 卡住或超时 |
| `git` | `url.insteadOf` 让 git 全局走镜像（可撤销） | 老仓库频繁 fetch 慢 |
| `pip` | 配置 PyPI 国内镜像 | 装 Python 依赖慢 |
| `install` | 安装到 PATH + 生成启动器 | 一条命令装好 |
| `selftest` | 离线自检 | 确认拷过去的文件没坏 |

关键设计：**不信任任何写死的 IP 或镜像**。每次运行都现场实测——解析出来只是候选，TCP 握手测速，最快的那几个再做真实 TLS 握手（SNI=域名）和 HTTP 请求，只有握手成功才被采用。镜像同理，真的拉 64 字节，不看首页状态码。

## 平台支持

| 系统 | 版本 | hosts | 安装位置 | 已验证 |
|---|---|---|---|---|
| Linux | glibc / WSL | `/etc/hosts` | `~/.local/bin` | ✅ 本机实测 |
| macOS | 10.13+ | `/etc/hosts` | `~/.local/bin` | ✅ CI |
| Windows | 10 / 11 | `%SystemRoot%\System32\drivers\etc\hosts` | `%USERPROFILE%\.local\bin` + `ghfast.cmd` | ✅ CI |

Windows 下额外处理了三件事：控制台切 UTF-8 并开启 ANSI（否则中文乱码）、`ctypes` 判断管理员权限、以及给出 `Start-Process -Verb RunAs` 的提权命令而不是直接失败。macOS 会同时 `dscacheutil -flushcache` 和 `killall -HUP mDNSResponder`，Linux 有 `resolvectl` 就刷。

## 安装

**依赖：一个 Python 3.8+ 解释器，别的没了。**

### Windows

```powershell
git clone https://github.com/yingzhou-bjtu/course-teaching.git
cd course-teaching\ghfast
powershell -ExecutionPolicy Bypass -File .\install.ps1
# 新开一个终端
ghfast doctor
```

没有 git？直接下载 ZIP 解压，再执行上面的 `install.ps1`。没有 Python？`winget install Python.Python.3.12`。

### macOS

```bash
git clone https://github.com/yingzhou-bjtu/course-teaching.git
cd course-teaching/ghfast
sh install.sh
ghfast doctor
```

### Linux / WSL

```bash
git clone https://github.com/yingzhou-bjtu/course-teaching.git
cd course-teaching/ghfast
sh install.sh
ghfast doctor
```

### 不想安装

```bash
python3 ghfast/ghfast.py doctor      # 在仓库根目录直接跑
./ghfast/launchers/ghfast doctor     # POSIX 启动器
ghfast\launchers\ghfast.cmd doctor  # Windows 启动器
python3 ghfast/build.py              # 打成单文件 ghfast/dist/ghfast.pyz
```

`dist/ghfast.pyz` 是一个 15 KB 的单文件，拷到任何装有 Python 3.8+ 的机器都能直接跑，适合离线分发。

## 用法

```bash
# 0) 先诊断：卡在哪一层？
ghfast doctor

# 1) 修 DNS（会备份 /etc/hosts，可随时还原）
ghfast hosts                  # 只预览，不动系统
sudo ghfast hosts --apply     # Windows 用管理员 PowerShell，去掉 sudo
sudo ghfast hosts --restore   # 还原

# 2) 绕 CDN：看哪些镜像活着
ghfast mirrors

# 3) 下载：多镜像竞速，失败自动换下一条
ghfast download https://github.com/pytorch/pytorch/releases/download/v2.5.0/x.whl -O x.whl
ghfast download https://raw.githubusercontent.com/octocat/Hello-World/master/README

# 4) clone：逐个镜像重试
ghfast clone https://github.com/pytorch/pytorch -d pytorch --depth 1

# 5) git 全局走镜像（注意：push 也会被改写，故默认不写入）
ghfast git
ghfast git --apply
ghfast git --unset

# 6) PyPI 镜像
ghfast pip --apply --mirror tuna     # tuna | aliyun | ustc | tencent
```

`--timeout` / `--workers` 写在子命令前后都行，例如 `ghfast mirrors --timeout 8`。

## 工作原理

**第一层：DNS 污染。** 对 `github.com`、`raw.githubusercontent.com`、`codeload.github.com` 等 13 个域名，并发问阿里 / 腾讯 / Cloudflare / Google 的 DoH（JSON 接口，不需要 dnspython）。拿到候选 IP 后先 TCP 握手测速取两次最小值，最快的 4 个再做真实 TLS 握手（`server_hostname=域名`）+ HTTP HEAD。**能 ping 通不等于能用**——GitHub 的证书绑定域名，CDN 节点未必服务该域名，这一步能过滤掉大量"看着通的假 IP"。最后写入带 `>>> ghfast managed block >>>` 标记的区块，替换式更新，可整体剥离。

**第二层：SNI 阻断。** 如果 TCP 通但 TLS 握手被 reset（典型症状：`raw.githubusercontent.com` 连不上），hosts 就无能为力了，必须走镜像：

- 前缀反代：`<mirror>https://github.com/...`（ghproxy 系）
- jsDelivr：`raw.githubusercontent.com/u/r/ref/path` → `cdn.jsdelivr.net/gh/u/r@ref/path`（四个 CDN 域名轮换）
- raw 域名替换：`raw.gitmirror.com/...`

下载时把一个 URL 展开成 N 条候选，并发各取前 1 KB 竞速，选最快的流式下载，失败自动换下一条并支持断点续传。另外公共镜像经常把错误页以 **200 + `text/html`** 返回，所以下载前会校验 content-type 与正文首字节——否则你下到的「README」可能是一张 404 页面（这个坑是实测踩出来的）。

**第三层：工具链。** git 用 `url.<mirror>.insteadOf` 做地址重写（副作用是 push 也走镜像，所以默认只打印不写入，写入后可 `--unset` 精确回滚，规则记在 `~/.config/ghfast/state.json`）；pip 写 `pip.conf` / `pip.ini`。

## 目录结构

```
ghfast/
├── ghfast.py                  # 全部实现，单文件，零依赖
├── install.sh / install.ps1   # 两种系统的安装入口
├── build.py                   # 打包 dist/ghfast.pyz
├── launchers/                 # 免安装直接运行的启动器
├── vendor/                    # 依赖目录（空的，因为不需要依赖）
└── README.md
```

测试与 CI 在仓库根目录：`tests/test_ghfast.py`、`.github/workflows/ci.yml`。

## 常见问题

**为什么仓库叫 `course-teaching` 而不是「课程教学」？**
GitHub 的仓库名只接受 ASCII 字母、数字和 `.-_`，建「课程教学」会被静默改成一个 `-`（我试过，URL 变成 `github.com/yingzhou-bjtu/-`）。所以用英文名，中文标题放在 description 和 README 里。

**为什么不需要 `pip install`？**
因为一个第三方包都没用。见 [vendor/README.md](vendor/README.md)——那里也写了"如果以后真的加了依赖，怎么做纯离线安装"。

**改了 hosts 还是打不开？**
1. 浏览器有自己的 DNS 缓存：Chrome 打开 `chrome://net-internals/#dns` → Clear host cache。
2. IP 会随 GitHub 调度变化，隔几周重跑 `ghfast hosts --apply`。
3. 如果 `doctor` 显示 TLS 失败，说明是 SNI 阻断，hosts 无效，用 `download` / `clone`。

**镜像安全吗？**
公共镜像能看到你请求的 URL 和内容。**不要用它传私有仓库、token 或公司代码**——私有库请只用 `hosts`（官方域名 + 好 IP），不要 `git --apply`。

**能上 GitHub 就一定要用这个吗？**
不用。它只在网络受限或很慢时才有价值；一切正常时 `doctor` 会直接告诉你"可用"，不影响你任何配置（除非你显式 `--apply`）。

## 安全与合规

- 只做三件事：改本机 DNS 解析、走公共反代下载公开资源、改你自己的 git/pip 配置。不改系统代理、不装证书、不启后台服务。
- `hosts --apply` 会先备份到 `hosts.ghfast.bak`，`--restore` 精确还原。
- 所有改动都可逆：`hosts --restore`、`git --unset`、`pip` 配置文件旁边有 `.ghfast.bak`。
- 仅用于加速访问公开的开源资源，请遵守当地法律法规与网络使用规定。

## License

[MIT](../LICENSE)
