from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

THUMBNAIL_MAX_EDGE = 256


def site_photo_thumbnail_path(
    data_dir: Path,
    project_id: int,
    max_edge: int = THUMBNAIL_MAX_EDGE,
) -> Path:
    return data_dir / "thumbnails" / f"{project_id}_{max_edge}.jpg"


def site_photo_thumbnail_url(project_id: int, max_edge: int = THUMBNAIL_MAX_EDGE) -> str:
    return f"/thumbnails/{project_id}_{max_edge}.jpg"


def ensure_site_photo_thumbnail(
    project_id: int,
    site_photo_path: str | Path | None,
    data_dir: Path,
    max_edge: int = THUMBNAIL_MAX_EDGE,
) -> str | None:
    if site_photo_path is None:
        return None

    thumb_path = site_photo_thumbnail_path(data_dir, project_id, max_edge)
    if thumb_path.exists():
        return site_photo_thumbnail_url(project_id, max_edge)

    source_path = Path(site_photo_path)
    if not source_path.exists():
        return None

    try:
        with Image.open(source_path) as source_image:
            image = ImageOps.exif_transpose(source_image)
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            image = _jpeg_ready(image)

            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(thumb_path, format="JPEG", quality=85, optimize=True)
    except (OSError, UnidentifiedImageError):
        return None

    return site_photo_thumbnail_url(project_id, max_edge)


def _jpeg_ready(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    return image.convert("RGB")
