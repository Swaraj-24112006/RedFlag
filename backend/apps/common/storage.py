import logging

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def get_internal_s3_client():
    """Client for server-side S3 calls (head_bucket, head_object, get_object, etc.)."""
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT_INTERNAL,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name=getattr(settings, "MINIO_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
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
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        use_ssl=settings.MINIO_SECURE,
    )


def check_minio_health() -> bool:
    """Verifies MinIO is accessible by checking bucket status (head_bucket)."""
    try:
        s3 = get_internal_s3_client()
        s3.head_bucket(Bucket=settings.MINIO_BUCKET_NAME)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        logger.warning(f"MinIO health check returned ClientError: {error_code} - {e}")
        # Bucket not found might mean MinIO is up but bucket not created yet
        return error_code in ["404", "NoSuchBucket"] or False
    except Exception as e:
        logger.warning(f"MinIO health check failed: {e}")
        return False


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
