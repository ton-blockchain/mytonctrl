from __future__ import annotations

import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psutil
import requests

from mypylib import MyPyClass
from mytoninstaller.context import InstallerContext
from mytoninstaller.utils import is_testnet
from mytonctrl.utils import is_container


@dataclass(frozen=True)
class DumpMetadata:
    archive_name: str
    sha256: str
    archive_size: int
    disk_size: int


DUMP_STATE_VERSION = 1
DUMP_PHASES = ("downloading", "verified", "extracting", "extracted")
DUMP_COMPLETE_MARKER = ".mytonctrl-dump.json"


def download_dump(local: MyPyClass, ctx: InstallerContext) -> bool:
    local.add_log("start download_dump function", "debug")
    if not is_container():
        return _download_host_dump(local, ctx)
    missing = [tool for tool in ("plzip", "aria2c", "tar", "sha256sum") if shutil.which(tool) is None]
    if missing:
        local.add_log(f"Missing dump tools in the controller image: {', '.join(missing)}", "error")
        return False
    dump_dir = os.path.abspath(ctx.paths.ton_db_dir)
    dump_cache_dir = os.path.abspath(get_dump_cache_dir(ctx.paths.ton_work_dir))
    os.makedirs(dump_dir, exist_ok=True)
    os.makedirs(dump_cache_dir, exist_ok=True)
    # An image restart may resume initialization, but two installers must never
    # write the same download or database concurrently.
    try:
        with open(os.path.join(dump_cache_dir, "dump-state.lock"), "a") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                local.add_log(f"Another installer is using dump cache {dump_cache_dir}", "error")
                return False
            return _download_dump(local, ctx, dump_dir, dump_cache_dir)
    except (OSError, ValueError, requests.RequestException) as exc:
        local.add_log(f"Dump setup failed; cached files are preserved: {exc}", "error")
        return False


def _download_host_dump(local: MyPyClass, ctx: InstallerContext) -> bool:
    # Preserve the native workflow: each call fetches a fresh dump and cleans its temporary files.
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


