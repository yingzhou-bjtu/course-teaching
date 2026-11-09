# data/sample 里的 16 张真实照片

这些图都来自 Wikimedia Commons，挑了公共领域或 CC 授权的照片，每张压到 160×160 的 JPEG（总共 110 KB），方便放进仓库。

课程里把它们读回来显示成一张网格图（`figures/01_samples.png`）。训练用的两千张仍然是程序画的，所以第一次运行不用联网、不用下数据集。

挑这 16 张不是为了好看，是为了让“同一类东西的样子可以差很远”这件事具体可见：

| 文件 | 画面里有什么 | 想让你注意的特性 | 作者 | 许可 |
|---|---|---|---|---|
| `cat/cat_00.jpg` | File:Black Cat - Tim.jpg | 黑猫侧脸，白色纯背景：轮廓清晰、背景无干扰 | Warriorprincessdi | CC BY-SA 3.0 |
| `cat/cat_01.jpg` | File:BLACK-WHITE-CAT-SITIA-CRETE.jpg | 黑白花猫趴在门口台阶上：同一只猫两种毛色，白斑位置不规则 | Petro Stelte | CC BY-SA 4.0 |
| `cat/cat_02.jpg` | File:Orange Tabby Cat 2.jpg | 橘色虎斑幼猫在室内：暖色调灯光，条纹是主要线索 | Kalel Tonatiuh | CC BY-SA 3.0 |
| `cat/cat_03.jpg` | File:Calico cat, - Assisi, Italy.jpg | 三花猫坐在地上：三块颜色分明，纹理比轮廓更显眼 | Terragio67 | CC BY-SA 4.0 |
| `cat/cat_04.jpg` | File:Cat-sleeping-curled-up.jpg | 蜷成一团睡觉：姿态完全变了，只剩一团毛 | Sonkiki | CC0 |
| `cat/cat_05.jpg` | File:Black and gray mackerel tabby cat at night in Tuntorp 1 | 夜里的虎斑猫：曝光不足、暗部糊成一片，明暗对比很弱 | W.carter | CC BY-SA 4.0 |
| `cat/cat_06.jpg` | File:Cat playing with a lizard.jpg | 猫在草丛里拨弄一只蜥蜴：背景杂、还多了个干扰物体 | Basile Morin | CC BY-SA 4.0 |
| `cat/cat_07.jpg` | File:Kittens resting close together for warmth and security. | 两只小猫挤在一起：一格里不止一个目标 | Kitten Goes Meow | CC0 |
| `dog/dog_00.jpg` | File:A Golden Retriever-9 (Barras).JPG | 金毛躺在草地上：长毛、逆光，边缘有亮边 | Barras | CC BY 3.0 |
| `dog/dog_01.jpg` | File:Seva-5.jpg | 哈士奇正面，浅灰背景：面部斑纹左右不对称 | Кугуракова Влада | Public domain |
| `dog/dog_02.jpg` | File:Black and white dog in the snow (50899369822).jpg | 雪地里的黑白狗在跑：背景和毛色都接近白色，轮廓难分 | Joseph Gage from Yorkville, IL, USA | CC BY-SA 2.0 |
| `dog/dog_03.jpg` | File:Handsome Theo - Flickr - Living in Monrovia.jpg | 黑色卷毛犬：毛是密集小卷，纹理高频 | Living in Monrovia | CC BY-SA 2.0 |
| `dog/dog_04.jpg` | File:Cavapoo dog chasing a maltipoo with a ball (11881).jpg | 两只狗追球跑：运动模糊，形体被拉长 | Rhododendrites | CC BY-SA 4.0 |
| `dog/dog_05.jpg` | File:Close-up of dog looking at photographer.jpg | 狗头特写：鼻子占了画面很大一块，看不到全身 | Pittigrilli | CC BY-SA 4.0 |
| `dog/dog_06.jpg` | File:Two dogs play-fighting.jpg | 两只狗打闹：互相遮挡，边界不清 | Sarah Farris | CC BY-SA 3.0 |
| `dog/dog_07.jpg` | File:Dog Running in the Snow (3116908486).jpg | 远处沙地上的小狗：目标只占几十个像素，背景颜色和毛色相近 | Rennett Stowe from USA | CC BY 2.0 |

来源页面：
- `cat/cat_00.jpg` — None
- `cat/cat_01.jpg` — None
- `cat/cat_02.jpg` — None
- `cat/cat_03.jpg` — None
- `cat/cat_04.jpg` — None
- `cat/cat_05.jpg` — None
- `cat/cat_06.jpg` — None
- `cat/cat_07.jpg` — None
- `dog/dog_00.jpg` — None
- `dog/dog_01.jpg` — None
- `dog/dog_02.jpg` — None
- `dog/dog_03.jpg` — None
- `dog/dog_04.jpg` — None
- `dog/dog_05.jpg` — None
- `dog/dog_06.jpg` — None
- `dog/dog_07.jpg` — None

作者、许可与原始页面按上表保留。如果你的用途需要替换其中某张，直接同名覆盖即可，不影响代码；`tests/test_sample_data.py` 会检查文件、尺寸和这张许可表是否一一对应。
