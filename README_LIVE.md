# 牌桌军师 · Android 实时视觉模式

这组文件是给现有 `index.html` 加的“外挂层”。原来的评牌、蒙特卡洛、范围和建议逻辑不需要重写；`live.html` 在同源 iframe 里打开原页面，再把视觉服务识别到的状态写入原页面的 `slots / nOpp / potInput / callInput`，随后调用原来的 `scheduleCompute()`。

## 文件放置

把本目录全部文件复制到你现有仓库根目录，**保留原来的 `index.html`**：

```
paizhuo-junshi/
├─ index.html                # 你原来的最新版
├─ live.html                 # 新：实时总控页面
├─ vision_server.py          # 新：本地服务 + ADB 截屏
├─ vision_core.py            # 新：识别、OCR、稳定器
├─ calibrate.py              # 新：框选每个区域
├─ learn_templates.py        # 新：学习点数/花色模板
├─ config.example.json
├─ requirements.txt
├─ setup.bat
└─ run.bat
```

## 1. Windows 准备

- Python 3.10+。
- Android Platform Tools，确保命令行运行 `adb devices` 能看到手机。
- 手机打开 USB 调试，并允许这台电脑调试。

双击 `setup.bat` 安装 Python 依赖。

## 2. 标定屏幕区域

把手机保持在牌桌主界面，运行：

```bash
python calibrate.py
```

按提示依次框出：2 个底牌位置、5 个公共牌位置、底池数字、跟注金额、剩余玩家人数。

区域坐标以屏幕比例保存，所以手机分辨率不变时可以一直复用。

## 3. 学习牌面字形

运行：

```bash
python learn_templates.py
```

它会依次显示已标定的牌位。输入当前看到的牌，例如：

- `As` = A♠
- `Th` = 10♥
- `Qd` = Q♦
- `7c` = 7♣

空牌位直接回车。模板按“点数”和“花色”分开学，所以不是必须收集 52 张完整牌；目标是最终覆盖 13 个点数 + 4 个花色。相同点数/花色可以多存几个样本，匹配会更稳。

## 4. 开实时模式

双击 `run.bat`，浏览器打开：

```
http://127.0.0.1:8765/
```

左边是你原来的“牌桌军师”，右边是手机截图和识别状态。视觉服务默认约 3 FPS；一组牌连续 3 帧一致才会写入军师，避免发牌动画时误判。

## 状态接口

`GET /api/state` 示例：

```json
{
  "ok": true,
  "hole": ["As", "Kh"],
  "board": ["Qh", "Jh", "2c"],
  "players": 4,
  "pot": 38,
  "call": 8,
  "hero_turn": true,
  "confidence": 0.91,
  "stable": true
}
```

## 识别不准时

1. 首先重新运行 `calibrate.py`，框尽量只包含牌面本身，不要把头像/动画一起框进去。
2. 多运行几次 `learn_templates.py`，为同一个点数、花色增加 2~4 个不同桌面/亮度下的样本。
3. `config.json` 中 `template_threshold` 默认 `0.72`：误识别多就提高到 `0.78~0.85`；经常识别不到则适当降低。
4. 如果牌左上角的点数/花色位置不是默认布局，调整 `card_inner_boxes.rank` 与 `card_inner_boxes.suit` 四个比例坐标。

## 边界

这版只负责读取屏幕和给出建议，不执行自动点击，也不包含隐藏进程、反检测或规避平台限制的逻辑。
