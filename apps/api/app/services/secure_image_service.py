"""Safety checks and metadata removal for uploaded evidence images."""

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.core.config import Settings


class ImageSecurityError(RuntimeError):
    pass


@dataclass(frozen=True)
class SanitizedImage:
    body: bytes
    metadata: dict[str, int | str | bool]


_IMAGE_FORMATS = {
    "image/png": "PNG",
    "image/jpeg": "JPEG",
    "image/webp": "WEBP",
}


def sanitize_image(settings: Settings, *, content_type: str, body: bytes) -> SanitizedImage:
    """Decode allowed images within limits and re-encode them without metadata."""
    expected_format = _IMAGE_FORMATS.get(content_type)
    if expected_format is None:
        raise ImageSecurityError("Image content type is not supported.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(body)) as image:
                if image.format != expected_format:
                    raise ImageSecurityError("Image content does not match its MIME type.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ImageSecurityError("Animated images are not allowed.")
                width, height = image.size
                pixel_count = width * height
                if pixel_count > settings.max_image_pixels:
                    raise ImageSecurityError("Image exceeds the configured pixel limit.")
                decoded_bytes = _estimated_decoded_bytes(image)
                if decoded_bytes > settings.max_image_decoded_bytes:
                    raise ImageSecurityError("Image exceeds the configured decoded-size limit.")
                if decoded_bytes / max(len(body), 1) > settings.max_image_decompression_ratio:
                    raise ImageSecurityError(
                        "Image exceeds the configured decompression ratio limit."
                    )
                image.load()
                sanitized_body = _encode_without_metadata(image, expected_format)
    except ImageSecurityError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
    ):
        raise ImageSecurityError("Image could not be parsed safely.") from None
    return SanitizedImage(
        body=sanitized_body,
        metadata={
            "image_sanitized": True,
            "image_width": width,
            "image_height": height,
            "image_pixels": pixel_count,
            "image_decoded_bytes": decoded_bytes,
            "image_format": expected_format,
        },
    )


def _estimated_decoded_bytes(image: Image.Image) -> int:
    component_bytes = 2 if "16" in image.mode else 4 if image.mode in {"F", "I"} else 1
    return image.width * image.height * len(image.getbands()) * component_bytes


def _encode_without_metadata(image: Image.Image, image_format: str) -> bytes:
    output = BytesIO()
    sanitized = image.copy()
    if image_format == "JPEG" and sanitized.mode not in {"L", "RGB", "CMYK"}:
        sanitized = sanitized.convert("RGB")
    sanitized.save(output, format=image_format)
    return output.getvalue()
