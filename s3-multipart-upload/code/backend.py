"""The backend's side of the upload design in note 00: every call here needs AWS credentials."""

import boto3
from botocore.config import Config

URL_LIFETIME_SECONDS = 900


class Backend:
    def __init__(self, bucket: str):
        # SigV4, with the bucket name in the host so presigned URLs target the bucket's Region
        config = Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
        self.s3 = boto3.client("s3", config=config)
        self.bucket = bucket

    def prepare(self, key: str) -> str:
        """Step 1: start a multipart upload and return its ID."""
        return self.s3.create_multipart_upload(Bucket=self.bucket, Key=key)["UploadId"]

    def list_parts(self, key: str, upload_id: str) -> dict[int, str] | None:
        """Step 2: part number to ETag for each part S3 has, or None if the upload is gone."""
        pages = self.s3.get_paginator("list_parts").paginate(
            Bucket=self.bucket, Key=key, UploadId=upload_id
        )
        try:
            return {
                part["PartNumber"]: part["ETag"]
                for page in pages
                for part in page.get("Parts", [])
            }
        except self.s3.exceptions.NoSuchUpload:
            return None

    def presign(self, key: str, upload_id: str, part_number: int) -> str:
        """Step 3: a URL that allows a PUT of this one part until the URL expires."""
        return self.s3.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=URL_LIFETIME_SECONDS,
        )

    def complete(self, key: str, upload_id: str, etags: dict[int, str], size: int) -> None:
        """Step 5: tell S3 to assemble the object from these parts."""
        parts = [{"PartNumber": number, "ETag": etags[number]} for number in sorted(etags)]
        self.s3.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
            MpuObjectSize=size,  # S3 rejects the request if the object would be another size
        )

    def abort(self, key: str, upload_id: str) -> None:
        """Discard an upload and its parts. An upload that is already gone is fine."""
        try:
            self.s3.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        except self.s3.exceptions.NoSuchUpload:
            pass
