#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python 精简版：不装任何第三方库也能跑完猫狗识别。

电脑上没有 numpy 时由 run.py 自动调用：

    python3 run_lite.py
    python3 run_lite.py --fast

为了在纯 Python 里跑得动，网络比完整课程小：16x16 灰度图，4 个 3x3 卷积核，
2x2 最大池化，两层全连接，参数六百多个。结构与完整课程一致。
"""

import math
import random
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

IMG = 16
KS = 3
K = 4                 # 卷积核数量
OUT = (IMG - KS) // 2 + 1     # 卷积后边长
POOL = OUT // 2               # 池化后边长
H = 16                # 隐藏层宽度

FAST = "--fast" in sys.argv[1:]
N_TRAIN = 60 if FAST else 150
N_VAL = 40 if FAST else 80
EPOCHS = 1 if FAST else 3
BATCH = 16
LR = 2e-3
SEED = 0


def make_image(label, rng):
    """画一张 16x16 的猫或狗：猫尖耳加横胡须，狗垂耳加短口鼻。"""
    img = [[0.08 * rng.random() for _ in range(IMG)] for _ in range(IMG)]
    cx = IMG // 2 + rng.randint(-1, 1)
    cy = IMG // 2 + rng.randint(-1, 1)
    r = 4 + rng.randint(0, 1)

    for y in range(IMG):
        for x in range(IMG):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                img[y][x] = 0.7 + 0.1 * rng.random()

    if label == 0:                                    # 猫：两只尖耳
        for side in (-1, 1):
            ex = cx + side * 3
            for y in range(max(0, cy - r - 2), max(0, cy - r + 2)):
                for x in range(ex - 1, ex + 2):
                    if 0 <= x < IMG:
                        img[y][x] = 0.15
        for k in range(3):                             # 横向胡须，贯穿整行
            yy = cy + k - 1
            if 0 <= yy < IMG:
                for x in range(IMG):
                    img[yy][x] = 0.95
    else:                                              # 狗：两侧垂耳
        for side in (-1, 1):
            ex = cx + side * r
            for y in range(max(0, cy - 2), min(IMG, cy + r + 2)):
                for x in (ex - 1, ex):
                    if 0 <= x < IMG:
                        img[y][x] = 0.15
        for y in range(cy + 1, min(IMG, cy + 5)):      # 短口鼻，亮色方块
            for x in range(max(0, cx - 2), min(IMG, cx + 3)):
                img[y][x] = 0.95
    return img


def make_data(n, rng):
    xs, ys = [], []
    for label in (0, 1):
        for _ in range(n):
            xs.append(make_image(label, rng))
            ys.append(label)
    order = list(range(len(xs)))
    rng.shuffle(order)
    return [xs[i] for i in order], [ys[i] for i in order]


def zeros(shape):
    """按形状生成全零列表；一维时直接生成一列浮点数。"""
    if isinstance(shape, int):
        return [0.0] * shape
    if len(shape) == 1:
        return [0.0] * shape[0]
    return [zeros(shape[1:]) for _ in range(shape[0])]


def randn(shape, rng, scale):
    """按形状生成正态随机数，用于权重初始化。"""
    if isinstance(shape, int):
        return [rng.gauss(0.0, scale) for _ in range(shape)]
    if len(shape) == 1:
        return [rng.gauss(0.0, scale) for _ in range(shape[0])]
    return [randn(shape[1:], rng, scale) for _ in range(shape[0])]


def forward(img, p):
    w1, b1, w2, b2, w3, b3 = p
    conv = [0.0] * (K * OUT * OUT)
    for f in range(K):
        for oy in range(OUT):
            for ox in range(OUT):
                s = b1[f]
                for ky in range(KS):
                    row = img[2 * oy + ky]
                    for kx in range(KS):
                        s += w1[f][ky][kx] * row[2 * ox + kx]
                conv[(f * OUT + oy) * OUT + ox] = s if s > 0 else 0.0

    # 最大池化：记录最大值来自哪个位置，反传要用
    pooled, argmax = [0.0] * (K * POOL * POOL), [0] * (K * POOL * POOL)
    for f in range(K):
        for py in range(POOL):
            for px in range(POOL):
                best, pos = -1e9, 0
                for dy in range(2):
                    for dx in range(2):
                        v = conv[(f * OUT + py * 2 + dy) * OUT + px * 2 + dx]
                        if v > best:
                            best, pos = v, dy * 2 + dx
                pooled[(f * POOL + py) * POOL + px] = best
                argmax[(f * POOL + py) * POOL + px] = pos

    hidden = [0.0] * H
    for j in range(H):
        s = b2[j]
        for i in range(K * POOL * POOL):
            s += w2[j][i] * pooled[i]
        hidden[j] = s if s > 0 else 0.0

    logits = [b3[o] for o in range(2)]
    for o in range(2):
        for j in range(H):
            logits[o] += w3[o][j] * hidden[j]
    return conv, argmax, pooled, hidden, logits


def softmax(logits):
    m = max(logits)
    e = [math.exp(v - m) for v in logits]
    s = sum(e)
    return [v / s for v in e]


def backward(img, label, cache, p, g):
    w1, b1, w2, b2, w3, b3 = p
    conv, argmax, pooled, hidden, logits = cache
    prob = softmax(logits)

    d_logits = prob[:]
    d_logits[label] -= 1.0

    d_hidden = [0.0] * H
    for o in range(2):
        for j in range(H):
            g[4][o][j] += d_logits[o] * hidden[j]
            d_hidden[j] += d_logits[o] * w3[o][j]
        g[5][o] += d_logits[o]

    d_pooled = [0.0] * (K * POOL * POOL)
    for j in range(H):
        if hidden[j] <= 0.0:
            continue
        for i in range(K * POOL * POOL):
            g[2][j][i] += d_hidden[j] * pooled[i]
            d_pooled[i] += d_hidden[j] * w2[j][i]
        g[3][j] += d_hidden[j]

    d_conv = [0.0] * (K * OUT * OUT)
    for f in range(K):
        for py in range(POOL):
            for px in range(POOL):
                idx = (f * POOL + py) * POOL + px
                dy, dx = divmod(argmax[idx], 2)
                d_conv[(f * OUT + py * 2 + dy) * OUT + px * 2 + dx] += d_pooled[idx]

    for f in range(K):
        for oy in range(OUT):
            for ox in range(OUT):
                d_out = d_conv[(f * OUT + oy) * OUT + ox]
                if d_out == 0.0 or conv[(f * OUT + oy) * OUT + ox] <= 0.0:
                    continue
                g[1][f] += d_out
                for ky in range(KS):
                    row = img[2 * oy + ky]
                    for kx in range(KS):
                        g[0][f][ky][kx] += d_out * row[2 * ox + kx]


def adam_step(p, g, m, v, t):
    for i in range(len(p)):
        if isinstance(p[i], list):
            adam_step(p[i], g[i], m[i], v[i], t)
            continue
        m[i] = 0.9 * m[i] + 0.1 * g[i]
        v[i] = 0.999 * v[i] + 0.001 * g[i] * g[i]
        mh = m[i] / (1.0 - 0.9 ** t)
        vh = v[i] / (1.0 - 0.999 ** t)
        p[i] -= LR * mh / (math.sqrt(vh) + 1e-8)


def add_grads(g, gb):
    for i in range(len(g)):
        if isinstance(g[i], list):
            add_grads(g[i], gb[i])
            continue
        for k in range(len(g[i])):
            g[i][k] += gb[i][k]


def evaluate(xs, ys, p):
    right = 0
    matrix = [[0, 0], [0, 0]]
    for img, y in zip(xs, ys):
        cache = forward(img, p)
        pred = 0 if cache[4][0] > cache[4][1] else 1
        matrix[y][pred] += 1
        right += pred == y
    return right / len(xs), matrix


def main():
    rng = random.Random(SEED)
    print("=" * 60)
    print("猫狗识别 · 纯 Python 精简版（无需安装任何第三方库）")
    if FAST:
        print("快速模式：只跑 1 个 epoch")
    print("=" * 60)

    t0 = time.time()
    x_tr, y_tr = make_data(N_TRAIN, rng)
    x_va, y_va = make_data(N_VAL, rng)
    print("训练集 %d 张，验证集 %d 张，图片 %dx%d 灰度"
          % (len(x_tr), len(x_va), IMG, IMG))

    # He 初始化：方差按输入个数缩放，ReLU 才不会一开始就全死
    p = [randn((K, KS, KS), rng, math.sqrt(2.0 / (KS * KS))), zeros(K),
         randn((H, K * POOL * POOL), rng, math.sqrt(2.0 / (K * POOL * POOL))), zeros(H),
         randn((2, H), rng, math.sqrt(2.0 / H)), zeros(2)]
    g = [zeros((K, KS, KS)), zeros(K),
         zeros((H, K * POOL * POOL)), zeros(H),
         zeros((2, H)), zeros(2)]
    m = [zeros((K, KS, KS)), zeros(K),
         zeros((H, K * POOL * POOL)), zeros(H),
         zeros((2, H)), zeros(2)]
    v = [zeros((K, KS, KS)), zeros(K),
         zeros((H, K * POOL * POOL)), zeros(H),
         zeros((2, H)), zeros(2)]

    n_params = K * KS * KS + K + H * K * POOL * POOL + H + 2 * H + 2
    print("参数总量 %d" % n_params)

    index = list(range(len(x_tr)))
    t = 0
    for epoch in range(1, EPOCHS + 1):
        rng.shuffle(index)
        total_loss = 0.0
        for start in range(0, len(index), BATCH):
            batch = index[start:start + BATCH]
            for i in range(6):
                reset(g[i])
            for n in batch:
                img, y = x_tr[n], y_tr[n]
                cache = forward(img, p)
                prob = softmax(cache[4])
                total_loss -= math.log(prob[y] + 1e-12)
                backward(img, y, cache, p, g)
            for i in range(len(g)):
                scale_grads(g[i], 1.0 / len(batch))
            t += 1
            adam_step(p, g, m, v, t)
        acc_tr, _ = evaluate(x_tr, y_tr, p)
        acc_va, _ = evaluate(x_va, y_va, p)
        print("epoch %d/%d  loss %.4f  train %.3f  val %.3f"
              % (epoch, EPOCHS, total_loss / max(1, len(x_tr)), acc_tr, acc_va))

    acc, matrix = evaluate(x_va, y_va, p)
    print("\n验证集准确率 %.4f" % acc)
    print("混淆矩阵（行=真实，列=预测）")
    print("            pred cat  pred dog")
    print("真实 cat    %8d %9d" % (matrix[0][0], matrix[0][1]))
    print("真实 dog    %8d %9d" % (matrix[1][0], matrix[1][1]))
    print("耗时 %.1f 秒" % (time.time() - t0))
    print("=" * 60)
    print("运行结束，验证集准确率 %.4f" % acc)
    print("=" * 60)
    return 0


def reset(container):
    for i in range(len(container)):
        if isinstance(container[i], list):
            reset(container[i])
        else:
            container[i] = 0.0


def scale_grads(container, factor):
    for i in range(len(container)):
        if isinstance(container[i], list):
            scale_grads(container[i], factor)
        else:
            container[i] *= factor


if __name__ == "__main__":
    raise SystemExit(main())
