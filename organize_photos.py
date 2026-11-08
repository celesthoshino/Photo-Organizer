"""
Photo Organizer
---------------
Put photos (and videos) in the "input" folder, run this script, and they get
sorted into dated folders in the "output" folder, like output/2024/05 - May/.

    python organize_photos.py              # copy into year/month folders
    python organize_photos.py --dry-run    # only show what would happen
    python organize_photos.py --move       # move instead of copy
    python organize_photos.py --by day     # output/2024/2024-05-14/
    python organize_photos.py --rename     # rename files to the date taken

See README.md for all the details.
"""

import argparse
import filecmp
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Error: Pillow is not installed.\nFix it by running:  pip install -r requirements.txt")

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()  # lets Pillow read the date from iPhone (HEIC) photos
except ImportError:
    pass  # HEIC photos then fall back to the date in the file name, or the file's own date

# The input/output folders live next to this script, so it works no matter
# which folder you run it from.
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".jfif", ".png", ".heic", ".heif", ".webp", ".gif", ".bmp", ".tif", ".tiff",
    ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf",  # camera RAW files
}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".3gp", ".mts", ".m2ts", ".wmv"}

MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# Where cameras store the date inside a photo (EXIF tags), best first:
# date taken, date digitized, date last changed.
EXIF_SUB_IFD = 0x8769
EXIF_DATE_TAGS = [(EXIF_SUB_IFD, 0x9003), (EXIF_SUB_IFD, 0x9004), (None, 0x0132)]

# Dates in file names, e.g. IMG_20230514_134510.jpg, PXL_20230514_134510123.jpg,
# Screenshot 2023-05-14 at 13.45.10.png, IMG-20230514-WA0001.jpg (WhatsApp)
NAME_DATE = re.compile(
    r"(?<!\d)((?:19|20)\d\d)[-_.]?(0[1-9]|1[0-2])[-_.]?(0[1-9]|[12]\d|3[01])"
    r"(?:\D{0,4}?([01]\d|2[0-3])[-_.:]?([0-5]\d)[-_.:]?([0-5]\d))?"
)


