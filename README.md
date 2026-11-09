# 课程教学

用 NumPy 从零实现一个卷积网络，做猫狗图片分类。不用框架，不下载数据，装了 Python 就能跑。

- 想马上跑起来：[开始使用.md](开始使用.md)
- 想看每一步在算什么：打开 [`猫狗识别.ipynb`](猫狗识别.ipynb)
- 没有 Jupyter：`python3 run.py`

## 五分钟跑起来

### 第一步，拿到文件

直接下载压缩包：

```
https://github.com/yingzhou-bjtu/course-teaching/archive/refs/heads/main.zip
```

也可以在仓库页面点 `Code` → `Download ZIP`。解压得到一个文件夹。如果拿到的是别人给的压缩包，直接解压即可。

### 第二步，进入这个文件夹

打开终端，切到刚解压的目录：

```bash
cd 下载路径/course-teaching-main
```

Windows 用 PowerShell 或命令提示符，路径里有空格时整个路径加引号。

### 第三步，运行

```bash
python3 run.py
```

Windows 上多数情况下命令是 `python run.py`。哪个能跑通用哪个，后面都同一个规则。

十几秒后结束，最后一行打印验证集准确率。

## 你会看到什么

真实输出，节选：

```
Python: 3.10.12 | NumPy: 1.26.4
数据模式: toy | 尺寸: 32x32
照片目录: data/sample | 教学图目录: figures
训练集 X: (2000, 3, 32, 32)  y: (2000,)
验证集 X: (600, 3, 32, 32)  y: (600,)
...
参数总量：132850（约 13.3 万）
最大相对误差 2.76e-03
epoch  1/4  loss 0.0939  训练 1.000  验证 1.000  (2.6s)
epoch  4/4  loss 0.0000  训练 1.000  验证 1.000  (3.2s)
照片: (16, 3, 96, 96) 来源: data/sample（从磁盘读取）
教学图已保存: figures/01_samples.png
教学图已保存: figures/02_conv_kernels.png
教学图已保存: figures/03_training_curves.png
教学图已保存: figures/04_confusion_matrix.png
教学图已保存: figures/05_predictions.png
总训练时间 11.1 秒
验证集准确率: 1.0000  (600/600)
混淆矩阵（行=真实，列=预测）
          预测猫  预测狗
真实猫      300       0
真实狗        0     300
运行结束，验证集准确率 1.0000
```

三行关键数字的含义：

（1）`训练集 X: (2000, 3, 32, 32)` 表示两千张 32x32 的彩色图，通道在前。

（2）`最大相对误差` 是梯度检验的结果，千分之一量级说明反向传播写对了。

（3）`验证集准确率` 是六百张没参与训练的图上算出来的。

准确率到 100% 不是造假。样本由程序生成，两类差异明显，网络几十步就分开了。换成真实照片会明显下降，原因在第 7 步解释。

## 两种运行模式

程序会自己选，你不用管。

| | 完整模式 | 精简模式 |
|---|---|---|
| 前提 | 装了 numpy | 只装 Python，什么都不用装 |
| 输入 | 32x32 彩色图 | 16x16 灰度图 |
| 参数 | 132850 | 666 |
| 耗时 | 本机约 13 秒，慢一些的二三十秒 | 1 秒内 |
| 跑法 | `python3 run.py` | `python3 run.py`（自动） |

只想确认环境通不通，用：

```bash
python3 run.py --fast
```

一秒多结束，准确率八成左右，因为只训练一个 epoch。

## 常见问题

**提示 `python3: command not found` 或 `不是内部或外部命令`**

Windows 上一般是 `python run.py`。如果 `python` 和 `python3` 都没有，说明 Python 没装好，去 python.org 装一个，安装时勾选 `Add Python to PATH`。

**提示 `No module named 'numpy'`**

不影响运行，程序会自动切到精简模式。想要完整模式，用国内镜像装一次：

```bash
python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy
```

**提示 `No module named pip`**