def _download_dump(local: MyPyClass, ctx: InstallerContext, dump_dir: str, dump_cache_dir: str) -> bool:
    base_url = "https://dump.ton.org/dumps"
    dump_name = "latest_testnet" if is_testnet(ctx.paths.global_config_path) else "latest"
    try:
        state = read_dump_state(dump_cache_dir)
        if state is None:
            # Older images did not pin metadata. Adopt their archive by its
            # exact name, never by today's latest dump, and never delete it.
            archives = sorted(
                name for name in os.listdir(dump_cache_dir)
                if name.endswith(".tar.lz") and os.path.isfile(os.path.join(dump_cache_dir, name))
            )
            if len(archives) > 1:
                raise ValueError("multiple cached dump archives; select the intended archive before retrying")
            metadata = get_archive_metadata(base_url, archives[0]) if archives else get_dump_metadata(base_url, dump_name)
            state = {
                "version": DUMP_STATE_VERSION,
                "dump_name": dump_name,
                "archive_url": f"{base_url}/{metadata.archive_name}",
                "archive_name": metadata.archive_name,
                "sha256": metadata.sha256,
                "archive_size": metadata.archive_size,
                "disk_size": metadata.disk_size,
                "dump_dir": dump_dir,
                "phase": "downloading",
            }
            validate_dump_state(state, dump_name, dump_dir, base_url)
            write_dump_state(dump_cache_dir, state)
        else:
            validate_dump_state(state, dump_name, dump_dir, base_url)
    except Exception as exc:
        local.add_log(f"Failed to load pinned dump metadata; cached files are preserved: {exc}", "error")
        return False

    metadata = DumpMetadata(state["archive_name"], state["sha256"], state["archive_size"], state["disk_size"])
    archive_name = metadata.archive_name
    temp_file = os.path.join(dump_cache_dir, archive_name)
    if dump_extraction_complete(dump_dir, state):
        state["phase"] = "extracted"
        write_dump_state(dump_cache_dir, state)
        local.add_log(f"Pinned dump {archive_name} is already extracted; keeping the existing database", "info")
        return True
    if state["phase"] == "extracted":
        # If the database volume was removed separately, a stale cache marker
        # cannot stand in for a completed extraction in the new database.
        state["phase"] = "verified"
        write_dump_state(dump_cache_dir, state)

    print("dumpName:", archive_name)
    print("dumpSize:", metadata.archive_size)
    print("dumpDiskSize:", metadata.disk_size)
    print("dumpCacheDir:", dump_cache_dir)
    if not check_dump_space(local, dump_dir, dump_cache_dir, metadata):
        return False
    verified = False
    if os.path.exists(temp_file):
        fingerprint = dump_file_fingerprint(temp_file)
        if fingerprint["size"] > metadata.archive_size:
            local.add_log(f"Cached dump is larger than its pinned size; preserving {temp_file}", "error")
            return False
        if fingerprint["size"] == metadata.archive_size:
            if state.get("verified_file") == fingerprint:
                verified = True
                local.add_log(f"Reusing previously verified dump archive: {temp_file}", "info")
            else:
                verified = verify_dump_checksum(local, dump_cache_dir, archive_name, metadata.sha256)
                if not verified and (state["phase"] != "downloading" or not os.path.isfile(temp_file + ".aria2")):
                    local.add_log(f"Cached dump checksum failed; preserving {temp_file} for inspection", "error")
                    return False

    if not verified:
        state["phase"] = "downloading"
        state.pop("verified_file", None)
        write_dump_state(dump_cache_dir, state)
        cmd = [
            "aria2c", "-x", "8", "-s", "8",
            "--enable-http-keep-alive=false", "--retry-wait=5", "--max-tries=20",
            "--connect-timeout=60", "--timeout=120", "--auto-file-renaming=false",
            "--allow-overwrite=true", "--check-integrity=true",
            f"--checksum=sha-256={metadata.sha256}", "-c", state["archive_url"],
            "-d", dump_cache_dir, "-o", archive_name,
        ]
        download_started_at = time.monotonic()
        download_result = subprocess.run(cmd).returncode
        download_elapsed = format_elapsed_time(time.monotonic() - download_started_at)
        if download_result != 0 or not os.path.isfile(temp_file):
            local.add_log(f"Dump download failed after {download_elapsed}; download will resume from {temp_file}", "error")
            return False
        if os.path.getsize(temp_file) != metadata.archive_size:
            local.add_log(f"Dump download size mismatch after {download_elapsed}; preserving {temp_file}", "error")
            return False
        checksum_started_at = time.monotonic()
        if not verify_dump_checksum(local, dump_cache_dir, archive_name, metadata.sha256):
            local.add_log(f"Dump checksum verification failed; preserving {temp_file}", "error")
            return False
        checksum_elapsed = format_elapsed_time(time.monotonic() - checksum_started_at)
        local.add_log(f"Dump checksum verified in {checksum_elapsed}: {temp_file}", "info")
    state["verified_file"] = dump_file_fingerprint(temp_file)
    state["phase"] = "verified"
    write_dump_state(dump_cache_dir, state)

    if dump_bool_env("DUMP_VALIDATE_BEFORE_EXTRACT", False):
        validation_started_at = time.monotonic()
        validation_result = validate_dump_archive(local, temp_file)
        validation_elapsed = format_elapsed_time(time.monotonic() - validation_started_at)
        if validation_result != 0:
            local.add_log(f"Dump lzip validation failed after {validation_elapsed}; preserving {temp_file}", "error")
            return False
        local.add_log(f"Dump lzip validation succeeded in {validation_elapsed}: {temp_file}", "info")

    state["phase"] = "extracting"
    write_dump_state(dump_cache_dir, state)
    msg = f"Extracting pinned dump {temp_file} to {dump_dir}"
    print(msg, flush=True)
    local.add_log(msg, "info")
    extraction_started_at = time.monotonic()
    extraction_result = extract_dump(local, temp_file, dump_dir)
    extraction_elapsed = format_elapsed_time(time.monotonic() - extraction_started_at)
    if extraction_result != 0:
        local.add_log(f"Dump extraction failed after {extraction_elapsed}; archive and database are preserved for retry", "error")
        return False
    # Write the database marker first. A crash between these two atomic writes
    # then recovers as completed instead of overwriting an initialized database.
    write_dump_json(os.path.join(dump_dir, DUMP_COMPLETE_MARKER), dump_identity(state))
    state["phase"] = "extracted"
    write_dump_state(dump_cache_dir, state)
    msg = f"Dump extracted to {dump_dir} in {extraction_elapsed}"
    print(msg, flush=True)
    local.add_log(msg, "info")
    return True


