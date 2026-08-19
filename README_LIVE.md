# 牌桌军师 · Android / iPhone 实时视觉模式

这组文件是给现有 `index.html` 加的实时视觉层。原来的评牌、蒙特卡洛、范围和建议逻辑不需要重写；`live.html` 在同源 iframe 里打开原页面，再把视觉服务识别到的状态写入原页面的 `slots / nOpp / potInput / callInput`，随后调用原来的 `scheduleCompute()`。

程序默认使用 `capture_mode: "auto"`：有可用的 Android ADB 就直接截手机；否则自动寻找 Windows 上的 iPhone AirPlay 投屏窗口。日常使用不需要手动切模式。

## 文件放置

把本目录全部文件复制到你现有仓库根目录，**保留原来的 `index.html`**：

```
paizhuo-junshi/
├─ index.html                # 你原来的最新版
├─ live.html                 # 新：实时总控页面
├─ vision_server.py          # 新：本地服务 + 自动选择画面来源
├─ vision_core.py            # 新：识别、OCR、稳定器
├─ calibrate.py              # 新：框选每个区域
├─ learn_templates.py        # 新：学习点数/花色模板
├─ config.example.json
├─ requirements.txt
├─ setup.bat
└─ run.bat
```

## 1. 一次性准备

- Python 3.10+。
- Android：安装 Android Platform Tools，打开 USB 调试，并确保 `adb devices` 能看到手机。
- iPhone：在 Windows 安装一个 AirPlay 接收器。默认会自动识别 `AirDroid Cast / LetsView / ApowerMirror / LonelyScreen / 5KPlayer` 窗口。

双击 `setup.bat` 安装 Python 依赖。

### iPhone 最短操作

首次只需安装一次 Windows 版 [AirDroid Cast](https://www.airdroid.com/download/airdroid-cast/)。之后每次：

1. 电脑打开 AirDroid Cast，电脑与 iPhone 接入同一 Wi-Fi。
2. iPhone 从右上角下拉控制中心，点“屏幕镜像”，选择 `AirDroid Cast - 电脑名`。
3. 双击本项目的 `run.bat`。页面会自动打开并显示 `iPhone · AirDroid Cast`。

投屏窗口不要最小化。若使用其他接收器，把它的窗口标题关键词加入 `config.json` 的 `window_title_keywords` 即可。

## 2. 标定屏幕区域

把手机保持在牌桌主界面。Android 先连好 USB；iPhone 先完成投屏。然后运行：

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

双击 `run.bat`，浏览器会自动打开：

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
  "stable": true,
  "source": "iPhone · AirDroid Cast"
}
```

## 识别不准时

1. 首先重新运行 `calibrate.py`，框尽量只包含牌面本身，不要把头像/动画一起框进去。iPhone 投屏窗口改过大小后也应重新标定。
2. 多运行几次 `learn_templates.py`，为同一个点数、花色增加 2~4 个不同桌面/亮度下的样本。
3. `config.json` 中 `template_threshold` 默认 `0.72`：误识别多就提高到 `0.78~0.85`；经常识别不到则适当降低。
4. 如果牌左上角的点数/花色位置不是默认布局，调整 `card_inner_boxes.rank` 与 `card_inner_boxes.suit` 四个比例坐标。

## 边界

这版只负责读取屏幕和给出建议，不执行自动点击，也不包含隐藏进程、反检测或规避平台限制的逻辑。部分应用可能主动禁止系统投屏或截屏；遇到黑屏时程序无法绕过该限制。