先用精简模式跑，`python3 run.py` 一样出结果。要装 numpy 再执行 `python3 -m ensurepip --upgrade`。

**服务器不能联网**

在任意一台能上网的电脑上执行下面这条，把生成的 `vendor` 目录拷到服务器，再执行第二条：

```bash
python3 -m pip download numpy -d vendor --only-binary=:all: -i https://pypi.tuna.tsinghua.edu.cn/simple
python3 -m pip install --no-index --find-links vendor numpy
```

**Windows 控制台中文乱码**

程序已经把输出切到 UTF-8。仍然乱码时，在命令提示符里先执行 `chcp 65001`。

**运行太慢**

用 `python3 run.py --fast`。或者在第一个单元格把 `FAST_DEMO` 改成 `True`，样本降到 64 张。

**想看训练曲线**

```bash
python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple matplotlib
```

装完重跑 `python3 run.py`，会多出两张图。图注是英文，避免机器缺中文字体显示成方块。不装也能跑完，只是没有图。

## notebook 里有什么

| 步骤 | 你会做什么 | 跑完看到什么 |
|---|---|---|
| 0 | 检查版本，设定参数 | Python 与 numpy 版本号 |
| 1 | 生成两千张猫狗样本 | 形状、像素范围、耗时 |
| 2 | 标准化、打乱 | 标准化后的数值范围 |
| 3 | 手算一次卷积，再看固定核扫过一张图 | 特征图，边缘被点亮 |
| 4 | 实现 im2col、卷积、池化、交叉熵、Adam | 每层的输出形状与数值 |
| 5 | 搭网络，做梯度检验 | 数值梯度与解析梯度的相对误差 |
| 6 | 训练 | 每个 epoch 的损失与准确率 |
| 7 | 评估 | 混淆矩阵、九个预测样本 |
| 8 | 数据增强对比 | 两次训练的准确率 |

每个代码格子开头都有中文注释，说明这一格在做什么。参数集中在第一个单元格，改完重跑即可。

## 预置的真实照片与教学图

仓库里放了 16 张真实照片，猫狗各 8 张，都是 160x160 的 JPEG：

```
data/sample/cat/cat_00.jpg ... cat_07.jpg
data/sample/dog/dog_00.jpg ... dog_07.jpg
```

挑这 16 张不是为了好看，是为了让“同一类东西长得能差多远”具体可见：

- **毛色和纹理**：全黑侧脸、黑白花、橘色虎斑、三花、黑色卷毛、哈士奇脸纹
- **姿态**：蜷成一团睡觉、跑起来拉长、只剩一个脑袋的特写
- **光照**：夜里曝光不足、雪地背景和毛色几乎一样白、逆光
- **构图与干扰**：背景里多一只蜥蜴、两只挤在一格、远处只剩几十像素

每张的照片来源、作者、许可以及它想体现的特性，都写在 `data/sample/README.md` 里。图片来自 Wikimedia Commons，选的是公共领域或 CC 授权，压缩后总共约 110 KB。

课程第 1 步会把这些照片从磁盘读回来，显示成 `figures/01_samples.png` 那张网格图，标题上写着 `samples from data/sample`。训练用的两千张仍然是程序画的，所以第一次运行不用联网、不用下载数据集；这 16 张的作用是让你看见真实照片有多“不规整”。

想换掉其中某张：同名覆盖即可，代码不用改。`tests/test_sample_data.py` 会检查文件、尺寸，以及许可表是否和文件名一一对应。

运行结束后，`figures/` 里会有五张教学图，可以直接拿去上课或交作业：

| 文件 | 内容 |
|---|---|
| `01_samples.png` | 16 张真实照片，两行八列 |
| `02_conv_kernels.png` | 同一张图被竖直边缘、水平边缘、模糊三种卷积核扫过 |
| `03_training_curves.png` | 损失下降曲线 + 训练/验证准确率差距 |
| `04_confusion_matrix.png` | 混淆矩阵热力图 |
| `05_predictions.png` | 九张验证图的预测结果，对错标红绿 |

