"""
Media Scene Maker v3
--------------------
Offline Tkinter app for placing a character/overlay media on many backgrounds,
adding a watermark/logo and one different word/phrase per background, then
exporting as MP4, GIF, PNG, or JPG.

Supported imports:
- Foreground/character: PNG, JPG, GIF, MP4, MOV, WEBM
- Backgrounds: PNG, JPG, GIF, MP4, MOV, WEBM
- Logo/watermark: single file OR folder of files. PNG/JPG/GIF/MP4 supported.

Supported exports:
- MP4, GIF, PNG, JPG

Install:
    pip install pillow imageio imageio-ffmpeg numpy

Run:
    python media_scene_maker_v3.py

Notes:
- PNG/GIF can keep transparency.
- MP4 usually has no transparency. If your MP4 has a solid green/black/white
  background, enable Chroma Key to remove that color.
- For PNG/JPG export, the app exports the first frame only.
"""

from __future__ import annotations

import math
import os
import re
import threading
import traceback
from bisect import bisect_right
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageSequence, ImageTk

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import imageio.v2 as imageio
except Exception:  # pragma: no cover
    imageio = None

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ANIM_IMAGE_EXTS = {".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"}
MEDIA_EXTS = IMAGE_EXTS | ANIM_IMAGE_EXTS | VIDEO_EXTS
EXPORT_FORMATS = ["mp4", "gif", "png", "jpg"]


# ----------------------------- small helpers -----------------------------

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    s = (hex_color or "#000000").strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except Exception:
        return 0, 0, 0


def safe_filename(text: str, fallback: str = "scene") -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\-_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or fallback


