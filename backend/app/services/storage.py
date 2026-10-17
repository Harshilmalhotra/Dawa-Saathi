from pathlib import Path
from uuid import uuid4
from PIL import Image as PILImage
from app.config import settings

def save_upload(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    key = f"{uuid4()}.jpg"
    if settings.storage_backend == "s3":
        import boto3
        client = boto3.client("s3", endpoint_url=settings.s3_endpoint, region_name=settings.s3_region, aws_access_key_id=settings.s3_key, aws_secret_access_key=settings.s3_secret)
        import io
        with PILImage.open(io.BytesIO(data)) as im:
            im.thumbnail((1600, 1600)); out = io.BytesIO(); im.convert("RGB").save(out, format="JPEG")
        client.put_object(Bucket=settings.s3_bucket, Key=key, Body=out.getvalue(), ContentType="image/jpeg")
        return key
    root = Path(settings.upload_dir); root.mkdir(parents=True, exist_ok=True)
    import io
    with PILImage.open(io.BytesIO(data)) as im:
        im.thumbnail((1600, 1600)); im.convert("RGB").save(root / key, format="JPEG")
    return str(root / key)

def read_image(key: str) -> bytes:
    if settings.storage_backend == "s3":
        import boto3
        obj = boto3.client("s3", endpoint_url=settings.s3_endpoint, region_name=settings.s3_region, aws_access_key_id=settings.s3_key, aws_secret_access_key=settings.s3_secret).get_object(Bucket=settings.s3_bucket, Key=key)
        return obj["Body"].read()
    return Path(key).read_bytes()