def get_dump_state_path(dump_cache_dir: str) -> str:
    return os.path.join(dump_cache_dir, "dump-state.json")


def read_dump_state(dump_cache_dir: str) -> Optional[Dict[str, Any]]:
    try:
        with open(get_dump_state_path(dump_cache_dir)) as source:
            state = json.load(source)
    except FileNotFoundError:
        return None
    if not isinstance(state, dict):
        raise ValueError("dump-state.json must contain an object")
    return state


def write_dump_state(dump_cache_dir: str, state: Dict[str, Any]) -> None:
    write_dump_json(get_dump_state_path(dump_cache_dir), state)


def write_dump_json(path: str, data: Dict[str, Any]) -> None:
    directory = os.path.dirname(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=directory, prefix=".dump-state-", delete=False) as target:
            temporary = target.name
            json.dump(data, target, sort_keys=True)
            target.write("\n")
            os.fchmod(target.fileno(), 0o644)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            os.unlink(temporary)


def validate_dump_state(state: Dict[str, Any], dump_name: str, dump_dir: str, base_url: str) -> None:
    if type(state.get("version")) is not int or state.get("version") != DUMP_STATE_VERSION or state.get("phase") not in DUMP_PHASES:
        raise ValueError("invalid dump state version or phase")
    if state.get("dump_name") not in ("latest", "latest_testnet"):
        raise ValueError("invalid dump network selector")
    if state.get("dump_name") != dump_name or state.get("dump_dir") != dump_dir:
        raise ValueError("cached dump belongs to a different network or database directory")
    validate_dump_metadata(DumpMetadata(
        state.get("archive_name", ""), state.get("sha256", ""), state.get("archive_size", 0), state.get("disk_size", 0)
    ))
    if state.get("archive_url") != f"{base_url}/{state['archive_name']}":
        raise ValueError("cached dump URL does not match its archive")


