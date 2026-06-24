from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass

import psutil
import requests

from mypylib import MyPyClass
from mytoninstaller.context import InstallerContext
from mytoninstaller.utils import is_testnet


@dataclass(frozen=True)
class DumpMetadata:
    archive_name: str
    sha256: str
    archive_size: int
    disk_size: int


def download_dump(local: MyPyClass, ctx: InstallerContext) -> bool:
    local.add_log("start download_dump function", "debug")
    base_url = "https://dump.ton.org/dumps"
    dump_name = "latest"
    if is_testnet(ctx.paths.global_config_path):
        dump_name += '_testnet'
    dump_dir = ctx.paths.ton_db_dir
    dump_cache_dir = get_dump_cache_dir(ctx.paths.ton_work_dir)
    os.makedirs(dump_dir, exist_ok=True)
    os.makedirs(dump_cache_dir, exist_ok=True)
    cleanup_dump_temp_files(local, os.path.join(dump_dir, "latest.tar.lz"))
    cleanup_dump_temp_files(local, os.path.join(dump_cache_dir, "latest.tar.lz"))

    try:
        dump_metadata = get_dump_metadata(base_url, dump_name)
    except Exception as e:
        local.add_log(f"Failed to get dump metadata: {e}", "error")
        return False

    archive_name = dump_metadata.archive_name
    temp_file = os.path.join(dump_cache_dir, archive_name)
    cleanup_dump_temp_files(local, os.path.join(dump_dir, archive_name))
    cleanup_dump_temp_files(local, temp_file)
    print("dumpName:", archive_name)
    print("dumpSize:", dump_metadata.archive_size)
    print("dumpDiskSize:", dump_metadata.disk_size)
    print("dumpCacheDir:", dump_cache_dir)
    if not check_dump_space(local, dump_dir, dump_cache_dir, dump_metadata):
        return False

    # apt install
    apt_result = subprocess.run(["apt", "install", "plzip", "aria2", "curl", "-y"]).returncode
    if apt_result != 0:
        local.add_log(f"Failed to install dump tools with exit code {apt_result}", "error")
        return False

    # download dump using aria2c to a temporary file
    cmd = [
        "aria2c",
        "-x", "8",
        "-s", "8",
        "--enable-http-keep-alive=false",
        "--retry-wait=5",
        "--max-tries=20",
        "--connect-timeout=60",
        "--timeout=120",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--check-integrity=true",
        f"--checksum=sha-256={dump_metadata.sha256}",
        "-c",
        f"{base_url}/{archive_name}",
        "-d", dump_cache_dir,
        "-o", archive_name,
    ]
    download_started_at = time.monotonic()
    download_result = subprocess.run(cmd).returncode
    download_elapsed = format_elapsed_time(time.monotonic() - download_started_at)
    if download_result != 0 or not os.path.exists(temp_file):
        local.add_log(f"Dump download failed after {download_elapsed}: {temp_file}", "error")
        cleanup_dump_temp_files(local, temp_file)
        return False
    if os.path.getsize(temp_file) != dump_metadata.archive_size:
        local.add_log(f"Dump download size mismatch after {download_elapsed}: {temp_file}", "error")
        cleanup_dump_temp_files(local, temp_file)
        return False
    checksum_started_at = time.monotonic()
    checksum_result = verify_dump_checksum(local, dump_cache_dir, archive_name, dump_metadata.sha256)
    checksum_elapsed = format_elapsed_time(time.monotonic() - checksum_started_at)
    if checksum_result is False:
        local.add_log(f"Dump checksum verification failed after {checksum_elapsed}: {temp_file}", "error")
        cleanup_dump_temp_files(local, temp_file)
        return False
    local.add_log(f"Dump checksum verified in {checksum_elapsed}: {temp_file}", "info")

    if dump_bool_env("DUMP_VALIDATE_BEFORE_EXTRACT", False):
        validation_started_at = time.monotonic()
        validation_result = validate_dump_archive(local, temp_file)
        validation_elapsed = format_elapsed_time(time.monotonic() - validation_started_at)
        if validation_result != 0:
            local.add_log(f"Dump lzip validation failed after {validation_elapsed}: {temp_file}", "error")
            cleanup_dump_temp_files(local, temp_file)
            return False
        local.add_log(f"Dump lzip validation succeeded in {validation_elapsed}: {temp_file}", "info")

    # process the downloaded file
    msg = f"Dump downloaded to {temp_file} in {download_elapsed}. Starting extraction to {dump_dir}"
    print(msg, flush=True)
    local.add_log(msg, "info")
    extraction_started_at = time.monotonic()
    extraction_result = extract_dump(local, temp_file, dump_dir)
    extraction_elapsed = format_elapsed_time(time.monotonic() - extraction_started_at)
    if extraction_result != 0:
        local.add_log(f"Dump extraction failed after {extraction_elapsed}", "error")
        cleanup_dump_temp_files(local, temp_file)
        return False
    msg = f"Dump extracted to {dump_dir} in {extraction_elapsed}"
    print(msg, flush=True)
    local.add_log(msg, "info")

    # clean up the temporary file after processing
    cleanup_dump_temp_files(local, temp_file)
    return True


