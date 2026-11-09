# vendor：离线安装包目录

这个目录用来放 `.whl` 安装包，供不能联网的电脑使用。仓库里默认是空的。

## 怎么把安装包放进来

在一台能上网的电脑上，进入仓库根目录，执行：

```
python3 -m pip download numpy -d vendor --only-binary=:all: -i https://pypi.tuna.tsinghua.edu.cn/simple
```

下载完成后，`vendor` 目录里会出现一个类似 `numpy-1.26.4-cp310-cp310-manylinux_x86_64.whl` 的文件。把整个仓库文件夹拷到目标电脑，执行：

```
python3 -m pip install --no-index --find-links vendor numpy
```

## 注意

（1）wheel 文件与 Python 版本、操作系统、处理器架构绑定。目标电脑是 Python 3.10 的 64 位 Linux，就要下 `cp310` 且 `manylinux` 的那个文件。

（2）如果下载电脑与目标电脑的系统不同，先确认目标机器的版本：`python3 -c "import sys; print(sys.version, sys.platform)"`，再到对应系统上下载。

（3）需要绘图时把 `numpy` 换成 `numpy matplotlib`，两个文件会一并存放在这里。
