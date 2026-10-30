from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import warnings

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

UPLOAD_DIR = Path("/app/media/uploads")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_EDGE = 2048
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Keep large decodes off the event loop and bound concurrent image memory use.
_image_slots = asyncio.Semaphore(2)


def _encode_image(contents: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(contents)) as source:
                if source.format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY, "仅支持 JPG、PNG 或 WebP 图片"
                    )
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "图片像素不能超过 2000 万"
                    )
                if getattr(source, "is_animated", False):
                    raise HTTPException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY, "请上传静态图片，不支持动画"
                    )
                source.load()
                with ImageOps.exif_transpose(source) as oriented:
                    oriented.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
                    mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
                    with oriented.convert(mode) as converted, Image.new(mode, converted.size) as clean:
                        # New pixels ensure EXIF, text, ICC and other uploaded metadata are discarded.
                        clean.paste(converted)
                        output = BytesIO()
                        clean.save(output, format="WEBP", quality=85, method=4)
                        return output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "图片像素不能超过 2000 万"
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "图片损坏或格式不受支持"
        ) from exc


def _save_image(contents: bytes) -> dict[str, str]:
    encoded = _encode_image(contents)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # Never use the supplied filename. Exclusive creation also prevents overwriting files.
    for _ in range(3):
        filename = f"{uuid4().hex}.webp"
        destination = UPLOAD_DIR / filename
        try:
            output = destination.open("xb")
        except FileExistsError:
            continue
        try:
            with output:
                output.write(encoded)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return {"url": f"/media/uploads/{filename}"}
    raise RuntimeError("Unable to allocate an image filename")


async def save_menu_image(file: UploadFile) -> dict[str, str]:
    try:
        async with _image_slots:
            # Bound both buffered input and decoding; the extra byte detects oversize uploads.
            contents = await file.read(MAX_UPLOAD_BYTES + 1)
            if len(contents) > MAX_UPLOAD_BYTES:
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "图片文件不能超过 5 MB")
            try:
                return await run_in_threadpool(_save_image, contents)
            except (OSError, RuntimeError):
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE, "图片保存失败，请稍后重试"
                ) from None
    finally:
        await file.close()