def cleanup_dump_temp_files(local: MyPyClass, temp_file: str) -> None:
    for path in [temp_file, temp_file + ".aria2"]:
        if os.path.exists(path):
            os.remove(path)
            local.add_log(f"Temporary file {path} removed", "debug")


def dump_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def dump_extract_threads() -> int:
    value = os.getenv("DUMP_EXTRACT_THREADS", "8")
    try:
        threads = int(value)
    except ValueError:
        return 8
    if threads < 1:
        return 8
    return threads


def get_dump_cache_dir(ton_work_dir: str) -> str:
    return os.getenv("DUMP_CACHE_DIR") or os.path.join(ton_work_dir, "dump-cache")


def check_dump_space(local: MyPyClass, dump_dir: str, dump_cache_dir: str, dump_metadata: DumpMetadata) -> bool:
    archive_size = dump_metadata.archive_size
    disk_size = dump_metadata.disk_size

    dump_usage = psutil.disk_usage(dump_dir)
    cache_usage = psutil.disk_usage(dump_cache_dir)

    if os.stat(dump_dir).st_dev == os.stat(dump_cache_dir).st_dev:
        need_space = archive_size + disk_size
        if need_space > dump_usage.free:
            local.add_log(f"Not enough disk space in {dump_dir}: need {need_space}, free {dump_usage.free}", "error")
            return False
        return True

    if archive_size > cache_usage.free:
        local.add_log(f"Not enough disk space in {dump_cache_dir}: need {archive_size}, free {cache_usage.free}", "error")
        return False
    if disk_size > dump_usage.free:
        local.add_log(f"Not enough disk space in {dump_dir}: need {disk_size}, free {dump_usage.free}", "error")
        return False
    return True


def get_dump_metadata(base_url: str, dump_name: str) -> DumpMetadata:
    latest_name = dump_fetch_text(f"{base_url}/{dump_name}.tar.name.txt", timeout=10)
    if not latest_name:
        raise RuntimeError(f"empty dump name for {dump_name}")

    metadata_name = os.path.basename(latest_name)
    archive_name = metadata_name
    if not archive_name.endswith(".lz"):
        archive_name += ".lz"
    else:
        metadata_name = archive_name[:-3]

    sha_text = dump_fetch_text(f"{base_url}/{metadata_name}.sha256sum.txt", timeout=10)
    sha_parts = sha_text.split()
    if not sha_parts:
        raise RuntimeError(f"empty dump sha256 for {metadata_name}")
    sha256 = sha_parts[0]
    if len(sha256) != 64:
        raise RuntimeError(f"invalid dump sha256 for {metadata_name}: {sha256}")
    if len(sha_parts) > 1 and os.path.basename(sha_parts[1]) != archive_name:
        raise RuntimeError(f"dump sha256 file does not match archive {archive_name}: {sha_parts[1]}")

    archive_size = int(dump_fetch_text(f"{base_url}/{metadata_name}.size.archive.txt", timeout=10))
    disk_size = int(dump_fetch_text(f"{base_url}/{metadata_name}.size.disk.txt", timeout=10))
    return DumpMetadata(
        archive_name=archive_name,
        sha256=sha256,
        archive_size=archive_size,
        disk_size=disk_size,
    )


def dump_fetch_text(url: str, timeout: int = 10) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text.strip()


def verify_dump_checksum(local: MyPyClass, dump_dir: str, archive_name: str, sha256: str) -> bool:
    checksum_line = f"{sha256}  {archive_name}\n"
    result = subprocess.run(
        ["sha256sum", "-c", "-"],
        input=checksum_line,
        text=True,
        cwd=dump_dir,
        capture_output=True,
    )
    output = "\n".join([result.stdout.strip(), result.stderr.strip()]).strip()
    if output:
        print(output, flush=True)
        local.add_log(output, "debug" if result.returncode == 0 else "error")
    return result.returncode == 0


def validate_dump_archive(local: MyPyClass, temp_file: str) -> int:
    threads = dump_extract_threads()
    local.add_log(f"Validating lzip archive before extraction: file={temp_file} threads={threads}", "info")
    return subprocess.run(["plzip", "-tvv", f"-n{threads}", temp_file]).returncode


def format_elapsed_time(elapsed: float) -> str:
    total_seconds = int(elapsed)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def extract_dump(local: MyPyClass, temp_file: str, dump_dir: str) -> int:
    threads = dump_extract_threads()
    local.add_log(f"Extracting dump with plzip regular-file input: file={temp_file} dir={dump_dir} threads={threads}", "info")
    extract_cmd = 'plzip -cd -n"$3" -- "$1" | tar -xf - -C "$2"'
    # Use bash for pipefail so decompressor and tar failures are both surfaced.
    result = subprocess.run([
        "bash", "-o", "pipefail", "-c", extract_cmd,
        "extract-dump", temp_file, dump_dir, str(threads)
    ])
    if result.returncode != 0:
        local.add_log(f"Dump extraction failed with exit code {result.returncode}", "error")
    return result.returncode
