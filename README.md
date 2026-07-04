[GITHUB_RELEASE_BODY_v0.3.0.md](https://github.com/user-attachments/files/29654485/GITHUB_RELEASE_BODY_v0.3.0.md)
# Media-maker# Media Scene Maker v0.3.0

## Highlights

This release adds a more flexible media workflow for creating final scene exports from any available assets.

## Supported imports

- Foreground/character: MP4, GIF, PNG, JPG
- Backgrounds: MP4, GIF, PNG, JPG
- Logo/watermark: single image/video file or a folder of logo files

## Supported exports

- MP4
- GIF
- PNG
- JPG

## Main features

- Add a character/foreground over many backgrounds
- Add a logo watermark
- Add different text for each background using line-by-line text input
- Choose custom fonts with preview support
- Adjust text size, position, color, outline, and shadow
- Adjust foreground scale and position
- Use Chroma Key for MP4 overlays with solid-color backgrounds

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python media_scene_maker.py
```

## Notes

MP4 transparency is not supported in normal MP4 files. For transparent characters, use GIF/PNG whenever possible. If the foreground MP4 has green/black/white background, use Chroma Key.
