"""Give a theatre photo the site's look: black and white, contrast evened out,
and a faint purple tint, so photos from different sources sit together.

    python tools/grade_photo.py in.jpg src/cineclock/static/rooms/viff-main.jpg

Needs Pillow (pip install pillow). Not part of the site build.
"""

import sys

from PIL import Image, ImageEnhance, ImageOps

MAX_WIDTH = 1400


def grade(image: Image.Image) -> Image.Image:
    grey = ImageOps.exif_transpose(image).convert("L")
    grey = ImageOps.autocontrast(grey, cutoff=1)
    grey = ImageEnhance.Contrast(grey).enhance(1.08)
    return ImageOps.colorize(grey, black="#07080b", mid="#5b5468", white="#f1ecf7", midpoint=110)


def main(src: str, dest: str) -> None:
    out = grade(Image.open(src))
    if out.width > MAX_WIDTH:
        out = out.resize((MAX_WIDTH, round(out.height * MAX_WIDTH / out.width)), Image.LANCZOS)
    out.save(dest, quality=80, optimize=True, progressive=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
