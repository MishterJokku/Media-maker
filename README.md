# Media Scene Maker

Offline desktop app for adding transparent GIFs/images/videos on top of different backgrounds, with optional logo watermark and different text for each scene.

Created by **Mishter_Jokku**.

## Features

- Import foreground/character as **MP4, GIF, PNG, JPG**
- Import backgrounds as **MP4, GIF, PNG, JPG**
- Add logo/watermark from one file or a logo folder
- Add many words/phrases: one line of text can match one background
- Choose custom font `.ttf` / `.otf`
- Preview and adjust text size, position, outline, and color
- Export as **MP4, GIF, PNG, JPG**
- Chroma key option for MP4 overlays with green/black/white background
- Works offline after installing dependencies

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python media_scene_maker.py
```

On Windows, you can also double-click:

```text
run_windows.bat
```

## Recommended folder setup

```text
project/
  media_scene_maker.py
  foreground/
    character.gif
  backgrounds/
    classroom.png
    moon_workplace.png
    gaming_room.mp4
  logos/
    watermark.png
  exports/
```

## Text-per-background workflow

Paste your words in the text box line by line:

```text
Studying mode
Moon work shift
Gaming break
```

The app will use:

```text
1st background -> Studying mode
2nd background -> Moon work shift
3rd background -> Gaming break
```

## Important notes

- Normal MP4 files do **not** preserve transparency.
- Use transparent GIF/PNG for best overlay quality.
- For MP4 overlays, use the Chroma Key option if the video has a solid green, black, or white background.
- PNG/JPG export saves the first frame only.
