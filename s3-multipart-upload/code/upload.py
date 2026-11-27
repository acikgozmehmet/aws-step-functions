# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3"]
# ///
"""Resumable multipart upload through presigned URLs, following study note 00.

This file plays the browser: it splits the file, remembers the upload, and sends
each part with a plain HTTP PUT. backend.py plays the server.
"""

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from backend import Backend

MIB = 1024 * 1024
DEFAULT_PART_SIZE = 10 * MIB
MAX_PARTS = 10_000
PUT_TIMEOUT_SECONDS = 300  # can cover sending a whole part, so keep it generous


class UploadError(Exception):
    """A problem the person running the script has to act on."""


def choose_part_size(file_size: int) -> int:
    """10 MiB, or larger when that would need more than 10,000 parts."""
    return max(DEFAULT_PART_SIZE, math.ceil(file_size / MAX_PARTS))


# The state file stands in for the browser's localStorage.


def state_file_for(path: Path) -> Path:
    return path.with_name(path.name + ".upload.json")


def load_state(state_file: Path) -> dict | None:
    return json.loads(state_file.read_text()) if state_file.exists() else None


def save_state(state_file: Path, state: dict) -> None:
    # Write, then rename, so an interrupted write can't leave half a file
    temporary = state_file.with_name(state_file.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2))
    temporary.replace(state_file)


def check_destination(state: dict, bucket: str, key: str, state_file: Path) -> None:
    if (state["bucket"], state["key"]) != (bucket, key):
        raise UploadError(
            f"{state_file} belongs to an upload to s3://{state['bucket']}/{state['key']}. "
            "Finish or --abort that upload first."
        )


def file_version(path: Path) -> dict:
    """What has to stay the same for parts from different runs to belong together."""
    stat = path.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def is_same_file(state: dict, path: Path) -> bool:
    return all(state[name] == value for name, value in file_version(path).items())


def resume_or_prepare(backend: Backend, path: Path, key: str, state_file: Path) -> dict:
    """Steps 1, 2 and 6: return the upload state, listing only parts that S3 confirms."""
    state = load_state(state_file)
    if state:
        check_destination(state, backend.bucket, key, state_file)
        if not is_same_file(state, path):
            print("The file changed since the last run. Aborting the old upload.")
            backend.abort(key, state["upload_id"])
        else:
            in_s3 = backend.list_parts(key, state["upload_id"])
            if in_s3 is not None:
                # A part counts only if we recorded it and S3 has that same ETag
                state["parts"] = {
                    number: etag
                    for number, etag in state["parts"].items()
                    if in_s3.get(int(number)) == etag
                }
                print(f"Resuming. Parts already in S3: {len(state['parts'])}")
                return state
            print("The saved upload no longer exists in S3. Starting over.")

    version = file_version(path)
    state = {
        "bucket": backend.bucket,
        "key": key,
        "upload_id": backend.prepare(key),
        **version,
        "part_size": choose_part_size(version["size"]),
        "parts": {},
    }
    save_state(state_file, state)
    return state


def put_part(url: str, data: bytes) -> str:
    """Step 4: send one part straight to S3 and return its ETag. Needs no AWS credentials."""
    request = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": "application/octet-stream"}
    )
    with urllib.request.urlopen(request, timeout=PUT_TIMEOUT_SECONDS) as response:
        return response.headers["ETag"]


def upload(backend: Backend, path: Path, key: str, stop_after: int | None = None) -> None:
    """Send the missing parts, then complete the upload."""
    if path.stat().st_size == 0:
        raise UploadError("The file is empty. Upload it with a single PUT instead.")
    state_file = state_file_for(path)
    state = resume_or_prepare(backend, path, key, state_file)
    upload_id, part_size = state["upload_id"], state["part_size"]
    total = math.ceil(state["size"] / part_size)
    missing = [number for number in range(1, total + 1) if str(number) not in state["parts"]]

    with path.open("rb") as source:
        for number in missing[:stop_after]:
            source.seek((number - 1) * part_size)
            data = source.read(part_size)
            url = backend.presign(key, upload_id, number)
            state["parts"][str(number)] = put_part(url, data)
            save_state(state_file, state)
            print(f"Part {number}/{total}: sent {len(data)} bytes")

    if stop_after is not None and stop_after < len(missing):
        print("Stopped early. Run again to send the remaining parts.")
        return
    if not is_same_file(state, path):
        raise UploadError("The file changed during the upload. Run again to start over.")
    etags = {int(number): etag for number, etag in state["parts"].items()}
    backend.complete(key, upload_id, etags, state["size"])
    state_file.unlink()
    print(f"Completed s3://{backend.bucket}/{key}")


def abort(backend: Backend, path: Path, key: str) -> None:
    state_file = state_file_for(path)
    state = load_state(state_file)
    if state is None:
        raise UploadError(f"Nothing to abort: {state_file} does not exist.")
    check_destination(state, backend.bucket, key, state_file)
    backend.abort(key, state["upload_id"])
    state_file.unlink()
    print("Aborted.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("bucket")
    parser.add_argument("file", type=Path)
    parser.add_argument("--key", help="object key (default: the file name)")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--stop-after", type=int, metavar="N", help="send N parts and stop, to try out resuming"
    )
    action.add_argument("--abort", action="store_true", help="discard the unfinished upload")
    args = parser.parse_args()
    if not args.abort and not args.file.is_file():
        parser.error(f"no such file: {args.file}")
    key = args.key or args.file.name

    try:
        backend = Backend(args.bucket)
        if args.abort:
            abort(backend, args.file, key)
        else:
            upload(backend, args.file, key, args.stop_after)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted. Run the same command again to resume.", file=sys.stderr)
        return 130
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        print(f"Error: S3 rejected a part ({error.code}): {detail}", file=sys.stderr)
    except OSError as error:
        print(f"Error: {error}\nRun the same command again to resume.", file=sys.stderr)
    except (UploadError, BotoCoreError, ClientError) as error:
        print(f"Error: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
