# 课程教学

仓库包含两部分：一份讲原理的教学 notebook，一个网络不通时可用的小工具。

| 路径 | 内容 | 依赖 |
|---|---|---|
| [`猫狗识别.ipynb`](猫狗识别.ipynb) | 主线课程，用 NumPy 从零实现卷积网络做猫狗分类 | 仅 `numpy` |
| [`ghfast/`](ghfast/) | 不开 VPN 访问 GitHub 的工具，下载依赖时使用 | 仅 Python 标准库 |
| [`tests/`](tests/) | 自动化测试，含 notebook 的端到端执行 | `numpy` |

## 一、主线课程

### 设计取舍

现有教学多先讲网络结构，再调用框架接口。学习者看到损失下降，却看不到损失为何下降，出错时也难定位。本课程把卷积、池化、交叉熵与优化器逐层写成函数，中间量可打印，形状与梯度可逐层核对。

| | 本课程 | 框架方案 |
|---|---|---|
| 依赖 | NumPy | 框架轮子数百 MB |
| 首次运行 | 无需下载数据 | 需要数据集与依赖 |
| 训练耗时 | CPU 十余秒 | 通常需要 GPU |
| 教学重点 | 计算过程 | 端到端流程 |

### 课程结构

| 步骤 | 内容 |
|---|---|
| 0 | 检查环境，确认版本与中文字体 |
| 1 | 构造函数生成猫狗样本，或读取本地照片目录 |
| 2 | 标准化与打乱，确认张量形状 |
| 3 | 手算一次卷积，观察边缘响应 |
| 4 | 实现 im2col 卷积、最大池化、softmax 交叉熵与 Adam |
| 5 | 搭建约十三万参数的小网络，做数值梯度检验 |
| 6 | 训练并记录损失与准确率 |
| 7 | 评估，查看混淆矩阵与错例 |
| 8 | 数据增强对比实验 |
| 附 | 思考题与改用框架的时机 |

### 运行方式

```bash
pip install numpy              # 唯一必需项
pip install matplotlib         # 可选，用于绘制训练曲线
jupyter notebook 猫狗识别.ipynb
```

没有 Jupyter 时可先跑自检，它会完整执行一遍课程代码：

```bash
python -m unittest tests.test_notebook -v
```

默认配置为每类一千张样本、四个 epoch，普通笔记本 CPU 上十余秒即可跑完；把第一个单元格的 `FAST_DEMO` 改为 `True` 可压到两秒以内，用于确认环境。

### 数据来源

默认由程序生成两类头像样本，无需下载，也不依赖外部数据。若已有真实的猫狗照片，将 `DATA_MODE` 改为 `folder`，按 `data/cats_dogs/cat/*.jpg` 与 `data/cats_dogs/dog/*.jpg` 放置即可，读取时需要 Pillow。

### 前置知识

Python 基础语法与矩阵乘法的含义即可。反向传播的推导在使用处解释，不要求预先掌握微积分。

## 二、ghfast

课程中下载依赖常卡在 GitHub 上，`ghfast` 用于诊断与绕行：

```bash
python ghfast/ghfast.py doctor      # 检查卡在 DNS、TLS 还是线路
python ghfast/ghfast.py mirrors     # 查看当前可用镜像
python ghfast/ghfast.py download <url> -O out.bin
```

零第三方依赖，Windows、macOS、Linux 通用，详见 [ghfast/README.md](ghfast/README.md)。

## 目录结构

```
course-teaching/
├── 猫狗识别.ipynb            # 主线课程
├── requirements.txt          # numpy（matplotlib、pillow 可选）
├── ghfast/                   # GitHub 加速工具
│   ├── ghfast.py
│   ├── build.py              # 打包 dist/ghfast.pyz
│   ├── install.sh / install.ps1
│   ├── launchers/
│   ├── vendor/
│   └── README.md
├── tests/
│   ├── test_ghfast.py        # 30 个单元测试
│   └── test_notebook.py      # 端到端执行 notebook
└── .github/workflows/ci.yml
```

## 环境要求

| | 版本 | 说明 |
|---|---|---|
| Python | 3.8+ | notebook 与工具兼容 |
| NumPy | 1.21+ | 唯一硬依赖 |
| Matplotlib | 3.5+ | 可选，绘图 |
| Pillow | 9.0+ | 可选，读取本地照片 |
| 操作系统 | Windows、macOS、Linux | CI 三系统均测 |

## CI

每次 push 与 PR 在 Windows、macOS、Ubuntu 与 Python 3.8、3.10、3.12 的组合上运行：单元测试、ghfast 自检、zipapp 打包，以及 notebook 的完整执行。

## License

[MIT](LICENSE)