def dump_file_fingerprint(path: str) -> Dict[str, int]:
    info = os.stat(path, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"dump archive must be a regular file: {path}")
    return {"size": info.st_size, "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns}


def dump_identity(state: Dict[str, Any]) -> Dict[str, Any]:
    return {name: state[name] for name in ("version", "dump_name", "archive_name", "sha256", "dump_dir")}


def dump_extraction_complete(dump_dir: str, state: Dict[str, Any]) -> bool:
    try:
        with open(os.path.join(dump_dir, DUMP_COMPLETE_MARKER)) as source:
            return json.load(source) == dump_identity(state)
    except (OSError, ValueError):
        return False


def cleanup_completed_dump(dump_cache_dir: str, dump_dir: str) -> bool:
    """Reclaim only the pinned archive after the caller commits initialization."""
    state = read_dump_state(dump_cache_dir)
    if state is None:
        return False
    with open(os.path.join(dump_cache_dir, "dump-state.lock"), "a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        # Re-read under the same lock used by download/extraction.
        state = read_dump_state(dump_cache_dir)
        if state is None:
            return False
        validate_dump_state(state, state.get("dump_name", ""), os.path.abspath(dump_dir), "https://dump.ton.org/dumps")
        if state["phase"] != "extracted" or not dump_extraction_complete(dump_dir, state):
            return False
        removed = False
        for suffix in ("", ".aria2"):
            path = os.path.join(dump_cache_dir, state["archive_name"] + suffix)
            if os.path.lexists(path):
                os.unlink(path)
                removed = True
        if removed:
            print(f"Reclaimed completed dump archive: {state['archive_name']}", flush=True)
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


def allocated_dump_bytes(path: str) -> int:
    try:
        info = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return 0
    if not stat.S_ISREG(info.st_mode):
        return 0
    return info.st_blocks * 512


def allocated_database_bytes(dump_dir: str, dump_cache_dir: Optional[str] = None) -> int:
    allocated = 0
    seen = set()
    cache = os.path.abspath(dump_cache_dir) if dump_cache_dir is not None else None
    for directory, subdirectories, files in os.walk(dump_dir, followlinks=False):
        # DUMP_CACHE_DIR can be a child of the database directory. Its archive
        # allocation is already credited separately, never as extracted data.
        subdirectories[:] = [name for name in subdirectories if os.path.abspath(os.path.join(directory, name)) != cache]
        for name in files:
            if os.path.abspath(directory) == cache and (
                name.endswith((".tar.lz", ".tar.lz.aria2")) or name in ("dump-state.json", "dump-state.lock")
            ):
                continue
            info = os.stat(os.path.join(directory, name), follow_symlinks=False)
            inode = (info.st_dev, info.st_ino)
            if stat.S_ISREG(info.st_mode) and inode not in seen:
                seen.add(inode)
                allocated += info.st_blocks * 512
    return allocated


def check_dump_space(local: MyPyClass, dump_dir: str, dump_cache_dir: str, dump_metadata: DumpMetadata) -> bool:
    archive_size = dump_metadata.archive_size
    disk_size = dump_metadata.disk_size
    space_label = ""
    if is_container():
        # Container restarts can reuse already allocated archive and partial
        # database blocks. A native refresh retains its original full-space check.
        archive_path = os.path.join(dump_cache_dir, dump_metadata.archive_name)
        archive_size = max(0, archive_size - allocated_dump_bytes(archive_path))
        disk_size = max(0, disk_size - allocated_database_bytes(dump_dir, dump_cache_dir))
        space_label = " more bytes"
    dump_usage = psutil.disk_usage(dump_dir)
    cache_usage = psutil.disk_usage(dump_cache_dir)
    if os.stat(dump_dir).st_dev == os.stat(dump_cache_dir).st_dev:
        need_space = archive_size + disk_size
        if need_space > dump_usage.free:
            local.add_log(f"Not enough disk space in {dump_dir}: need {need_space}{space_label}, free {dump_usage.free}", "error")
            return False
        return True
    if archive_size > cache_usage.free:
        local.add_log(f"Not enough disk space in {dump_cache_dir}: need {archive_size}{space_label}, free {cache_usage.free}", "error")
        return False
    if disk_size > dump_usage.free:
        local.add_log(f"Not enough disk space in {dump_dir}: need {disk_size}{space_label}, free {dump_usage.free}", "error")
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
    if is_container():
        return get_archive_metadata(base_url, archive_name)

    # Keep native metadata handling compatible with the original fresh-dump workflow.
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


def get_archive_metadata(base_url: str, archive_name: str) -> DumpMetadata:
    if not isinstance(archive_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.tar\.lz", archive_name):
        raise ValueError("invalid dump archive filename")
    metadata_name = archive_name[:-3]
    sha_text = dump_fetch_text(f"{base_url}/{metadata_name}.sha256sum.txt", timeout=10)
    sha_parts = sha_text.split()
    if not sha_parts:
        raise RuntimeError(f"empty dump sha256 for {metadata_name}")
    sha256 = sha_parts[0].lower()
    if len(sha_parts) > 1 and os.path.basename(sha_parts[1].lstrip("*")) != archive_name:
        raise RuntimeError(f"dump sha256 file does not match archive {archive_name}: {sha_parts[1]}")
    metadata = DumpMetadata(
        archive_name=archive_name,
        sha256=sha256,
        archive_size=int(dump_fetch_text(f"{base_url}/{metadata_name}.size.archive.txt", timeout=10)),
        disk_size=int(dump_fetch_text(f"{base_url}/{metadata_name}.size.disk.txt", timeout=10)),
    )
    validate_dump_metadata(metadata)
    return metadata


def validate_dump_metadata(metadata: DumpMetadata) -> None:
    if not isinstance(metadata.archive_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.tar\.lz", metadata.archive_name):
        raise ValueError("invalid dump archive filename")
    if not isinstance(metadata.sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", metadata.sha256):
        raise ValueError("invalid dump sha256")
    if any(type(size) is not int or size <= 0 for size in (metadata.archive_size, metadata.disk_size)):
        raise ValueError("dump archive and database sizes must be positive integers")


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
    if is_container():
        # Container retry extraction must preserve this node's identity.
        # Native extraction keeps the original archive contents unchanged.
        protected = ("config.json", "keyring", "keys", "nodekeys", DUMP_COMPLETE_MARKER)
        exclusions = " ".join(f"--exclude={name} --exclude=*/{name}" for name in protected)
        extract_cmd += " " + exclusions
    # Use bash for pipefail so decompressor and tar failures are both surfaced.
    result = subprocess.run([
        "bash", "-o", "pipefail", "-c", extract_cmd,
        "extract-dump", temp_file, dump_dir, str(threads)
    ])
    if result.returncode != 0:
        local.add_log(f"Dump extraction failed with exit code {result.returncode}", "error")
    return result.returncode
