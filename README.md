# 牌桌军师

德州扑克实时胜率计算与决策助手。纯前端单文件，本地计算，不联网。

**在线使用：** https://gebilaomao666-droid.github.io/paizhuo-junshi/

## 功能

- **算牌** — 两步选牌（点数字→点花色），实时算胜率、底池赔率，给出弃牌/跟注/加注建议
- **陪练** — 内置完整 NLHE 牌局引擎，2~10 人桌，AI 对手有紧有松，轮到你时军师直接支招
- **起手表** — 169 手起手牌按强度五档着色，点开看每档打法
- **秘籍 / 规则** — 铁律、数字真相、对手类型、牌型排行、常见误区
- **实时视觉** — Android 通过 ADB、iPhone 通过 Windows AirPlay 投屏窗口自动识别；详见 [README_LIVE.md](README_LIVE.md)

## 文件

| 文件 | 说明 |
|---|---|
| `index.html` | 成品页面，HTML+CSS+JS 全内联，双击即可运行 |
| `engine.js` | 核心引擎的 Node 版（评牌 + 蒙特卡洛 + 对手范围） |
| `test_engine.js` | 30 项测试：牌型判定、大小比较、公认胜率基准校验 |
| `ranking169.json` | 169 手起手牌按全下胜率降序排列 |
| `live.html` | Android / iPhone 实时视觉总控页面 |
| `vision_core.py` | ADB、Windows 投屏窗口采集与牌面识别 |
| `README_LIVE.md` | 双端安装、标定与使用说明 |

## 引擎说明

牌用 0–51 整数表示：`rank = c >> 2`（0=2 … 12=A），`suit = c & 3`（0♠ 1♥ 2♦ 3♣）。

- `evaluate7(cards)` — 7 张取最优 5 张，返回可直接比大小的整数分值
- `simulate(hole, board, nOpp, iters, allowed, bluffP, restAllowed, tightN)` — 蒙特卡洛胜率。`allowed` 为 52×52 对手范围矩阵，`bluffP` 为诈唬混合概率，`restAllowed`/`tightN` 支持分组建模（如 1 人下重注 + 其余正常）
- `buildAllowed(pct, ranked)` — 把「最强前 pct% 起手牌」编成范围矩阵

平分底池按参与人数 1/k 计入 equity（非简单对半）。

## 验证

```bash
node test_engine.js
```

30 项全过。胜率对照独立 2000 万局/手模拟与 PokerStove 公布值校准：

| 手牌 | 对 8 个随机对手 | 基准 |
|---|---|---|
| AA | 34.58% | 34.61% |
| KK | 29.25% | 29.18% |
| AKs | 22.65% | 22.65% |
| 22 | 12.50% | 12.51% |
| 72o | 5.36% | 5.39% |

## 使用范围

学习、复盘、陪练与线下自娱。请勿用于违反所在平台规则的场合。
