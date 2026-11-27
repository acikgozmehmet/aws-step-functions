"""Shared pytest setup: every test runs against its own temporary AWS Emulator."""

import json
import os
import shutil
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import boto3
import pytest
from fault_proxy import FaultProxy

EMULATOR_ACCOUNT = "000000000000"
REGION = "us-east-1"
START_TIMEOUT_SECONDS = 30


def _read_endpoint(log_path: Path) -> str | None:
    """Return the endpoint URL from the startup log, if it is there yet."""
    for line in log_path.read_text().splitlines():
        try:
            return json.loads(line)["fields"]["endpoint_url"]
        except (ValueError, KeyError, TypeError):
            continue
    return None


def _is_healthy(endpoint: str, ca_file: Path) -> bool:
    try:
        context = ssl.create_default_context(cafile=ca_file)
        url = f"{endpoint}/__admin/health"
        with urllib.request.urlopen(url, context=context, timeout=2) as response:
            return response.status == 200
    except OSError:
        return False


def _wait_until_ready(process: subprocess.Popen, log_path: Path, home: Path) -> tuple[str, Path]:
    """Return the endpoint URL and settings folder once the emulator answers."""
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline and process.poll() is None:
        endpoint = _read_endpoint(log_path)
        if endpoint:
            settings = home / ".aws" / "emulator" / str(urlparse(endpoint).port)
            if _is_healthy(endpoint, settings / "ca.pem"):
                return endpoint, settings
        time.sleep(0.05)
    pytest.fail(f"AWS Emulator did not start:\n{log_path.read_text()}")


@pytest.fixture(autouse=True)
def emulator(tmp_path, monkeypatch):
    """Start a fresh emulator, point boto3 at it, and stop it after the test."""
    binary = shutil.which("aws-emulator")
    if binary is None:
        pytest.fail("aws-emulator is not installed (see README.md)")

    # No test may see real credentials or settings from the shell.
    for name in list(os.environ):
        if name.startswith("AWS_"):
            monkeypatch.delenv(name)

    # A temporary home keeps the emulator's files out of ~/.aws.
    home = tmp_path / "emulator-home"
    home.mkdir()
    log_path = tmp_path / "emulator.log"
    with log_path.open("w") as log:
        process = subprocess.Popen(
            [binary, "-p", "0", "-t", "off", "--idle-timeout", "300"],
            env={**os.environ, "HOME": str(home)},
            stdout=log,
            stderr=subprocess.STDOUT,
        )

    try:
        endpoint, settings = _wait_until_ready(process, log_path, home)

        monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint)
        monkeypatch.setenv("AWS_CONFIG_FILE", str(settings / "config"))
        monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(settings / "emulator_credentials"))
        monkeypatch.setenv("AWS_REGION", REGION)
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
        # upload.py sends parts with urllib, which reads this and not the SDK's ca_bundle.
        monkeypatch.setenv("SSL_CERT_FILE", str(settings / "ca.pem"))
        # boto3 caches a default session, which would keep older settings.
        monkeypatch.setattr(boto3, "DEFAULT_SESSION", None)

        sts = boto3.client("sts")
        if sts.meta.endpoint_url != endpoint:
            pytest.fail(f"boto3 points at {sts.meta.endpoint_url}, not the emulator")
        if sts.get_caller_identity()["Account"] != EMULATOR_ACCOUNT:
            pytest.fail("Not connected to the emulator account")

        yield endpoint
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def s3(emulator):
    """The test's own client, always connected straight to the emulator."""
    return boto3.client("s3", endpoint_url=emulator)


@pytest.fixture
def proxy(emulator, monkeypatch):
    """Route upload.py through a relay that can break its connection."""
    relay = FaultProxy(urlparse(emulator).port)
    monkeypatch.setenv("AWS_ENDPOINT_URL", relay.endpoint)
    yield relay
    relay.close()
