import logging
import os
import time
from pathlib import Path

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache MinIO health status briefly to avoid repeated timeouts when offline
_MINIO_HEALTH_CACHE = {"status": None, "checked_at": 0}
_MINIO_CACHE_TTL = 15.0  # seconds


def get_internal_s3_client():
    """Client for server-side S3 calls (head_bucket, head_object, get_object, etc.)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT_INTERNAL,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name=getattr(settings, "MINIO_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=1.5, read_timeout=2.0),
        use_ssl=settings.MINIO_SECURE,
    )


def get_public_s3_client():
    """Client for signing presigned URLs that the browser can reach."""
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_PUBLIC_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name=getattr(settings, "MINIO_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, connect_timeout=1.5, read_timeout=2.0),
        use_ssl=settings.MINIO_SECURE,
    )


def is_minio_available(force_refresh: bool = False) -> bool:
    """Verifies MinIO is accessible with cached fast probing."""
    now = time.time()
    if not force_refresh and _MINIO_HEALTH_CACHE["status"] is not None:
        if (now - _MINIO_HEALTH_CACHE["checked_at"]) < _MINIO_CACHE_TTL:
            return _MINIO_HEALTH_CACHE["status"]

    try:
        s3 = get_internal_s3_client()
        s3.head_bucket(Bucket=settings.MINIO_BUCKET_NAME)
        _MINIO_HEALTH_CACHE["status"] = True
        _MINIO_HEALTH_CACHE["checked_at"] = now
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.warning(f"MinIO health check returned ClientError: {error_code} - {e}")
        status_ok = error_code in ["404", "NoSuchBucket"] or False
        _MINIO_HEALTH_CACHE["status"] = status_ok
        _MINIO_HEALTH_CACHE["checked_at"] = now
        return status_ok
    except Exception as e:
        logger.info(f"MinIO service is offline/unreachable: {e}")
        _MINIO_HEALTH_CACHE["status"] = False
        _MINIO_HEALTH_CACHE["checked_at"] = now
        return False


def check_minio_health() -> bool:
    """Verifies MinIO is accessible by checking bucket status (head_bucket)."""
    return is_minio_available(force_refresh=True)


def save_file_dual(object_key: str, data: bytes, content_type: str = "image/jpeg") -> dict:
    """
    Dual-mode image storage:
    - First preference: Upload directly to MinIO S3 object storage.
    - Graceful fallback: Save to local Django media directory (settings.MEDIA_ROOT).
    """
    if is_minio_available():
        try:
            put_object_bytes(object_key, data, content_type)
            return {"storage": "minio", "object_key": object_key}
        except Exception as e:
            logger.warning(f"MinIO upload failed despite health check: {e}. Falling back to local storage.")
            _MINIO_HEALTH_CACHE["status"] = False
            _MINIO_HEALTH_CACHE["checked_at"] = time.time()

    # Local fallback
    local_path = Path(settings.MEDIA_ROOT) / object_key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(data)
    return {"storage": "local", "object_key": object_key}


def get_file_bytes_dual(object_key: str) -> bytes:
    """Retrieves file bytes from local MEDIA_ROOT if present, or downloads from MinIO."""
    local_path = Path(settings.MEDIA_ROOT) / object_key
    if local_path.exists():
        return local_path.read_bytes()

    if is_minio_available():
        return get_object_bytes(object_key)

    raise FileNotFoundError(f"Object {object_key} not found locally or in MinIO.")


def get_file_url(object_key: str, ttl_seconds: int = 600) -> str:
    """
    Returns signed MinIO URL if MinIO is running and accessible;
    otherwise returns relative local media URL '/media/{object_key}'.
    """
    if not object_key:
        return ""

    local_path = Path(settings.MEDIA_ROOT) / object_key
    if local_path.exists():
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        return f"{media_url.rstrip('/')}/{object_key}"

    if is_minio_available():
        try:
            return generate_presigned_get(object_key, ttl_seconds)
        except Exception:
            pass

    media_url = getattr(settings, "MEDIA_URL", "/media/")
    return f"{media_url.rstrip('/')}/{object_key}"



def generate_presigned_post(object_key: str, content_type: str, max_size_bytes: int = 10 * 1024 * 1024):
    """
    Generates a presigned POST policy allowing direct browser upload to MinIO.
    Enforces content-type and content-length-range.
    """
    s3_pub = get_public_s3_client()
    conditions = [
        {"bucket": settings.MINIO_BUCKET_NAME},
        {"key": object_key},
        ["starts-with", "$Content-Type", content_type.split(";")[0]],
        ["content-length-range", 1, max_size_bytes],
    ]

    fields = {
        "Content-Type": content_type,
    }

    presigned = s3_pub.generate_presigned_post(
        Bucket=settings.MINIO_BUCKET_NAME,
        Key=object_key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=3600,
    )
    return presigned


def generate_presigned_get(object_key: str, ttl_seconds: int = 600) -> str:
    """Generates a presigned GET URL for viewing private attachments."""
    s3_pub = get_public_s3_client()
    return s3_pub.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.MINIO_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=ttl_seconds,
    )


def head_object(object_key: str):
    """Fetches metadata for an object from MinIO."""
    s3 = get_internal_s3_client()
    return s3.head_object(Bucket=settings.MINIO_BUCKET_NAME, Key=object_key)


def get_object_bytes(object_key: str) -> bytes:
    """Downloads object bytes from MinIO for server-side processing/thumbnailing."""
    s3 = get_internal_s3_client()
    response = s3.get_object(Bucket=settings.MINIO_BUCKET_NAME, Key=object_key)
    return response["Body"].read()


def put_object_bytes(object_key: str, data: bytes, content_type: str):
    """Uploads bytes directly to MinIO (used for thumbnails, generated assets)."""
    s3 = get_internal_s3_client()
    s3.put_object(
        Bucket=settings.MINIO_BUCKET_NAME,
        Key=object_key,
        Body=data,
        ContentType=content_type,
    )
