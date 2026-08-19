from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

try:
    import mss
except Exception:  # optional for Android, required for Windows window capture
    mss = None

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # optional at import time, required for number OCR
    RapidOCR = None

ROOT = Path(__file__).resolve().parent
RANKS = "23456789TJQKA"
SUITS = "shdc"


def load_config(path: Path) -> dict:
    if not path.exists():
        example = ROOT / "config.example.json"
        path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def adb_cmd(cfg: dict, *args: str) -> List[str]:
    cmd = [cfg.get("adb_path") or "adb"]
    serial = (cfg.get("device_serial") or "").strip()
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return cmd


def capture_android(cfg: dict, timeout: float = 4.0) -> np.ndarray:
    cmd = adb_cmd(cfg, "exec-out", "screencap", "-p")
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or b"adb screencap failed").decode("utf-8", "ignore").strip())
    arr = np.frombuffer(p.stdout, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("无法解码手机截图")
    return frame


DEFAULT_WINDOW_KEYWORDS = [
    "AirDroid Cast",
    "LetsView",
    "ApowerMirror",
    "LonelyScreen",
    "5KPlayer",
]


def list_windows() -> List[dict]:
    """Return visible, non-minimized Windows client areas."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    windows: List[dict] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title_buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buf, length + 1)
        title = title_buf.value.strip()
        rect = wintypes.RECT()
        if not title or not user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return True
        top_left = wintypes.POINT(rect.left, rect.top)
        bottom_right = wintypes.POINT(rect.right, rect.bottom)
        if not user32.ClientToScreen(hwnd, ctypes.byref(top_left)):
            return True
        if not user32.ClientToScreen(hwnd, ctypes.byref(bottom_right)):
            return True
        width = bottom_right.x - top_left.x
        height = bottom_right.y - top_left.y
        if width >= 160 and height >= 240:
            windows.append({
                "hwnd": int(hwnd),
                "title": title,
                "left": int(top_left.x),
                "top": int(top_left.y),
                "width": int(width),
                "height": int(height),
            })
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return windows


def pick_window(windows: Sequence[dict], keywords: Sequence[str]) -> Optional[dict]:
    wanted = [str(x).strip().lower() for x in keywords if str(x).strip()]
    matches = [
        w for w in windows
        if any(k in str(w.get("title", "")).lower() for k in wanted)
    ]
    return max(matches, key=lambda w: int(w.get("width", 0)) * int(w.get("height", 0))) if matches else None


def capture_window(cfg: dict) -> Tuple[np.ndarray, str]:
    if os.name != "nt":
        raise RuntimeError("投屏窗口采集目前需要 Windows")
    if mss is None:
        raise RuntimeError("缺少窗口采集依赖，请先双击 setup.bat")
    keywords = cfg.get("window_title_keywords") or DEFAULT_WINDOW_KEYWORDS
    target = pick_window(list_windows(), keywords)
    if target is None:
        names = " / ".join(str(x) for x in keywords)
        raise RuntimeError(f"找不到苹果投屏窗口。请先打开投屏，窗口标题需包含：{names}")
    box = {k: target[k] for k in ("left", "top", "width", "height")}
    # mss.mss 与 with_cursor 参数在 Windows 上已废弃，优先用 mss.MSS()
    grabber_factory = getattr(mss, "MSS", None) or mss.mss
    with grabber_factory() as grabber:
        shot = np.asarray(grabber.grab(box), dtype=np.uint8)
    if shot.size == 0:
        raise RuntimeError("投屏窗口截图为空，请确认窗口没有最小化")
    return np.ascontiguousarray(shot[:, :, :3]), str(target["title"])


class FrameSource:
    """Choose Android ADB or an iPhone AirPlay receiver window."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        raw = str(cfg.get("capture_mode", "auto")).strip().lower()
        aliases = {"android": "adb", "iphone": "window", "ios": "window", "airplay": "window"}
        self.mode = aliases.get(raw, raw)
        if self.mode not in ("auto", "adb", "window"):
            raise ValueError("capture_mode 只能是 auto / adb / window")
        self.active_mode: Optional[str] = None
        self.label = ""

    def candidate_modes(self) -> List[str]:
        if self.mode != "auto":
            return [self.mode]
        if self.active_mode == "window":
            return ["window", "adb"]
        return ["adb", "window"]

    def capture(self) -> np.ndarray:
        errors = []
        for mode in self.candidate_modes():
            try:
                if mode == "adb":
                    frame = capture_android(self.cfg)
                    label = "Android · ADB"
                else:
                    frame, title = capture_window(self.cfg)
                    label = f"iPhone · {title}"
                self.active_mode = mode
                self.label = label
                return frame
            except Exception as exc:
                errors.append(f"{mode}: {exc}")
        self.active_mode = None
        self.label = ""
        raise RuntimeError("未找到手机画面；" + "；".join(errors))


def roi_px(frame: np.ndarray, roi: Optional[Sequence[float]]) -> Optional[np.ndarray]:
    if not roi or len(roi) != 4:
        return None
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = roi
    # config stores normalized [0,1]; accept pixel coords too for debugging
    if max(abs(float(v)) for v in roi) <= 1.5:
        x1, x2 = int(x1 * w), int(x2 * w)
        y1, y2 = int(y1 * h), int(y2 * h)
    else:
        x1, y1, x2, y2 = map(int, roi)
    x1, x2 = sorted((max(0, x1), min(w, x2)))
    y1, y2 = sorted((max(0, y1), min(h, y2)))
    if x2 - x1 < 3 or y2 - y1 < 3:
        return None
    return frame[y1:y2, x1:x2]


def inner_crop(card: np.ndarray, box: Sequence[float]) -> np.ndarray:
    h, w = card.shape[:2]
    x1, y1, x2, y2 = box
    x1, x2 = int(x1 * w), int(x2 * w)
    y1, y2 = int(y1 * h), int(y2 * h)
    x1, x2 = sorted((max(0, x1), min(w, x2)))
    y1, y2 = sorted((max(0, y1), min(h, y2)))
    return card[y1:y2, x1:x2]


def normalize_glyph(img: np.ndarray, size: int = 56) -> np.ndarray:
    if img is None or img.size == 0:
        return np.zeros((size, size), np.uint8)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # Automatically choose polarity, then crop to foreground.
    _, a = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, b = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = a if np.count_nonzero(a) < np.count_nonzero(b) else b
    ys, xs = np.where(mask > 0)
    if len(xs) < 8:
        return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    x1, x2 = xs.min(), xs.max() + 1
    y1, y2 = ys.min(), ys.max() + 1
    crop = mask[y1:y2, x1:x2]
    ch, cw = crop.shape
    scale = min((size - 8) / max(cw, 1), (size - 8) / max(ch, 1))
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    crop = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((size, size), np.uint8)
    ox, oy = (size - nw) // 2, (size - nh) // 2
    canvas[oy:oy + nh, ox:ox + nw] = crop
    return canvas


class GlyphMatcher:
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.templates: Dict[str, List[np.ndarray]] = {}
        self.reload()

    def reload(self) -> None:
        self.templates = {}
        if not self.template_dir.exists():
            return
        for p in self.template_dir.glob("*.png"):
            label = p.stem.split("__", 1)[0]
            img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                self.templates.setdefault(label, []).append(normalize_glyph(img))

    def match(self, img: np.ndarray) -> Tuple[Optional[str], float]:
        if not self.templates:
            return None, 0.0
        q = normalize_glyph(img).astype(np.float32)
        best_label, best = None, -1.0
        for label, arrs in self.templates.items():
            for t in arrs:
                # normalized correlation of equal-size images
                score = float(cv2.matchTemplate(q, t.astype(np.float32), cv2.TM_CCOEFF_NORMED)[0, 0])
                if score > best:
                    best_label, best = label, score
        return best_label, max(0.0, best)


class NumberOCR:
    def __init__(self):
        self.engine = RapidOCR() if RapidOCR is not None else None

    def read_number(self, crop: Optional[np.ndarray]) -> Optional[float]:
        if crop is None or crop.size == 0 or self.engine is None:
            return None
        try:
            result, _ = self.engine(crop)
        except Exception:
            return None
        if not result:
            return None
        text = " ".join(str(x[1]) for x in result if len(x) > 1)
        text = text.replace(",", "").replace("，", "").replace("O", "0").replace("o", "0")
        m = re.search(r"(?<!\d)(\d+(?:\.\d+)?)", text)
        return float(m.group(1)) if m else None


@dataclass
class VisionState:
    ok: bool = False
    hole: List[str] = None
    board: List[str] = None
    players: Optional[int] = None
    pot: Optional[float] = None
    call: Optional[float] = None
    hero_turn: bool = False
    confidence: float = 0.0
    stable: bool = False
    frame_id: int = 0
    captured_at: float = 0.0
    source: str = ""
    error: str = ""

    def __post_init__(self):
        if self.hole is None:
            self.hole = []
        if self.board is None:
            self.board = []

    def to_dict(self) -> dict:
        return asdict(self)


class PokerRecognizer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.rank_matcher = GlyphMatcher(ROOT / "templates" / "ranks")
        self.suit_matcher = GlyphMatcher(ROOT / "templates" / "suits")
        self.ocr = NumberOCR()
        self.threshold = float(cfg.get("template_threshold", 0.72))
        inner = cfg.get("card_inner_boxes") or {}
        self.rank_box = inner.get("rank", [0.02, 0.02, 0.38, 0.30])
        self.suit_box = inner.get("suit", [0.02, 0.25, 0.38, 0.52])

    def reload_templates(self):
        self.rank_matcher.reload()
        self.suit_matcher.reload()

    def read_card(self, card_crop: Optional[np.ndarray]) -> Tuple[Optional[str], float]:
        if card_crop is None or card_crop.size == 0:
            return None, 0.0
        rc = inner_crop(card_crop, self.rank_box)
        sc = inner_crop(card_crop, self.suit_box)
        r, rs = self.rank_matcher.match(rc)
        s, ss = self.suit_matcher.match(sc)
        if r not in RANKS or s not in SUITS:
            return None, min(rs, ss)
        score = min(rs, ss)
        if score < self.threshold:
            return None, score
        return r + s, score

    def recognize(self, frame: np.ndarray, frame_id: int, source: str = "") -> VisionState:
        rois = self.cfg.get("rois") or {}
        hole, board, scores = [], [], []
        for r in rois.get("hole") or []:
            c, s = self.read_card(roi_px(frame, r))
            if c:
                hole.append(c)
                scores.append(s)
        for r in rois.get("board") or []:
            c, s = self.read_card(roi_px(frame, r))
            if c:
                board.append(c)
                scores.append(s)

        pot = self.ocr.read_number(roi_px(frame, rois.get("pot")))
        call = self.ocr.read_number(roi_px(frame, rois.get("call")))
        pnum = self.ocr.read_number(roi_px(frame, rois.get("players")))
        players = int(pnum) if pnum is not None and 2 <= int(pnum) <= 10 else int(self.cfg.get("default_players", 9))

        cards = hole + board
        unique = len(cards) == len(set(cards))
        board_count_ok = len(board) in (0, 3, 4, 5)
        ok = len(hole) == 2 and unique and board_count_ok
        confidence = float(sum(scores) / len(scores)) if scores else 0.0
        # Call amount generally appears on the user's action controls; use it as a soft turn signal.
        hero_turn = call is not None
        return VisionState(
            ok=ok,
            hole=hole,
            board=board,
            players=players,
            pot=pot,
            call=call,
            hero_turn=hero_turn,
            confidence=confidence,
            stable=False,
            frame_id=frame_id,
            captured_at=time.time(),
            source=source,
        )


class StableState:
    def __init__(self, need: int = 3):
        self.need = max(1, int(need))
        self.sig = None
        self.count = 0
        self.last_good = VisionState(error="等待识别")

    @staticmethod
    def signature(s: VisionState):
        return tuple(s.hole), tuple(s.board), s.players

    def push(self, s: VisionState) -> VisionState:
        if not s.ok:
            s.stable = False
            return s
        sig = self.signature(s)
        if sig == self.sig:
            self.count += 1
        else:
            self.sig, self.count = sig, 1
        s.stable = self.count >= self.need
        if s.stable:
            self.last_good = s
        return s


class VisionWorker:
    def __init__(self, cfg_path: Path, overrides: Optional[dict] = None):
        self.cfg_path = cfg_path
        self.cfg = load_config(cfg_path)
        if overrides:
            self.cfg.update({k: v for k, v in overrides.items() if v is not None})
        self.frame_source = FrameSource(self.cfg)
        self.recognizer = PokerRecognizer(self.cfg)
        self.stabilizer = StableState(self.cfg.get("stable_frames", 3))
        self.lock = threading.Lock()
        self.state = VisionState(error="启动中")
        self.latest_frame: Optional[np.ndarray] = None
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.frame_id = 0

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._loop, name="vision-worker", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def get_state(self) -> dict:
        with self.lock:
            return self.state.to_dict()

    def get_jpeg(self) -> Optional[bytes]:
        with self.lock:
            frame = None if self.latest_frame is None else self.latest_frame.copy()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return buf.tobytes() if ok else None

    def _loop(self):
        fps = max(0.5, min(10.0, float(self.cfg.get("fps", 3.0))))
        interval = 1.0 / fps
        while not self.stop_event.is_set():
            t0 = time.time()
            try:
                frame = self.frame_source.capture()
                self.frame_id += 1
                state = self.recognizer.recognize(frame, self.frame_id, self.frame_source.label)
                state = self.stabilizer.push(state)
                with self.lock:
                    self.latest_frame = frame
                    # Keep latest numbers but only publish card changes once stable.
                    if state.stable:
                        self.state = state
                    elif self.stabilizer.last_good.ok:
                        last = self.stabilizer.last_good
                        self.state = VisionState(**last.to_dict())
                        self.state.pot = state.pot if state.pot is not None else last.pot
                        self.state.call = state.call if state.call is not None else last.call
                        self.state.hero_turn = state.hero_turn
                        self.state.frame_id = state.frame_id
                        self.state.captured_at = state.captured_at
                        self.state.error = "牌面变化确认中"
                    else:
                        self.state = state
            except Exception as e:
                with self.lock:
                    self.state = VisionState(
                        error=str(e),
                        frame_id=self.frame_id,
                        captured_at=time.time(),
                        source=self.frame_source.label,
                    )
            elapsed = time.time() - t0
            self.stop_event.wait(max(0.01, interval - elapsed))
