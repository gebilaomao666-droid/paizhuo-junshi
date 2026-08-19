from __future__ import annotations

import json
from pathlib import Path

import cv2

from vision_core import FrameSource, ROOT, load_config

CFG_PATH = ROOT / "config.json"


def norm_roi(rect, shape):
    x, y, w, h = rect
    H, W = shape[:2]
    if w <= 0 or h <= 0:
        return None
    return [round(x / W, 6), round(y / H, 6), round((x + w) / W, 6), round((y + h) / H, 6)]


def pick(frame, title, optional=False):
    print(f"选择：{title}" + ("（可选，按 C 跳过）" if optional else ""))
    rect = cv2.selectROI(title, frame, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow(title)
    r = norm_roi(rect, frame.shape)
    if r is None and not optional:
        raise SystemExit(f"{title} 未选择，已停止。")
    return r


def main():
    cfg = load_config(CFG_PATH)
    source = FrameSource(cfg)
    print("正在自动查找 Android ADB 或 iPhone 投屏窗口……")
    frame = source.capture()
    print("已连接：", source.label)
    rois = {"hole": [], "board": []}
    for i in range(2):
        rois["hole"].append(pick(frame, f"底牌 {i+1} 的完整牌面位置"))
    for i in range(5):
        rois["board"].append(pick(frame, f"公共牌 {i+1} 的完整牌面位置"))
    rois["pot"] = pick(frame, "底池数字区域", optional=True)
    rois["call"] = pick(frame, "跟注金额数字区域", optional=True)
    rois["players"] = pick(frame, "剩余玩家人数数字区域", optional=True)
    cfg["rois"] = rois
    CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    debug_dir = ROOT / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(debug_dir / "calibration_screen.png"), frame)
    print("已写入 config.json。下一步运行 python learn_templates.py")


if __name__ == "__main__":
    main()