def date_from_photo(path: Path):
    """Date taken, from the info the camera stored inside the photo. None if there isn't one."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            for ifd, tag in EXIF_DATE_TAGS:
                value = (exif.get_ifd(ifd) if ifd else exif).get(tag)
                if value:
                    text = str(value).strip("\x00 ")[:19]
                    try:
                        return datetime.strptime(text.replace("-", ":"), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue  # some cameras write 0000:00:00 when the clock isn't set
    except Exception:
        pass  # not readable by Pillow (e.g. some RAW files), try other ways
    return None


def date_from_name(path: Path):
    """(date, has_time) from a date written in the file name, or None."""
    for match in NAME_DATE.finditer(path.stem):
        year, month, day, hour, minute, second = match.groups()
        try:
            date = datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
        except ValueError:
            continue  # e.g. February 30th
        if date <= datetime.now():
            return date, hour is not None
    return None


def find_date(path: Path, use_file_date: bool):
    """Returns (date, has_time, where it came from). date is None if nothing was found."""
    if path.suffix.lower() in PHOTO_EXTENSIONS:
        date = date_from_photo(path)
        if date:
            return date, True, "photo info"
    found = date_from_name(path)
    if found:
        return found[0], found[1], "file name"
    if use_file_date:
        return datetime.fromtimestamp(path.stat().st_mtime), True, "file date"
    return None, False, "no date"


def folder_for(date, by: str) -> Path:
    if date is None:
        return Path("Unknown date")
    if by == "year":
        return Path(str(date.year))
    if by == "month":
        return Path(str(date.year), f"{date.month:02d} - {MONTHS[date.month - 1]}")
    return Path(str(date.year), date.strftime("%Y-%m-%d"))


class DuplicateFinder:
    """
    Spots exact copies (same content, any name) going into the same folder.
    Only files with the same size are compared byte by byte, so it stays fast.
    """

    def __init__(self):
        self.folders = {}  # folder -> {file size: [(file to compare with, where it is/will be in output)]}

    def _index(self, folder: Path) -> dict:
        key = str(folder).lower()
        if key not in self.folders:
            index = {}
            if folder.is_dir():
                for path in folder.iterdir():
                    if path.is_file():
                        index.setdefault(path.stat().st_size, []).append((path, path))
            self.folders[key] = index
        return self.folders[key]

    def find(self, src: Path, folder: Path):
        """Where an identical file already is (or will be) in the output, or None."""
        for compare_with, location in self._index(folder).get(src.stat().st_size, []):
            if filecmp.cmp(src, compare_with, shallow=False):
                return location
        return None

    def add(self, folder: Path, size: int, compare_with: Path, location: Path):
        self._index(folder).setdefault(size, []).append((compare_with, location))


def free_name(wanted: Path, taken: set) -> Path:
    """`wanted`, or if that name is used, the same name with (2), (3), ... added."""
    candidate, number = wanted, 2
    # Windows treats IMG.JPG and img.jpg as the same name, hence the lower().
    while candidate.exists() or str(candidate).lower() in taken:
        candidate = wanted.with_name(f"{wanted.stem} ({number}){wanted.suffix}")
        number += 1
    return candidate


def scan(input_dir: Path):
    """All photos and videos in input_dir and its subfolders, plus a count of other files."""
    media, ignored = [], Counter()
    for path in sorted(input_dir.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_file() or path.name.startswith("."):
            continue
        suffix = path.suffix.lower()
        if suffix in PHOTO_EXTENSIONS or suffix in VIDEO_EXTENSIONS:
            media.append(path)
        else:
            ignored[suffix or "(no extension)"] += 1
    return media, ignored


def main():
    parser = argparse.ArgumentParser(description="Sort photos and videos into folders by the date they were taken.")
    parser.add_argument("--by", choices=["year", "month", "day"], default="month",
                        help="folder per year, month or day (default: month)")
    parser.add_argument("--move", action="store_true",
                        help="move files instead of copying them (the input folder gets emptied)")
    parser.add_argument("--rename", action="store_true",
                        help="rename files to the date taken, e.g. '2024-05-14 13.45.10.jpg'")
    parser.add_argument("--dry-run", action="store_true",
                        help="only show what would happen, without copying or moving anything")
    parser.add_argument("--no-file-date", action="store_true",
                        help="put files with no date in their photo info or name in 'Unknown date' "
                             "instead of using the file's own date")
    parser.add_argument("-i", "--input", type=Path, default=INPUT_DIR,
                        help="folder to read photos from, including subfolders (default: the input folder)")
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_DIR,
                        help="folder to sort photos into (default: the output folder)")
    args = parser.parse_args()

    args.input.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.output.resolve().is_relative_to(args.input.resolve()):
        sys.exit("Error: the output folder can't be inside the input folder.")

    print(f"Looking in: {args.input} (and its subfolders)")
    files, ignored = scan(args.input)
    if ignored:
        kinds = ", ".join(f"{count} {ext}" for ext, count in ignored.most_common())
        print(f"  Ignoring {sum(ignored.values())} file(s) that aren't photos or videos ({kinds})")
    if not files:
        print("No photos or videos found. Put them in that folder, then run this again.")
        return

    action = "move" if args.move else "copy"
    if args.dry_run:
        print("DRY RUN: nothing will be copied or moved, this only shows what would happen.")
    print(f"Found {len(files)} photo(s)/video(s).\n")

    duplicate_finder = DuplicateFinder()
    taken_names = set()  # needed for --dry-run, where nothing is actually created
    sources = Counter()
    done = duplicates = failed = 0
    for src in files:
        try:
            date, has_time, source = find_date(src, not args.no_file_date)
            folder = args.output / folder_for(date, args.by)

            existing = duplicate_finder.find(src, folder)
            if existing:
                shown = existing.relative_to(args.output).as_posix()
                print(f"  [duplicate] {src.name} (an identical file is already at {shown})")
                duplicates += 1
                continue

            name = src.name
            if args.rename and date:
                stamp = date.strftime("%Y-%m-%d %H.%M.%S") if has_time else date.strftime("%Y-%m-%d")
                name = stamp + src.suffix.lower()
            dest = free_name(folder / name, taken_names)
            size = src.stat().st_size

            label = f"would {action}" if args.dry_run else ("moved" if args.move else "copied")
            print(f"  [{label}] {src.name} -> {dest.relative_to(args.output).as_posix()}  ({source})")
            if not args.dry_run:
                folder.mkdir(parents=True, exist_ok=True)
                if args.move:
                    shutil.move(str(src), str(dest))
                else:
                    shutil.copy2(src, dest)  # copy2 keeps the file's original dates
            taken_names.add(str(dest).lower())
            duplicate_finder.add(folder, size, src if args.dry_run else dest, dest)
            sources[source] += 1
            done += 1
        except Exception as error:
            print(f"  [fail] {src.name}: {error}")
            failed += 1

    past = "moved" if args.move else "copied"
    verb = f"would be {past}" if args.dry_run else past
    print(f"\nDone: {done} {verb}, {duplicates} duplicate(s) skipped, {failed} failed.")
    if sources:
        print("Dates came from: " + ", ".join(f"{name} {count}" for name, count in sources.most_common()))
    if sources["file date"]:
        print(f"  Note: {sources['file date']} file(s) had no date inside the photo or in the name, so the file's own\n"
              "  date was used. That can be wrong if the files were downloaded or copied from somewhere.\n"
              "  Use --no-file-date to put those in an 'Unknown date' folder instead.")
    if not args.dry_run:
        print(f"Organized files are in: {args.output}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        sys.exit(1)
