"""End to end: run upload.py the way a user does, then check what S3 holds."""

import hashlib
import json
import os
import re
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import backend

UPLOAD_SCRIPT = Path(__file__).parent.parent / "upload.py"
BUCKET = "uploads"
MIB = 1024 * 1024
PART = 10 * MIB
SIZE = 25 * MIB  # the study note's example: parts of 10, 10 and 5 MiB


@pytest.fixture
def bucket(s3):
    s3.create_bucket(Bucket=BUCKET)


@pytest.fixture
def video(tmp_path, bucket):
    path = tmp_path / "video.mp4"
    path.write_bytes(os.urandom(SIZE))
    return path


# Running the script


def command(path, *options):
    return [sys.executable, str(UPLOAD_SCRIPT), BUCKET, str(path), *options]


def upload(path, *options, exit_code=0):
    """Run upload.py to the end and return everything it printed."""
    done = subprocess.run(
        command(path, *options), capture_output=True, text=True, timeout=60, check=False
    )
    output = done.stdout + done.stderr
    assert done.returncode == exit_code, output
    assert "Traceback" not in output
    return output


def sent_parts(output):
    return [int(number) for number in re.findall(r"^Part (\d+)/", output, re.MULTILINE)]


# Looking at the results


def state_file(path):
    return path.with_name(path.name + ".upload.json")


def saved_state(path):
    return json.loads(state_file(path).read_text())


def parts_in_s3(s3, path):
    """Part number to size, for the unfinished upload named in the state file."""
    response = s3.list_parts(Bucket=BUCKET, Key=path.name, UploadId=saved_state(path)["upload_id"])
    return {part["PartNumber"]: part["Size"] for part in response.get("Parts", [])}


def unfinished_uploads(s3):
    response = s3.list_multipart_uploads(Bucket=BUCKET)
    return [item["UploadId"] for item in response.get("Uploads", [])]


def object_keys(s3):
    response = s3.list_objects_v2(Bucket=BUCKET)
    return [item["Key"] for item in response.get("Contents", [])]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assert_uploaded(s3, path):
    """The object matches the file, and nothing is left over."""
    with s3.get_object(Bucket=BUCKET, Key=path.name)["Body"] as body:
        assert digest(body.read()) == digest(path.read_bytes())
    assert not state_file(path).exists()
    assert unfinished_uploads(s3) == []


# Uploading and resuming


def test_full_upload_stores_the_file(s3, video):
    output = upload(video)

    assert sent_parts(output) == [1, 2, 3]
    assert_uploaded(s3, video)
    assert s3.head_object(Bucket=BUCKET, Key=video.name)["ETag"].endswith('-3"')


def test_stop_then_resume_sends_only_the_rest(s3, video):
    output = upload(video, "--stop-after", "2")

    assert sent_parts(output) == [1, 2]
    assert parts_in_s3(s3, video) == {1: PART, 2: PART}
    assert list(saved_state(video)["parts"]) == ["1", "2"]
    assert object_keys(s3) == []  # no object until the upload is completed

    output = upload(video)

    assert "Parts already in S3: 2" in output
    assert sent_parts(output) == [3]
    assert_uploaded(s3, video)


def test_dropped_connection_resumes_at_the_failed_part(s3, video, proxy):
    proxy.arm("drop", 2)

    output = upload(video, exit_code=1)

    assert proxy.tripped.is_set()
    assert "Run the same command again to resume" in output
    assert parts_in_s3(s3, video) == {1: PART}  # S3 keeps nothing of a partial part
    assert list(saved_state(video)["parts"]) == ["1"]

    output = upload(video)

    assert sent_parts(output) == [2, 3]
    assert_uploaded(s3, video)


