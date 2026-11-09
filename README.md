# 课程教学

两个东西放在一个仓库里，都是给学生用的：

| 目录 / 文件 | 是什么 | 依赖 |
|---|---|---|
| [`猫狗识别.ipynb`](猫狗识别.ipynb) | **主线课程**：从零用 NumPy 写一个小卷积网络做猫狗分类 | 只有 `numpy` |
| [`ghfast/`](ghfast/) | 小工具：不开 VPN 也能访问 / 加速 GitHub（下数据集、装依赖时救命） | 只有 Python 标准库 |
| [`tests/`](tests/) | 自动化测试：保证 notebook 和工具都能跑 | `numpy` |

## 1. 主线课程：猫狗识别

`猫狗识别.ipynb` 用一个**只用 NumPy** 的小卷积网络完成"猫 vs 狗"二分类，
目的是把"神经网络到底在算什么"讲透，而不是调包。

**为什么不用 PyTorch**：CPU 版轮子约 200 MB、CUDA 版 2 GB+，国内下载经常卡住；
而本课程唯一的硬依赖是 `numpy`（约 15 MB），配好镜像几秒装完。
学完原理再去用框架，你会知道 `nn.Conv2d` 到底替你做了什么。

### 课程结构（10 步，每步都能跑）

| 步骤 | 内容 | 你会看到 |
|---|---|---|
| 0 | 检查环境 | Python / NumPy 版本、中文字体 |
| 1 | 准备数据 | 下载 CIFAR-10 取猫狗子集；顺带抓几张真实猫狗大图显示在 notebook 里 |
| 2 | 预处理 | 标准化、打乱，确认 `(N,3,32,32)` 的形状 |
| 3 | 卷积是什么 | 手算一个 3×3 卷积，再作用到真实图片上 |
| 4 | 实现各层 | im2col 卷积、最大池化、softmax 交叉熵、Adam |
| 5 | 搭网络 | 13 万参数的小 CNN |
| 6 | **梯度检查** | 数值梯度 vs 反向传播，验证自己写对了 |
| 7 | 训练 | loss / 准确率曲线 |
| 8 | 评估 | 混淆矩阵、错例可视化，再用真实照片测一测（域差异） |
| 9 | 改进 | 数据增强对比实验（过拟合） |
| 10 | 换数据 | 用自己拍的猫狗照片 |

### 快速开始

```bash
# 1) 装依赖（配好镜像的话几秒钟）
pip install numpy               # 必需
pip install matplotlib pillow   # 可选：画图、读自己的照片

# 2) 打开 notebook
jupyter notebook 猫狗识别.ipynb
```

没有 Jupyter 也可以先跑自检（它会真的把 notebook 执行一遍）：

```bash
python -m unittest tests.test_notebook -v
```

**第一次跑建议**：把第一个 cell 里的 `FAST_DEMO` 改成 `True`，
用合成数据约 10 秒跑完全流程，确认环境没问题；再改回 `False` 用真实数据训练。

**默认配置耗时**：4000 张训练图、6 个 epoch，普通笔记本 CPU 上约 1~3 分钟。

所有图都**直接显示在 notebook 单元格下方**，不会弹独立窗口（脚本模式下只画不弹）。

### 数据从哪来（三选一）

| 模式 | 说明 | 需要什么 |
|---|---|---|
| `cifar`（默认） | 自动下载 CIFAR-10（约 163 MB，带断点续传 + MD5 校验），只取猫/狗两类 | 网络 |
| `folder` | 你自己的 `data/cats_dogs/cat/*.jpg` 与 `dog/*.jpg` | Pillow |
| `toy` | 程序合成的"尖耳猫 / 垂耳狗"，没网时兜底，只为跑通流程 | 什么都不用 |

> 想要真实猫狗大图：Kaggle 的 *Dogs vs Cats*（25000 张）需要注册下载，
> 让老师打包发给大家更省事；notebook 的 `folder` 模式直接支持。

### 前置知识

会 Python 基础语法、知道"矩阵相乘"是什么就够了。反向传播的数学会在用到时解释，
不要求先学微积分。

## 2. ghfast：网络不通时的那根救命稻草

课程里要下载数据集、装依赖，国内网络经常卡在 GitHub 上。`ghfast` 负责这一块：

```bash
python ghfast/ghfast.py doctor      # 先诊断：卡在 DNS、TLS 还是线路
python ghfast/ghfast.py mirrors     # 看当前哪些镜像活着
python ghfast/ghfast.py download <url> -O out.bin
```

零第三方依赖，Windows / macOS / Linux 都支持。详见 [ghfast/README.md](ghfast/README.md)。

## 目录结构

```
course-teaching/
├── 猫狗识别.ipynb            # 主线课程
├── requirements.txt          # numpy（+ 可选 matplotlib / pillow）
├── ghfast/                   # 加速工具（独立小项目，零依赖）
│   ├── ghfast.py
│   ├── build.py              # 打包 dist/ghfast.pyz
│   ├── install.sh / install.ps1
│   ├── launchers/            # 免安装直接运行
│   ├── vendor/               # 依赖目录（空的：本项目不需要依赖）
│   └── README.md
├── tests/
│   ├── test_ghfast.py        # 30 个单元测试
│   └── test_notebook.py      # 真的把 notebook 跑一遍
└── .github/workflows/ci.yml
```

## 环境要求

| | 版本 | 说明 |
|---|---|---|
| Python | 3.8+ | notebook 与工具都兼容 |
| NumPy | 1.21+ | 唯一的硬依赖 |
| Matplotlib | 3.5+ | 可选，画图 |
| Pillow | 9.0+ | 可选，读自己的照片 |
| 操作系统 | Windows / macOS / Linux | CI 三个系统都测 |

## CI

`push` 和 PR 都会在 **Windows / macOS / Ubuntu × Python 3.8 / 3.10 / 3.12** 上跑：
单元测试、ghfast 自检、打包 zipapp，以及**把 notebook 从头执行一遍**。

## License

[MIT](LICENSE)
