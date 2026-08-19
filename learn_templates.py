from __future__ import annotations

import time
from pathlib import Path

import cv2

from vision_core import ROOT, RANKS, SUITS, capture_android, inner_crop, load_config, roi_px

CFG_PATH = ROOT / "config.json"


def save_sample(folder: Path, label: str, img):
    folder.mkdir(parents=True, exist_ok=True)
    ts = int(time.time() * 1000)
    p = folder / f"{label}__{ts}.png"
    cv2.imwrite(str(p), img)
    print("保存", p.relative_to(ROOT))


def main():
    cfg = load_config(CFG_PATH)
    rois = cfg.get("rois") or {}
    all_rois = list(rois.get("hole") or []) + list(rois.get("board") or [])
    if len(all_rois) < 2:
        raise SystemExit("请先运行 python calibrate.py")
    inner = cfg.get("card_inner_boxes") or {}
    rank_box = inner.get("rank", [0.02, 0.02, 0.38, 0.30])
    suit_box = inner.get("suit", [0.02, 0.25, 0.38, 0.52])

    frame = capture_android(cfg)
    print("依次看每个牌位。输入牌名，例如 As / Th / Qd / 7c；空着回车=这个位置没牌或不想学习。")
    for i, r in enumerate(all_rois):
        card = roi_px(frame, r)
        if card is None:
            continue
        win = f"card-{i+1}"
        cv2.imshow(win, card)
        cv2.waitKey(150)
        label = input(f"牌位 {i+1}: ").strip()
        cv2.destroyWindow(win)
        if not label:
            continue
        label = label[0].upper() + label[1:].lower() if len(label) >= 2 else label
        if len(label) != 2 or label[0] not in RANKS or label[1] not in SUITS:
            print("格式不对，跳过；正确示例 As / Th / Qd / 7c")
            continue
        save_sample(ROOT / "templates" / "ranks", label[0], inner_crop(card, rank_box))
        save_sample(ROOT / "templates" / "suits", label[1], inner_crop(card, suit_box))
    print("学习完成。重复运行几次，尽量把 13 个点数和 4 个花色都收齐；同一标签多存几个样本会更稳。")


if __name__ == "__main__":
    main()