@pytest.mark.parametrize(
    ("interrupt", "exit_code"),
    [(signal.SIGKILL, -signal.SIGKILL), (signal.SIGINT, 130)],
    ids=["killed", "ctrl-c"],
)
def test_interrupted_in_the_middle_of_a_part(s3, video, proxy, interrupt, exit_code):
    proxy.arm("stall", 2)
    # Some shells start background jobs with Ctrl+C ignored, and a child inherits that.
    # With a handler set here, the child starts with the normal behaviour.
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        process = subprocess.Popen(
            command(video), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    finally:
        signal.signal(signal.SIGINT, previous)
    try:
        assert proxy.tripped.wait(30), "part 2 never started"
        process.send_signal(interrupt)
        _, errors = process.communicate(timeout=30)
    finally:
        process.kill()

    assert process.returncode == exit_code, errors
    assert "Traceback" not in errors
    if interrupt == signal.SIGINT:
        assert "Interrupted. Run the same command again to resume." in errors
    assert parts_in_s3(s3, video) == {1: PART}

    output = upload(video)

    assert sent_parts(output) == [2, 3]
    assert_uploaded(s3, video)


# When saved progress can't be trusted


def test_changed_file_starts_over(s3, video):
    upload(video, "--stop-after", "1")
    video.write_bytes(os.urandom(SIZE))  # same name and size, new content

    output = upload(video)

    assert "The file changed since the last run" in output
    assert sent_parts(output) == [1, 2, 3]
    assert_uploaded(s3, video)  # also shows the old upload was aborted


def test_upload_removed_from_s3_starts_over(s3, video):
    upload(video, "--stop-after", "1")
    upload_id = saved_state(video)["upload_id"]
    s3.abort_multipart_upload(Bucket=BUCKET, Key=video.name, UploadId=upload_id)

    output = upload(video)

    assert "The saved upload no longer exists in S3" in output
    assert sent_parts(output) == [1, 2, 3]
    assert_uploaded(s3, video)


def test_part_that_differs_in_s3_is_sent_again(s3, video):
    upload(video, "--stop-after", "2")
    s3.upload_part(
        Bucket=BUCKET,
        Key=video.name,
        UploadId=saved_state(video)["upload_id"],
        PartNumber=1,
        Body=os.urandom(PART),
    )

    output = upload(video)

    assert sent_parts(output) == [1, 3]
    assert_uploaded(s3, video)


def test_part_without_a_saved_etag_is_sent_again(s3, video):
    # As if the script died after S3 stored part 2, before saving its ETag
    upload(video, "--stop-after", "2")
    state = saved_state(video)
    del state["parts"]["2"]
    state_file(video).write_text(json.dumps(state))

    output = upload(video)

    assert sent_parts(output) == [2, 3]
    assert_uploaded(s3, video)


# Giving up, and refusing mistakes


def test_abort_discards_the_upload(s3, video):
    upload(video, "--stop-after", "1")

    output = upload(video, "--abort")

    assert "Aborted." in output
    assert unfinished_uploads(s3) == []
    assert object_keys(s3) == []
    assert not state_file(video).exists()


def test_a_different_key_is_refused_and_progress_is_kept(s3, video):
    upload(video, "--stop-after", "1")
    before = state_file(video).read_text()

    output = upload(video, "--key", "other.mp4", exit_code=1)

    assert "belongs to an upload to s3://uploads/video.mp4" in output
    assert state_file(video).read_text() == before
    assert parts_in_s3(s3, video) == {1: PART}


# What the backend signs. The emulator checks signatures, as S3 does.


def part_url():
    server = backend.Backend(BUCKET)
    upload_id = server.prepare("signed.bin")
    return server.presign("signed.bin", upload_id, 1)


def put(url):
    """PUT a few bytes and return the status code and any error text."""
    request = urllib.request.Request(
        url, data=b"part", method="PUT", headers={"Content-Type": "application/octet-stream"}
    )
    context = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    try:
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            return response.status, ""
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.read().decode()


def test_part_url_can_be_used_more_than_once(bucket):
    url = part_url()

    assert put(url) == (200, "")
    assert put(url) == (200, "")


@pytest.mark.parametrize(
    ("signed", "changed"),
    [("partNumber=1", "partNumber=2"), ("/signed.bin?", "/other.bin?")],
    ids=["part-number", "key"],
)
def test_altered_part_url_is_rejected(bucket, signed, changed):
    url = part_url()
    assert signed in url

    status, error = put(url.replace(signed, changed))

    assert status == 403
    assert "SignatureDoesNotMatch" in error


def test_expired_part_url_is_rejected(bucket, monkeypatch):
    monkeypatch.setattr(backend, "URL_LIFETIME_SECONDS", 1)
    url = part_url()
    time.sleep(2)

    status, error = put(url)

    assert status == 403
    assert "Request has expired" in error


# Large uploads


def test_list_parts_reads_past_the_first_page(s3, bucket):
    server = backend.Backend(BUCKET)
    upload_id = server.prepare("many.bin")
    numbers = range(1, 1002)  # S3 returns at most 1,000 parts per response
    for number in numbers:
        s3.upload_part(
            Bucket=BUCKET, Key="many.bin", UploadId=upload_id, PartNumber=number, Body=b"x"
        )

    assert sorted(server.list_parts("many.bin", upload_id)) == list(numbers)