def natural_sort_key(path: Path):
    parts = re.split(r"(\d+)", path.name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def list_media_files(folder: str) -> List[Path]:
    p = Path(folder)
    if not p.exists() or not p.is_dir():
        return []
    files = [x for x in p.iterdir() if x.is_file() and x.suffix.lower() in MEDIA_EXTS]
    return sorted(files, key=natural_sort_key)


def find_default_font() -> Optional[str]:
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_font(font_path: str, size: int) -> ImageFont.ImageFont:
    size = max(1, int(size))
    for path in [font_path, find_default_font()]:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def require_video_libs() -> None:
    missing = []
    if imageio is None:
        missing.append("imageio")
    if np is None:
        missing.append("numpy")
    if missing:
        raise RuntimeError(
            "Missing package(s): " + ", ".join(missing) + "\n\nInstall with:\n"
            "pip install pillow imageio imageio-ffmpeg numpy"
        )


def fit_image(img: Image.Image, size: Tuple[int, int], mode: str = "cover") -> Image.Image:
    """Fit image to canvas and return RGBA."""
    img = img.convert("RGBA")
    w, h = size
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return Image.new("RGBA", size, (255, 255, 255, 255))

    mode = (mode or "cover").lower()
    if mode == "stretch":
        return img.resize(size, Image.Resampling.LANCZOS)

    scale = max(w / iw, h / ih) if mode == "cover" else min(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)

    if mode == "cover":
        left = max(0, (nw - w) // 2)
        top = max(0, (nh - h) // 2)
        return resized.crop((left, top, left + w, top + h))

    canvas = Image.new("RGBA", size, (255, 255, 255, 255))
    canvas.alpha_composite(resized, ((w - nw) // 2, (h - nh) // 2))
    return canvas


def scale_image(img: Image.Image, scale_percent: float) -> Image.Image:
    scale_percent = max(1, float(scale_percent))
    w, h = img.size
    nw = max(1, int(w * scale_percent / 100.0))
    nh = max(1, int(h * scale_percent / 100.0))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def alpha_multiply(img: Image.Image, opacity_percent: float) -> Image.Image:
    img = img.convert("RGBA")
    opacity = clamp(float(opacity_percent), 0, 100) / 100.0
    if opacity >= 0.999:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda p: int(p * opacity))
    out = Image.merge("RGBA", (r, g, b, a))
    return out


def apply_chroma_key(img: Image.Image, key_hex: str, tolerance: int, softness: int = 10) -> Image.Image:
    """Remove pixels close to key color. Works best for green/black/white screen MP4."""
    if np is None:
        return img
    img = img.convert("RGBA")
    arr = np.array(img).astype(np.float32)
    key = np.array(hex_to_rgb(key_hex), dtype=np.float32)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    dist = np.sqrt(((rgb - key) ** 2).sum(axis=2))

    tolerance = max(0, int(tolerance))
    softness = max(1, int(softness))
    transparent = dist <= tolerance
    fade = (dist - tolerance) / softness
    fade = np.clip(fade, 0, 1)

    # fully transparent below tolerance; gradually returns alpha over softness range
    new_alpha = alpha * fade
    new_alpha[~transparent & (dist > tolerance + softness)] = alpha[~transparent & (dist > tolerance + softness)]
    arr[:, :, 3] = new_alpha
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


def draw_scene_text(
    base: Image.Image,
    text: str,
    font_path: str,
    font_size: int,
    x_percent: float,
    y_percent: float,
    fill: str,
    stroke_fill: str,
    stroke_width: int,
    shadow: bool,
    shadow_offset: int,
) -> None:
    text = text or ""
    if not text.strip():
        return

    draw = ImageDraw.Draw(base)
    font = load_font(font_path, font_size)
    x = int(base.width * clamp(x_percent, 0, 100) / 100.0)
    y = int(base.height * clamp(y_percent, 0, 100) / 100.0)
    spacing = max(2, int(font_size * 0.18))

    if shadow:
        draw.multiline_text(
            (x + shadow_offset, y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 135),
            anchor="mm",
            align="center",
            spacing=spacing,
            stroke_width=max(0, int(stroke_width)),
            stroke_fill=(0, 0, 0, 135),
        )

    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=fill,
        anchor="mm",
        align="center",
        spacing=spacing,
        stroke_width=max(0, int(stroke_width)),
        stroke_fill=stroke_fill,
    )


# ----------------------------- media sources -----------------------------

class MediaSource:
    def __init__(self, path: str):
        self.path = str(path or "")
        self.ext = Path(self.path).suffix.lower()
        self.kind = "missing"
        self.frames: List[Image.Image] = []
        self.durations_ms: List[int] = []
        self.cumulative_ms: List[int] = []
        self.duration_sec: float = 1.0
        self.reader = None
        self.fps: float = 24.0
        self.nframes: Optional[int] = None
        self.first_frame_cache: Optional[Image.Image] = None

        if not self.path or not os.path.exists(self.path):
            return

        if self.ext in VIDEO_EXTS:
            require_video_libs()
            self.kind = "video"
            self.reader = imageio.get_reader(self.path)
            meta = {}
            try:
                meta = self.reader.get_meta_data() or {}
            except Exception:
                meta = {}
            self.fps = float(meta.get("fps") or 24.0)
            duration = meta.get("duration")
            try:
                self.duration_sec = float(duration) if duration and math.isfinite(float(duration)) else 1.0
            except Exception:
                self.duration_sec = 1.0
            try:
                nf = meta.get("nframes")
                if nf and math.isfinite(float(nf)):
                    self.nframes = int(nf)
                    if not duration:
                        self.duration_sec = max(1.0 / self.fps, self.nframes / self.fps)
            except Exception:
                pass
            self.duration_sec = max(1.0 / self.fps, self.duration_sec)
        elif self.ext in ANIM_IMAGE_EXTS:
            self.kind = "gif"
            with Image.open(self.path) as im:
                default_duration = int(im.info.get("duration", 80) or 80)
                for frame in ImageSequence.Iterator(im):
                    dur = int(frame.info.get("duration", default_duration) or default_duration)
                    self.frames.append(frame.convert("RGBA"))
                    self.durations_ms.append(max(20, dur))
            if not self.frames:
                self.frames = [Image.new("RGBA", (1, 1), (0, 0, 0, 0))]
                self.durations_ms = [1000]
            total = 0
            self.cumulative_ms = []
            for d in self.durations_ms:
                total += d
                self.cumulative_ms.append(total)
            self.duration_sec = max(0.02, total / 1000.0)
        else:
            self.kind = "static"
            self.frames = [Image.open(self.path).convert("RGBA")]
            self.durations_ms = [1000]
            self.cumulative_ms = [1000]
            self.duration_sec = 1.0

    def close(self) -> None:
        if self.reader is not None:
            try:
                self.reader.close()
            except Exception:
                pass
            self.reader = None

    def get_frame(self, t: float) -> Image.Image:
        if self.kind == "missing":
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        if self.kind == "static":
            return self.frames[0].copy()
        if self.kind == "gif":
            total_ms = max(1, self.cumulative_ms[-1])
            t_ms = int((max(0.0, t) * 1000.0) % total_ms)
            idx = bisect_right(self.cumulative_ms, t_ms)
            idx = min(max(0, idx), len(self.frames) - 1)
            return self.frames[idx].copy()
        # video
        if self.reader is None:
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        try:
            duration = max(1.0 / self.fps, self.duration_sec)
            tt = max(0.0, t) % duration
            idx = int(tt * self.fps)
            if self.nframes:
                idx = idx % max(1, self.nframes)
            arr = self.reader.get_data(idx)
            img = Image.fromarray(arr)
            return img.convert("RGBA")
        except Exception:
            # fallback: cache first frame
            if self.first_frame_cache is not None:
                return self.first_frame_cache.copy()
            try:
                arr = self.reader.get_data(0)
                self.first_frame_cache = Image.fromarray(arr).convert("RGBA")
                return self.first_frame_cache.copy()
            except Exception:
                return Image.new("RGBA", (1, 1), (0, 0, 0, 0))


def first_frame(path: str) -> Optional[Image.Image]:
    try:
        src = MediaSource(path)
        frame = src.get_frame(0)
        src.close()
        return frame
    except Exception:
        return None


# ----------------------------- main Tk app -----------------------------

class MediaSceneMakerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Media Scene Maker v3 - MP4 / GIF / PNG / JPG")
        self.root.geometry("1360x900")
        self.root.minsize(1120, 760)

        self.foreground_path = tk.StringVar(value="")
        self.background_folder = tk.StringVar(value="")
        self.logo_path = tk.StringVar(value="")
        self.output_folder = tk.StringVar(value=str(Path.cwd() / "exports"))
        self.font_path = tk.StringVar(value=find_default_font() or "")

        self.canvas_w = tk.StringVar(value="1280")
        self.canvas_h = tk.StringVar(value="720")
        self.export_format = tk.StringVar(value="mp4")
        self.export_fps = tk.StringVar(value="24")
        self.duration_sec = tk.StringVar(value="4")
        self.bg_fit_mode = tk.StringVar(value="cover")

        self.fg_enabled = tk.BooleanVar(value=True)
        self.fg_x = tk.StringVar(value="50")
        self.fg_y = tk.StringVar(value="59")
        self.fg_scale = tk.StringVar(value="100")
        self.fg_opacity = tk.StringVar(value="100")
        self.chroma_enabled = tk.BooleanVar(value=False)
        self.chroma_color = tk.StringVar(value="#00ff00")
        self.chroma_tolerance = tk.StringVar(value="70")
        self.chroma_softness = tk.StringVar(value="25")

        self.logo_enabled = tk.BooleanVar(value=True)
        self.logo_scale = tk.StringVar(value="22")
        self.logo_opacity = tk.StringVar(value="28")
        self.logo_position = tk.StringVar(value="bottom_right")
        self.logo_margin = tk.StringVar(value="28")

        self.text_enabled = tk.BooleanVar(value=True)
        self.font_size = tk.StringVar(value="58")
        self.text_x = tk.StringVar(value="50")
        self.text_y = tk.StringVar(value="20")
        self.text_color = tk.StringVar(value="#ffffff")
        self.stroke_color = tk.StringVar(value="#102a66")
        self.stroke_width = tk.StringVar(value="4")
        self.text_shadow = tk.BooleanVar(value=True)
        self.shadow_offset = tk.StringVar(value="4")

        self.background_files: List[Path] = []
        self.preview_photo: Optional[ImageTk.PhotoImage] = None
        self.export_cancelled = False

        self.build_ui()
        self.bind_preview_updates()

    # -------------------------- UI building --------------------------

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)

        right = ttk.Frame(main)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(12, 0))

        self.build_paths_panel(left)
        self.build_settings_panel(left)
        self.build_controls_panel(left)
        self.build_words_panel(left)
        self.build_preview_panel(right)

    def row_entry(self, parent, label: str, var: tk.StringVar, row: int, width: int = 42, browse_cmd=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ent = ttk.Entry(parent, textvariable=var, width=width)
        ent.grid(row=row, column=1, sticky="ew", padx=6, pady=2)
        if browse_cmd:
            ttk.Button(parent, text="Browse", command=browse_cmd).grid(row=row, column=2, sticky="e", pady=2)
        return ent

    def build_paths_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="1. Files", padding=8)
        box.pack(fill=tk.X, pady=(0, 8))
        box.columnconfigure(1, weight=1)

        self.row_entry(box, "Foreground", self.foreground_path, 0, browse_cmd=self.choose_foreground)
        self.row_entry(box, "Background folder", self.background_folder, 1, browse_cmd=self.choose_background_folder)

        ttk.Label(box, text="Logo file/folder").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(box, textvariable=self.logo_path, width=42).grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        logo_btns = ttk.Frame(box)
        logo_btns.grid(row=2, column=2, sticky="e")
        ttk.Button(logo_btns, text="File", command=self.choose_logo_file).pack(side=tk.LEFT)
        ttk.Button(logo_btns, text="Folder", command=self.choose_logo_folder).pack(side=tk.LEFT, padx=(4, 0))

        self.row_entry(box, "Output folder", self.output_folder, 3, browse_cmd=self.choose_output_folder)

        ttk.Button(box, text="Reload backgrounds", command=self.load_backgrounds).grid(row=4, column=1, sticky="w", pady=(6, 0))

    def build_settings_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="2. Export settings", padding=8)
        box.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(box, text="Canvas").grid(row=0, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.canvas_w, width=8).grid(row=0, column=1, sticky="w", padx=(6, 2))
        ttk.Label(box, text="x").grid(row=0, column=2, sticky="w")
        ttk.Entry(box, textvariable=self.canvas_h, width=8).grid(row=0, column=3, sticky="w", padx=(2, 10))

        ttk.Label(box, text="Format").grid(row=0, column=4, sticky="w")
        ttk.Combobox(box, textvariable=self.export_format, values=EXPORT_FORMATS, width=7, state="readonly").grid(row=0, column=5, sticky="w", padx=(6, 10))

        ttk.Label(box, text="FPS").grid(row=0, column=6, sticky="w")
        ttk.Entry(box, textvariable=self.export_fps, width=6).grid(row=0, column=7, sticky="w", padx=(6, 10))

        ttk.Label(box, text="Duration sec").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(box, textvariable=self.duration_sec, width=8).grid(row=1, column=1, sticky="w", padx=(6, 10), pady=(6, 0))
        ttk.Label(box, text="0 = auto").grid(row=1, column=2, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(box, text="BG fit").grid(row=1, column=4, sticky="w", pady=(6, 0))
        ttk.Combobox(box, textvariable=self.bg_fit_mode, values=["cover", "contain", "stretch"], width=9, state="readonly").grid(row=1, column=5, sticky="w", padx=(6, 10), pady=(6, 0))

    def build_controls_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="3. Foreground / logo / text controls", padding=8)
        box.pack(fill=tk.X, pady=(0, 8))

        # foreground
        fg = ttk.LabelFrame(box, text="Foreground media", padding=6)
        fg.pack(fill=tk.X, pady=(0, 6))
        ttk.Checkbutton(fg, text="Enable", variable=self.fg_enabled).grid(row=0, column=0, sticky="w")
        self.small_labeled_entry(fg, "X%", self.fg_x, 0, 1)
        self.small_labeled_entry(fg, "Y%", self.fg_y, 0, 3)
        self.small_labeled_entry(fg, "Scale%", self.fg_scale, 0, 5)
        self.small_labeled_entry(fg, "Opacity%", self.fg_opacity, 0, 7)

        ttk.Checkbutton(fg, text="Chroma key", variable=self.chroma_enabled).grid(row=1, column=0, sticky="w", pady=(5, 0))
        ttk.Button(fg, text="Key color", command=lambda: self.pick_color(self.chroma_color)).grid(row=1, column=1, columnspan=2, sticky="w", pady=(5, 0))
        self.small_labeled_entry(fg, "Tol", self.chroma_tolerance, 1, 3)
        self.small_labeled_entry(fg, "Soft", self.chroma_softness, 1, 5)

        # logo
        logo = ttk.LabelFrame(box, text="Logo / watermark", padding=6)
        logo.pack(fill=tk.X, pady=(0, 6))
        ttk.Checkbutton(logo, text="Enable", variable=self.logo_enabled).grid(row=0, column=0, sticky="w")
        self.small_labeled_entry(logo, "Scale%", self.logo_scale, 0, 1)
        self.small_labeled_entry(logo, "Opacity%", self.logo_opacity, 0, 3)
        self.small_labeled_entry(logo, "Margin", self.logo_margin, 0, 5)
        ttk.Label(logo, text="Position").grid(row=0, column=7, sticky="w", padx=(8, 3))
        ttk.Combobox(
            logo,
            textvariable=self.logo_position,
            values=["bottom_right", "bottom_left", "top_right", "top_left", "center"],
            width=13,
            state="readonly",
        ).grid(row=0, column=8, sticky="w")

        # text
        text = ttk.LabelFrame(box, text="Words / font", padding=6)
        text.pack(fill=tk.X)
        ttk.Checkbutton(text, text="Enable", variable=self.text_enabled).grid(row=0, column=0, sticky="w")
        ttk.Button(text, text="Choose font", command=self.choose_font).grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.small_labeled_entry(text, "Size", self.font_size, 0, 2)
        self.small_labeled_entry(text, "X%", self.text_x, 0, 4)
        self.small_labeled_entry(text, "Y%", self.text_y, 0, 6)
        ttk.Button(text, text="Text color", command=lambda: self.pick_color(self.text_color)).grid(row=1, column=1, sticky="w", pady=(5, 0))
        ttk.Button(text, text="Outline color", command=lambda: self.pick_color(self.stroke_color)).grid(row=1, column=2, sticky="w", pady=(5, 0))
        self.small_labeled_entry(text, "Outline", self.stroke_width, 1, 3)
        ttk.Checkbutton(text, text="Shadow", variable=self.text_shadow).grid(row=1, column=5, sticky="w", pady=(5, 0))
        self.small_labeled_entry(text, "Shadow off", self.shadow_offset, 1, 6)

    def small_labeled_entry(self, parent, label: str, var: tk.StringVar, row: int, col: int):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(8, 2))
        ttk.Entry(parent, textvariable=var, width=7).grid(row=row, column=col + 1, sticky="w")

    def build_words_panel(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text="4. Words / phrases - one line per background", padding=8)
        box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        top = ttk.Frame(box)
        top.pack(fill=tk.X)
        ttk.Button(top, text="Auto-fill sample words", command=self.sample_words).pack(side=tk.LEFT)
        ttk.Label(top, text="Example: line 1 goes to background 1, line 2 to background 2").pack(side=tk.LEFT, padx=8)

        self.words_text = tk.Text(box, height=8, wrap="word", undo=True)
        self.words_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        self.words_text.insert("1.0", "Studying mode\nWork break\nMoon shift\nGaming night")

    def build_preview_panel(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Backgrounds").pack(side=tk.LEFT)
        ttk.Button(top, text="Preview selected", command=self.update_preview).pack(side=tk.LEFT, padx=8)
        ttk.Button(top, text="EXPORT ALL", command=self.export_all_threaded).pack(side=tk.RIGHT)

        body = ttk.Frame(parent)
        body.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        list_frame = ttk.Frame(body)
        list_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.bg_listbox = tk.Listbox(list_frame, width=34, height=26, exportselection=False)
        self.bg_listbox.pack(side=tk.LEFT, fill=tk.Y)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self.bg_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.bg_listbox.configure(yscrollcommand=sb.set)
        self.bg_listbox.bind("<<ListboxSelect>>", lambda _e: self.update_preview())

        preview_wrap = ttk.Frame(body)
        preview_wrap.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(12, 0))
        self.preview_label = ttk.Label(preview_wrap, text="Preview will appear here", anchor="center")
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(parent, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(10, 4))
        self.status = tk.StringVar(value="Ready")
        ttk.Label(parent, textvariable=self.status).pack(fill=tk.X)

    def bind_preview_updates(self) -> None:
        vars_to_trace = [
            self.canvas_w, self.canvas_h, self.export_format, self.export_fps, self.duration_sec, self.bg_fit_mode,
            self.fg_x, self.fg_y, self.fg_scale, self.fg_opacity, self.chroma_color, self.chroma_tolerance, self.chroma_softness,
            self.logo_scale, self.logo_opacity, self.logo_position, self.logo_margin,
            self.font_path, self.font_size, self.text_x, self.text_y, self.text_color, self.stroke_color, self.stroke_width, self.shadow_offset,
        ]
        for var in vars_to_trace:
            var.trace_add("write", lambda *_: self.root.after(250, self.update_preview))
        for bvar in [self.fg_enabled, self.chroma_enabled, self.logo_enabled, self.text_enabled, self.text_shadow]:
            bvar.trace_add("write", lambda *_: self.root.after(100, self.update_preview))
        self.words_text.bind("<KeyRelease>", lambda _e: self.root.after(250, self.update_preview))

    # -------------------------- file choices --------------------------

    def choose_foreground(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose foreground media",
            filetypes=[("Media", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mov *.m4v *.webm *.avi *.mkv"), ("All files", "*.*")],
        )
        if path:
            self.foreground_path.set(path)
            self.update_preview()

    def choose_background_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose background folder")
        if path:
            self.background_folder.set(path)
            self.load_backgrounds()

    def choose_logo_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose logo/watermark file",
            filetypes=[("Media", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mov *.m4v *.webm *.avi *.mkv"), ("All files", "*.*")],
        )
        if path:
            self.logo_path.set(path)
            self.update_preview()

    def choose_logo_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose logo/watermark folder")
        if path:
            self.logo_path.set(path)
            self.update_preview()

    def choose_output_folder(self) -> None:
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output_folder.set(path)

    def choose_font(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose font",
            filetypes=[("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*")],
        )
        if path:
            self.font_path.set(path)
            self.update_preview()

    def pick_color(self, var: tk.StringVar) -> None:
        _rgb, hx = colorchooser.askcolor(color=var.get())
        if hx:
            var.set(hx)
            self.update_preview()

    # -------------------------- background/words --------------------------

    def load_backgrounds(self) -> None:
        self.background_files = list_media_files(self.background_folder.get())
        self.bg_listbox.delete(0, tk.END)
        words = self.get_words()
        for i, path in enumerate(self.background_files):
            word = words[i] if i < len(words) else ""
            label = f"{i + 1:02d}. {path.name}"
            if word:
                label += f"  ->  {word[:26]}"
            self.bg_listbox.insert(tk.END, label)
        if self.background_files:
            self.bg_listbox.selection_clear(0, tk.END)
            self.bg_listbox.selection_set(0)
        self.status.set(f"Loaded {len(self.background_files)} background(s)")
        self.update_preview()

    def get_words(self) -> List[str]:
        return [line.strip() for line in self.words_text.get("1.0", tk.END).splitlines()]

    def selected_index(self) -> int:
        sel = self.bg_listbox.curselection()
        if not sel:
            return 0
        return int(sel[0])

    def sample_words(self) -> None:
        self.words_text.delete("1.0", tk.END)
        self.words_text.insert(
            "1.0",
            "Study mode\nOffice break\nMoon workplace\nGaming night\nCoffee time\nRelax zone\nMission control\nDream room\nFocus mode\n",
        )
        self.update_preview()

    def logo_for_index(self, index: int) -> Optional[str]:
        p = Path(self.logo_path.get())
        if not str(p):
            return None
        if p.is_file():
            return str(p)
        if p.is_dir():
            logos = list_media_files(str(p))
            if logos:
                return str(logos[index % len(logos)])
        return None

    # -------------------------- composition --------------------------

    def canvas_size(self) -> Tuple[int, int]:
        w = max(64, safe_int(self.canvas_w.get(), 1280))
        h = max(64, safe_int(self.canvas_h.get(), 720))
        return w, h

    def compose_frame(
        self,
        bg_img: Image.Image,
        fg_img: Optional[Image.Image],
        logo_img: Optional[Image.Image],
        word: str,
    ) -> Image.Image:
        size = self.canvas_size()
        base = fit_image(bg_img, size, self.bg_fit_mode.get())

        # foreground / character
        if self.fg_enabled.get() and fg_img is not None:
            fg = fg_img.convert("RGBA")
            if self.chroma_enabled.get():
                fg = apply_chroma_key(
                    fg,
                    self.chroma_color.get(),
                    safe_int(self.chroma_tolerance.get(), 70),
                    safe_int(self.chroma_softness.get(), 25),
                )
            fg = scale_image(fg, safe_float(self.fg_scale.get(), 100))
            fg = alpha_multiply(fg, safe_float(self.fg_opacity.get(), 100))
            x = int(size[0] * clamp(safe_float(self.fg_x.get(), 50), 0, 100) / 100.0)
            y = int(size[1] * clamp(safe_float(self.fg_y.get(), 59), 0, 100) / 100.0)
            base.alpha_composite(fg, (int(x - fg.width / 2), int(y - fg.height / 2)))

        # logo / watermark
        if self.logo_enabled.get() and logo_img is not None:
            logo = logo_img.convert("RGBA")
            logo = scale_image(logo, safe_float(self.logo_scale.get(), 22))
            logo = alpha_multiply(logo, safe_float(self.logo_opacity.get(), 28))
            margin = max(0, safe_int(self.logo_margin.get(), 28))
            w, h = size
            positions = {
                "top_left": (margin, margin),
                "top_right": (w - logo.width - margin, margin),
                "bottom_left": (margin, h - logo.height - margin),
                "bottom_right": (w - logo.width - margin, h - logo.height - margin),
                "center": ((w - logo.width) // 2, (h - logo.height) // 2),
            }
            x, y = positions.get(self.logo_position.get(), positions["bottom_right"])
            base.alpha_composite(logo, (int(x), int(y)))

        # text
        if self.text_enabled.get() and word:
            draw_scene_text(
                base,
                word,
                self.font_path.get(),
                safe_int(self.font_size.get(), 58),
                safe_float(self.text_x.get(), 50),
                safe_float(self.text_y.get(), 20),
                self.text_color.get(),
                self.stroke_color.get(),
                safe_int(self.stroke_width.get(), 4),
                self.text_shadow.get(),
                safe_int(self.shadow_offset.get(), 4),
            )

        return base

    def update_preview(self) -> None:
        try:
            if not self.background_files:
                # Try auto load if folder is set.
                if self.background_folder.get():
                    self.background_files = list_media_files(self.background_folder.get())
                if not self.background_files:
                    self.preview_label.configure(text="Choose a background folder to preview", image="")
                    return

            idx = min(self.selected_index(), len(self.background_files) - 1)
            words = self.get_words()
            word = words[idx] if idx < len(words) else ""
            bg_path = str(self.background_files[idx])
            bg = first_frame(bg_path)
            if bg is None:
                raise RuntimeError(f"Could not read background: {bg_path}")

            fg = first_frame(self.foreground_path.get()) if self.foreground_path.get() else None
            logo_path = self.logo_for_index(idx)
            logo = first_frame(logo_path) if logo_path else None
            composed = self.compose_frame(bg, fg, logo, word)

            # Fit preview to available area.
            max_w = max(500, self.preview_label.winfo_width() or 900)
            max_h = max(400, self.preview_label.winfo_height() or 650)
            scale = min(max_w / composed.width, max_h / composed.height, 1.0)
            preview = composed.resize((int(composed.width * scale), int(composed.height * scale)), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(preview)
            self.preview_label.configure(image=self.preview_photo, text="")
            self.status.set(f"Preview: {Path(bg_path).name} | word: {word or '(empty)'}")
        except Exception as e:
            self.preview_label.configure(text=f"Preview error:\n{e}", image="")
            self.status.set("Preview error")

    # -------------------------- export --------------------------

    def export_all_threaded(self) -> None:
        t = threading.Thread(target=self.export_all, daemon=True)
        t.start()

    def export_all(self) -> None:
        try:
            self.root.after(0, lambda: self.progress.configure(value=0))
            self.status.set("Starting export...")
            if not self.background_files:
                self.background_files = list_media_files(self.background_folder.get())
            if not self.background_files:
                raise RuntimeError("No backgrounds found. Choose a background folder first.")

            fmt = self.export_format.get().lower()
            if fmt not in EXPORT_FORMATS:
                raise RuntimeError("Unsupported export format.")
            if fmt == "mp4":
                require_video_libs()

            out_dir = Path(self.output_folder.get())
            out_dir.mkdir(parents=True, exist_ok=True)

            words = self.get_words()
            fps = max(1, min(60, safe_int(self.export_fps.get(), 24)))
            requested_duration = max(0.0, safe_float(self.duration_sec.get(), 4))
            total_items = len(self.background_files)

            fg_src = None
            if self.fg_enabled.get() and self.foreground_path.get():
                fg_src = MediaSource(self.foreground_path.get())

            for i, bg_path in enumerate(self.background_files):
                word = words[i] if i < len(words) else ""
                self.status.set(f"Exporting {i + 1}/{total_items}: {bg_path.name}")
                bg_src = MediaSource(str(bg_path))
                logo_src = None
                logo_path = self.logo_for_index(i)
                if self.logo_enabled.get() and logo_path:
                    logo_src = MediaSource(logo_path)

                stem = safe_filename(bg_path.stem, "background")
                word_part = safe_filename(word, f"scene_{i+1:02d}")
                out_path = out_dir / f"{i + 1:02d}_{stem}_{word_part}.{fmt}"

                if fmt in {"png", "jpg"}:
                    frame = self.compose_frame(
                        bg_src.get_frame(0),
                        fg_src.get_frame(0) if fg_src else None,
                        logo_src.get_frame(0) if logo_src else None,
                        word,
                    )
                    if fmt == "jpg":
                        frame.convert("RGB").save(out_path, quality=95)
                    else:
                        frame.save(out_path)
                else:
                    duration = requested_duration
                    if duration <= 0:
                        duration = max(
                            bg_src.duration_sec,
                            fg_src.duration_sec if fg_src else 0,
                            logo_src.duration_sec if logo_src else 0,
                            1.0,
                        )
                    duration = max(0.25, min(60.0, duration))
                    frame_count = max(1, int(duration * fps))

                    if fmt == "mp4":
                        writer = imageio.get_writer(
                            str(out_path),
                            fps=fps,
                            codec="libx264",
                            quality=8,
                            macro_block_size=1,
                        )
                        try:
                            for frame_idx in range(frame_count):
                                t = frame_idx / fps
                                frame = self.compose_frame(
                                    bg_src.get_frame(t),
                                    fg_src.get_frame(t) if fg_src else None,
                                    logo_src.get_frame(t) if logo_src else None,
                                    word,
                                )
                                writer.append_data(np.array(frame.convert("RGB")))
                        finally:
                            writer.close()
                    elif fmt == "gif":
                        frames: List[Image.Image] = []
                        for frame_idx in range(frame_count):
                            t = frame_idx / fps
                            frame = self.compose_frame(
                                bg_src.get_frame(t),
                                fg_src.get_frame(t) if fg_src else None,
                                logo_src.get_frame(t) if logo_src else None,
                                word,
                            )
                            frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
                        dur_ms = max(20, int(1000 / fps))
                        frames[0].save(
                            out_path,
                            save_all=True,
                            append_images=frames[1:],
                            duration=dur_ms,
                            loop=0,
                            optimize=False,
                            disposal=2,
                        )

                bg_src.close()
                if logo_src:
                    logo_src.close()
                progress = int((i + 1) / total_items * 100)
                self.root.after(0, lambda p=progress: self.progress.configure(value=p))

            if fg_src:
                fg_src.close()
            self.status.set(f"Done. Exported to: {out_dir}")
            messagebox.showinfo("Export complete", f"Exported {total_items} file(s) to:\n{out_dir}")
        except Exception as e:
            traceback.print_exc()
            self.status.set("Export failed")
            messagebox.showerror("Export failed", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = MediaSceneMakerApp(root)
    root.mainloop()
