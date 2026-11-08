# Photo Organizer

Sorts photos and videos into folders by the date they were taken. Put a messy pile of photos in the `input` folder
(a phone backup, a camera card, years of downloads), run the script, and get them sorted in the `output` folder:

```
output/
├── 2023/
│   ├── 05 - May/
│   │   ├── IMG_0001.jpg
│   │   └── IMG_0002.heic
│   └── 12 - December/
└── 2024/
    └── ...
```

## Folder layout

```
photo_organizer/
├── organize_photos.py   the script
├── requirements.txt     Python packages to install
├── README.md            this file
├── input/               put your photos and videos here (subfolders are fine)
└── output/              sorted photos appear here, in year/month folders
```

## Setup (one time)

1. Install **Python 3.9 or newer** from https://www.python.org/downloads/
   (on Windows, tick "Add Python to PATH" during install).
2. Open a terminal in the `photo_organizer` folder and run:

   ```
   pip install -r requirements.txt
   ```

## How to use

1. Copy your photos and videos into the `input` folder. Subfolders are fine; they're all searched.
2. Open a terminal in the `photo_organizer` folder.
3. **Optional, recommended the first time:** see what would happen without changing anything:

   ```
   python organize_photos.py --dry-run
   ```

4. Sort them for real:

   ```
   python organize_photos.py
   ```

5. The sorted photos are in the `output` folder. Your originals in `input` are left alone (they're copied, not moved),
   unless you use `--move`.

| Command | What it does |
|---|---|
| `python organize_photos.py` | Copies photos into `year/month` folders |
| `python organize_photos.py --dry-run` | Shows what would happen without copying anything |
| `python organize_photos.py --move` | Moves photos instead of copying (saves space, empties `input`) |
| `python organize_photos.py --by year` | One folder per year: `2023/` |
| `python organize_photos.py --by day` | One folder per day: `2023/2023-05-14/` |
| `python organize_photos.py --rename` | Renames each file to its date: `2023-05-14 13.45.10.jpg` |
| `python organize_photos.py --no-file-date` | Photos with no real date go to `Unknown date/` (see below) |
| `python organize_photos.py --by day --rename --dry-run` | Options can be combined |
| `python organize_photos.py --help` | Shows all options |

## Options

| Option | Default | Meaning |
|---|---|---|
| `--by` | `month` | Folder per `year`, `month` (`2023/05 - May/`) or `day` (`2023/2023-05-14/`) |
| `--move` | off | Move files instead of copying them |
| `--rename` | off | Rename files to the date taken, e.g. `2023-05-14 13.45.10.jpg` |
| `--dry-run` | off | Only show what would happen. Nothing is copied, moved or renamed |
| `--no-file-date` | off | Don't use the file's own date as a last resort; use an `Unknown date` folder instead |
| `-i`, `--input` | `input` folder | Folder to read photos from (subfolders included) |
| `-o`, `--output` | `output` folder | Folder to sort photos into |

## How it finds the date

For each file it tries these, in order, and uses the first one it finds. The script shows which one it used for each file.

1. **Photo info**: the "date taken" that cameras and phones store inside the photo. This is the most reliable.
2. **File name**: many phones and apps put the date in the name, like `IMG_20230514_134510.jpg`,
   `IMG-20230514-WA0001.jpg` (WhatsApp), `Screenshot 2023-05-14 at 13.45.10.png` or `VID_20230514_134510.mp4`.
3. **File date**: the date the file was last changed, as shown in File Explorer. This is usually right for files copied
   straight off a phone or camera. It can be wrong for files that were downloaded, emailed, or edited.

If you don't trust the file date, use `--no-file-date`. Files without a date in their photo info or name then go into
an `Unknown date` folder for you to sort by hand.

**Videos** don't have photo info this script can read, so they use the file name or the file date.

**Files it sorts:**
- Photos: `.jpg .jpeg .jfif .png .heic .heif .webp .gif .bmp .tif .tiff`
- Camera RAW: `.dng .cr2 .cr3 .nef .arw .orf .rw2 .raf`
- Videos: `.mp4 .mov .m4v .avi .mkv .3gp .mts .m2ts .wmv`

Other files, like the `.aae` edit files iPhones create, are counted as "ignored" and left alone.

## Good to know

- **By default nothing in `input` is changed.** Files are copied, so you can check the result before deleting anything.
- **Use `--dry-run` first** if you're unsure. It prints exactly what would happen.
- **Exact duplicates are skipped.** If the same photo is in `input` twice (even with different names), or is already in
  the output folder from an earlier run, it's only kept once. With `--move`, duplicates stay in `input` so nothing is lost.
- **Running it again is safe.** Photos that were already sorted are recognized as duplicates and skipped. Only new
  photos are added.
- **Different photos with the same name** (common with `IMG_0001.jpg` from different phones) are never overwritten.
  The second one gets ` (2)` added to its name.
- **Folder names are in English**: `05 - May`. The number at the front keeps the months in calendar order.

## Troubleshooting

**`Error: Pillow is not installed`**
Run `pip install -r requirements.txt` from inside the `photo_organizer` folder.

**iPhone (HEIC) photos are sorted by the wrong date**
pillow-heif probably isn't installed, so the date inside the photo can't be read. Run `pip install -r requirements.txt`.

**Lots of photos say `(file date)` and are in the wrong year**
The files probably lost their original dates when they were downloaded or copied. Use `--no-file-date` to put them in
`Unknown date` instead.

**`the output folder can't be inside the input folder`**
Choose an output folder somewhere else, otherwise the script would sort its own results.

**`'python' is not recognized`**
Python isn't on your PATH. On Windows, try `py organize_photos.py` instead, or reinstall Python with "Add Python to PATH" ticked.
