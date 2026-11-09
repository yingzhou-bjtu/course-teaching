# 依赖：这里是空的，而且是有意为之

ghfast 只使用 Python 标准库（`urllib` / `socket` / `ssl` / `argparse` / `hashlib` …），
**没有任何第三方依赖**，所以不需要 `pip install`，也就不存在"装不上依赖"的死循环。

## 为什么很多教程会在这里翻车

被墙的机器上 `pip install requests` 往往也要先配镜像，而配镜像又得先能上网——
所以本项目的选择是：干脆不用任何第三方包。

## vendor/ 的用途

只有当你在这个项目上**新增**依赖时才需要它：

1. 在能联网的机器上下载 wheel：
   ```bash
   pip download -d vendor requests==2.32.3
   ```
2. 把包名写进 `requirements.txt`（一行一个）。
3. 拷贝整个仓库到目标机器，执行：
   ```bash
   python ghfast.py install
   ```
   安装器会用 `pip install --no-index --find-links vendor -r vendor/requirements.txt`
   做**纯离线**安装。

`vendor/requirements.txt` 目前为空，因此安装器会跳过这一步并打印
「本项目不需要任何第三方包」。
