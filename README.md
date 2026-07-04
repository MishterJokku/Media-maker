# Media Scene Maker

Offline desktop app for placing foreground media on backgrounds, adding a logo watermark, adding one text line per scene, and exporting the final result.

Created by **Mishter_Jokku**.

## Features

- Foreground import: MP4, GIF, PNG, JPG
- Background import: MP4, GIF, PNG, JPG
- Logo/watermark support
- One word or phrase per background
- Custom font picker with preview
- Export: MP4, GIF, PNG, JPG
- Chroma key option for solid-color MP4 overlays

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python media_scene_maker.py
```

Windows users can double-click `run_windows.bat`.

## Text per background

Example:

```text
Studying mode
Moon work shift
Gaming break
```

The app maps line 1 to background 1, line 2 to background 2, and so on.

## Notes

Normal MP4 files do not keep alpha transparency. For transparent overlays, use GIF or PNG when possible. For MP4 with a solid color background, use Chroma Key.
