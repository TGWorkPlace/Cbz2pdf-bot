"""
converter.py — CBZ/CBR -> PDF conversion helpers.

CBZ files are plain ZIP archives of images, extracted with the stdlib
`zipfile` module. CBR files are RAR archives, extracted by shelling out
to the `unar` CLI tool (The Unarchiver), which is free/open-source and
handles both classic RAR and RAR5 archives without needing the
proprietary `unrar` binary.
"""

import os
import re
import shutil
import zipfile
import subprocess

from PIL import Image
import img2pdf

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


class ConversionError(Exception):
    """Raised when extraction or conversion fails."""


def _natural_sort_key(path: str):
    """Sort like 'page2' before 'page10' instead of lexicographically."""
    name = os.path.basename(path)
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def extract_cbz(archive_path: str, dest_dir: str) -> None:
    try:
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile as e:
        raise ConversionError(f"Not a valid CBZ/ZIP file: {e}")


def extract_cbr(archive_path: str, dest_dir: str) -> None:
    os.makedirs(dest_dir, exist_ok=True)
    if not shutil.which("unar"):
        raise ConversionError(
            "The 'unar' tool is not installed on the server, so CBR files "
            "can't be extracted. Ask the bot host to install the 'unar' package."
        )
    result = subprocess.run(
        ["unar", "-quiet", "-force-overwrite", "-output-directory", dest_dir, archive_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ConversionError(f"Failed to extract CBR file: {result.stderr.strip() or 'unknown error'}")


def collect_images(root_dir: str) -> list:
    images = []
    for dirpath, _dirs, files in os.walk(root_dir):
        for fname in files:
            if os.path.splitext(fname)[1].lower() in IMAGE_EXTS:
                images.append(os.path.join(dirpath, fname))
    images.sort(key=_natural_sort_key)
    return images


def images_to_pdf(image_paths: list, output_path: str) -> None:
    if not image_paths:
        raise ConversionError("No image pages were found inside the archive.")

    # Normalize every page to plain RGB JPEG first. This fixes odd modes
    # (CMYK, palette, RGBA with alpha, corrupt EXIF) that make img2pdf choke,
    # and keeps output file size reasonable.
    normalized_dir = output_path + "_pages"
    os.makedirs(normalized_dir, exist_ok=True)
    normalized = []
    try:
        for i, src in enumerate(image_paths):
            try:
                with Image.open(src) as img:
                    img.load()
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    out_path = os.path.join(normalized_dir, f"{i:06d}.jpg")
                    img.save(out_path, "JPEG", quality=92)
                    normalized.append(out_path)
            except Exception:
                # Skip unreadable/corrupt pages rather than failing the whole book.
                continue

        if not normalized:
            raise ConversionError("None of the pages inside the archive could be read as images.")

        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(normalized))
    finally:
        shutil.rmtree(normalized_dir, ignore_errors=True)


def convert_to_pdf(archive_path: str, work_dir: str, output_path: str, is_cbr: bool) -> str:
    """
    Extract archive_path (cbz or cbr) into work_dir, gather the images,
    and write a PDF to output_path. Returns output_path on success.
    """
    extract_dir = os.path.join(work_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    if is_cbr:
        extract_cbr(archive_path, extract_dir)
    else:
        extract_cbz(archive_path, extract_dir)

    images = collect_images(extract_dir)
    images_to_pdf(images, output_path)
    return output_path
