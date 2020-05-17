#!/usr/bin/env python3
# coding: utf-8
import os
import shlex
import signal
from pathlib import Path
from subprocess import Popen
from typing import Dict, List, Optional

from flask import abort, current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from sapporo.type import Log, RunLog, RunRequest, ServiceInfo, State
from sapporo.util import (generate_service_info, get_all_run_ids, get_path,
                          get_run_dir, get_state, read_file, write_file)


def validate_run_request(run_request: RunRequest) -> None:
    required_fields: List[str] = ["workflow_params",
                                  "workflow_type",
                                  "workflow_type_version",
                                  "workflow_url",
                                  "workflow_engine_name"]
    for field in required_fields:
        if field not in run_request:
            abort(400,
                  f"{field} not included in the form data of the request.")


def validate_wf_type(wf_type: str, wf_type_version: str) -> None:
    service_info: ServiceInfo = generate_service_info()
    wf_type_versions = service_info["workflow_type_versions"]

    available_wf_types: List[str] = \
        list(map(str, wf_type_versions.keys()))
    if wf_type not in available_wf_types:
        abort(400,
              f"{wf_type}, the workflow_type specified in the " +
              f"request, is not included in {available_wf_types}, " +
              "the available workflow_types.")

    available_wf_versions: List[str] = \
        list(map(str, wf_type_versions[wf_type]["workflow_type_version"]))
    if wf_type_version not in available_wf_versions:
        abort(400,
              f"{wf_type_version}, the workflow_type_version specified in " +
              f"the request, is not included in {available_wf_versions}, " +
              "the available workflow_type_versions.")


def prepare_exe_dir(run_id: str,
                    request_files: Dict[str, FileStorage]) -> None:
    exe_dir: Path = get_path(run_id, "exe_dir")
    exe_dir.mkdir(parents=True, exist_ok=True)
    for file in request_files.values():
        if file.filename != "":
            filename: str = secure_filename(file.filename)
            file.save(exe_dir.joinpath(filename))  # type: ignore


def fork_run(run_id: str) -> None:
    run_dir: Path = get_run_dir(run_id)
    stdout: Path = get_path(run_id, "stdout")
    stderr: Path = get_path(run_id, "stderr")
    cmd: str = f"/bin/bash {current_app.config['RUN_SH']} {run_dir}"
    with stdout.open(mode="w") as f_stdout, stderr.open(mode="w") as f_stderr:
        process = Popen(shlex.split(cmd), stdout=f_stdout, stderr=f_stderr)
    pid: Optional[int] = process.pid
    if pid is not None:
        write_file(run_id, "pid", str(pid))


def validate_run_id(run_id: str) -> None:
    all_run_ids: List[str] = get_all_run_ids()
    if run_id not in all_run_ids:
        abort(404,
              f"The run_id {run_id} you requested does not exist, " +
              "please check with GET /runs.")


def get_run_log(run_id: str) -> RunLog:
    run_log: RunLog = {
        "run_id": run_id,
        "request": read_file(run_id, "run_request"),
        "state": get_state(run_id).name,  # type: ignore
        "run_log": get_log(run_id),
        "task_logs": read_file(run_id, "task_logs"),
        "outputs": read_file(run_id, "outputs")
    }

    return run_log


def get_log(run_id: str) -> Log:
    log: Log = {
        "name": "",
        "cmd": read_file(run_id, "cmd"),
        "start_time": read_file(run_id, "start_time"),
        "end_time": read_file(run_id, "end_time"),
        "stdout": read_file(run_id, "stdout"),
        "stderr": read_file(run_id, "stderr"),
        "exit_code": read_file(run_id, "exit_code")
    }

    return log


def cancel_run(run_id: str) -> None:
    state: State = get_state(run_id)
    if state == State.RUNNING:
        write_file(run_id, "state", State.CANCELING.name)
        pid: int = int(read_file(run_id, "pid"))
        os.kill(pid, signal.SIGUSR1)