`figures/` 里是运行产物，已经写进 `.gitignore`，不会提交。示例图用的是英文标注，避免缺中文字体。

## 用真实的猫狗照片

把第一个单元格的 `DATA_MODE` 改成 `folder`，照片按下面的结构放：

```
data/cats_dogs/cat/001.jpg
data/cats_dogs/cat/002.jpg
...
data/cats_dogs/dog/001.jpg
...
```

要求：

（1）每类建议一百张以上。样本太少时准确率不稳定，也更难看出过拟合。

（2）jpg、png 都行，尺寸不限，程序会统一缩放到 32x32。

（3）读取照片需要 Pillow：`python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pillow`。

（4）真实照片的准确率明显低于合成数据，这是正常的，正是这门课要讲的重点。

## 学完可以做什么

（1）把输出层从 2 改成 10，换十个类别，看准确率怎么变。

（2）把网络加深一层，观察训练时间和准确率的变化。

（3）同样的网络用框架写一遍，大约三十行，对比代码量和训练速度，就知道框架替你做了什么。

（4）觉得手写太慢，说明该换框架了；觉得看不懂框架在干什么，回到这里再看一遍。

## 环境要求

| | 要求 | 说明 |
|---|---|---|
| Python | 3.8 以上 | 3.8、3.10、3.12 在 CI 上实测 |
| NumPy | 1.21 以上 | 完整模式需要，精简模式不需要 |
| Matplotlib | 3.5 以上 | 可选，画训练曲线 |
| Pillow | 9.0 以上 | 可选，读真实照片 |
| 系统 | Windows、macOS、Linux | 三系统都有 CI |
| 显卡 | 不需要 | 纯 CPU，十余秒 |

## 目录结构

```
course-teaching/
├── 开始使用.md            # 新手入口，三五句话说完
├── 猫狗识别.ipynb         # 主线课程，八个步骤
├── run.py                 # 不用 Jupyter 的运行入口
├── run_lite.py            # 纯 Python 精简版，零依赖
├── requirements.txt       # numpy（matplotlib、pillow 可选）
├── data/sample/           # 16 张真实照片：猫狗各 8 张 160x160 JPEG
├── figures/               # 运行生成的教学图（不提交）
├── vendor/                # 离线 wheel 存放处，默认空
├── ghfast/
│   ├── ghfast.py          # GitHub 加速与诊断
│   ├── build.py           # 打包成单文件 ghfast.pyz
│   ├── install.sh
│   ├── install.ps1
│   ├── launchers/
│   ├── vendor/
│   └── README.md
├── tests/
│   ├── test_notebook.py   # 端到端执行 notebook
│   ├── test_run.py        # 两个入口的冒烟测试
│   └── test_ghfast.py     # ghfast 三十项单元测试
└── .github/workflows/ci.yml
```

## 二、ghfast

只有一种情况用得上：要装包、要下载仓库，但 GitHub 连不上。平时跑课程不需要它。

```bash
python3 ghfast/ghfast.py doctor --timeout 1   # 判断卡在 DNS、TLS 还是线路，约一分半
python3 ghfast/ghfast.py mirrors --timeout 1  # 查看当前可用镜像，约半分钟
python3 ghfast/ghfast.py download <url> -O out.bin
```

`doctor` 要逐个探测十几个域名，默认每个等六秒，网络差时可能要好几分钟，加上 `--timeout 1` 快很多。

只用 Python 标准库，三个系统通用，详见 [ghfast/README.md](ghfast/README.md)。

## 测试与 CI

自己验证一遍：

```bash
python3 -m unittest discover -s tests -v
```

每次 push 会在 Windows、macOS、Linux 与 Python 3.8、3.10、3.12 的组合上跑：单元测试、两个运行入口、ghfast 自检、打包，以及 notebook 的完整执行。

## License

[MIT](LICENSE)
