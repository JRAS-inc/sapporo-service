#!/usr/bin/env python3
# coding: utf-8
# pylint: disable=consider-using-with
import os
import shlex
import shutil
import signal
import subprocess as sp
import tempfile
from os import environ
from pathlib import Path
from time import sleep
from typing import Generator

import pytest
from pytest import MonkeyPatch

UNIT_TEST_DIR = Path(__file__).parent.resolve()
ROOT_DIR = UNIT_TEST_DIR.parent.parent.resolve()

TEST_HOST = "127.0.0.1"
TEST_PORT = "8888"


@pytest.fixture()
def tmpdir():  # type: ignore
    with tempfile.TemporaryDirectory() as tempdir:
        yield Path(tempdir)


@pytest.fixture
def delete_env_vars(monkeypatch: MonkeyPatch):  # type: ignore
    sapporo_envs = {key: value for key, value in os.environ.items() if key.startswith("SAPPORO")}

    for key in sapporo_envs:
        monkeypatch.delenv(key, raising=False)

    yield  # execute the test function

    # restore the original environment variables after the test function
    for key, value in sapporo_envs.items():
        monkeypatch.setenv(key, value)


@pytest.fixture()
def setup_test_server() -> Generator[None, None, None]:
    tempdir = tempfile.mkdtemp()
    if environ.get("TEST_SERVER_MODE", "uwsgi") == "uwsgi":
        proc = sp.Popen(shlex.split(f"uwsgi "
                                    f"--http {TEST_HOST}:{TEST_PORT} "
                                    f"--chdir {str(ROOT_DIR)} "
                                    "--module sapporo.uwsgi "
                                    "--callable app "
                                    "--master --need-app --single-interpreter "
                                    "--enable-threads --die-on-term --vacuum"),
                        cwd=str(UNIT_TEST_DIR),
                        env={"SAPPORO_DEBUG": str(True),
                             "SAPPORO_RUN_DIR": str(tempdir),
                             "PATH": os.environ.get("PATH", "")},
                        encoding="utf-8",
                        stdout=sp.PIPE, stderr=sp.PIPE)
    else:
        proc = sp.Popen(shlex.split(f"sapporo "
                                    f"--host {TEST_HOST} --port {TEST_PORT} "
                                    f"--run-dir {tempdir} "),
                        cwd=str(UNIT_TEST_DIR),
                        env={"SAPPORO_HOST": str(TEST_HOST),
                             "SAPPORO_PORT": str(TEST_PORT),
                             "SAPPORO_DEBUG": str(True),
                             "SAPPORO_RUN_DIR": str(tempdir),
                             "PATH": os.environ.get("PATH", "")},
                        encoding="utf-8",
                        stdout=sp.PIPE, stderr=sp.PIPE)
    sleep(3)
    if proc.poll() is not None:
        stderr = proc.communicate()[1]
        raise Exception(
            f"Failed to start the test server.\n{str(stderr)}")
    yield
    os.kill(proc.pid, signal.SIGTERM)
    sleep(3)
    try:
        shutil.rmtree(tempdir)
    except Exception:
        pass
