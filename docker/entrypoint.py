"""Bootstrap MyTonCtrl from externally supplied TON artifacts, then supervise it."""
import fcntl
from ipaddress import IPv4Address
import json
import os
import platform
import pwd
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

from mytonctrl_docker_args import installation_environment


REQUIRED_BINARIES = ("validator-engine", "validator-engine-console", "lite-client",
                     "generate-random-id", "fift", "func")
BINARY_LAYOUT = {
    "validator-engine": "validator-engine/validator-engine",
    "validator-engine-console": "validator-engine-console/validator-engine-console",
    "lite-client": "lite-client/lite-client",
    "generate-random-id": "utils/generate-random-id",
    "fift": "crypto/fift", "func": "crypto/func", "create-state": "crypto/create-state",
    "dht-server": "dht-server/dht-server",
    "libtonlibjson.so": "tonlib/libtonlibjson.so",
    "libemulator.so": "emulator/libemulator.so",
    "blockchain-explorer": "blockchain-explorer/blockchain-explorer",
    "tonutils-storage": "tonutils-storage/tonutils-storage",
}
INITIALIZATION_SETTINGS = (
    "MODE", "NETWORK", "MTC_USER", "TELEMETRY", "IGNORE_MINIMAL_REQS", "DUMP", "ARCHIVE",
    "ONLY_MTC", "ONLY_NODE", "BACKUP", "BIN_DIR", "SRC_DIR", "TON_WORK_DIR", "PUBLIC_IP",
    "GLOBAL_CONFIG_URL", "GLOBAL_CONFIG_FILE", "CONFIG_URL", "VALIDATOR_PORT",
    "VALIDATOR_CONSOLE_PORT", "LITESERVER_PORT", "QUIC_PORT", "ARCHIVE_TTL", "STATE_TTL",
    "ADD_SHARD", "ARCHIVE_BLOCKS", "DUMP_CACHE_DIR", "DUMP_EXTRACT_THREADS",
    "DUMP_VALIDATE_BEFORE_EXTRACT", "CUSTOM_PARAMETERS", "VERBOSITY",
)


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w") as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def resume_settings(env, pending, identity):
    """Resume the same installation; older images created an empty marker."""
    if not pending.exists():
        return False
    text = pending.read_text().strip()
    if text:
        try:
            value = json.loads(text)
            if value["version"] != 1 or value["identity"] != identity:
                raise ValueError("Persisted initialization paths/user differ from .env")
            settings = value["installer_environment"]
            if not isinstance(settings, dict) or any(
                    name not in INITIALIZATION_SETTINGS or not isinstance(setting, str)
                    for name, setting in settings.items()):
                raise ValueError("Invalid persisted initialization settings")
            for name in INITIALIZATION_SETTINGS:
                env.pop(name, None)
            env.update(settings)
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid initialization marker {pending}; data and dump cache were preserved") from error
    print("Resuming interrupted initialization; existing node data and dump cache will be reused.", flush=True)
    return True


def pin_installer_ports(env, work):
    """Keep randomly selected ports stable across interrupted installations."""
    node = work / "db/config.json"
    config = json.loads(node.read_text()) if node.is_file() else {}
    sections = {"VALIDATOR_PORT": "addrs", "VALIDATOR_CONSOLE_PORT": "control",
                "LITESERVER_PORT": "liteservers"}
    used = {int(env[name]) for name in sections if env.get(name)}
    for name, section in sections.items():
        if not env.get(name):
            entries = config.get(section) or []
            value = entries[0].get("port") if entries else None
            if value is None:
                value = random.SystemRandom().randint(2000, 64000)
                while value in used:
                    value = random.SystemRandom().randint(2000, 64000)
            env[name] = str(value)
        port = int(env[name])
        if not 1 <= port <= 65535:
            raise ValueError(f"{name} must be between 1 and 65535")
        used.add(port)


def boolean(env, name, default=False):
    value = env.get(name, str(default)).lower()
    if value not in ("true", "false", "1", "0", "yes", "no"):
        raise ValueError(f"{name} must be true or false")
    return value in ("true", "1", "yes")


def directory(env, name, default):
    path = Path(env.get(name) or default)
    if not path.is_absolute() or any(c.isspace() for c in str(path)):
        raise ValueError(f"{name} must be an absolute path without whitespace")
    return path


def mounted(path):
    # Individual native directories or a parent artifact volume are both valid.
    path = path.resolve()
    return any(os.path.ismount(parent) for parent in (path, *path.parents) if parent != Path("/"))


def artifact_sources(env):
    root = directory(env, "TON_ARTIFACTS_DIR", "/ton-artifacts")
    if (root / "current").exists():
        release = (root / "current").resolve(strict=True)
        if root.resolve() not in release.parents:
            raise ValueError("TON current release must stay inside TON_ARTIFACTS_DIR")
        sources = (release / "bin", release / "fift", release / "smartcont")
    else:
        sources = (directory(env, "TON_BINARIES_DIR", "/ton-source/bin"),
                   directory(env, "FIFT_LIB_DIR", "/ton-source/fift"),
                   directory(env, "TON_SMARTCONT_DIR", "/ton-source/smartcont"))
    for source in sources:
        if not source.is_dir() or not mounted(source):
            raise ValueError(f"Missing TON artifact mount: {source}. Mount official TON binaries, "
                             "Fift libraries and smart contracts read-only; see docker/README.md.")
    validate_artifacts(*sources)
    return sources


def validate_artifacts(binaries, fift, smartcont):
    for name in REQUIRED_BINARIES:
        path = binaries / name
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError(f"Missing executable TON binary: {path}")
    for path in (fift / "Fift.fif", fift / "TonUtil.fif", fift / "Asm.fif",
                 smartcont / "wallet-v3.fif", smartcont / "validator-elect-signed.fif"):
        if not path.is_file():
            raise ValueError(f"Missing TON runtime resource: {path}")


def snapshot_artifacts(sources, target=Path("/run/ton-active")):
    # Never execute through `current` or a volume that an exporter may overwrite.
    if target.exists():
        shutil.rmtree(target)
    for source, name in zip(sources, ("bin", "fift", "smartcont")):
        shutil.copytree(source, target / name)
    # Keep the reported image tied to these binaries, even after another export.
    if sources and all(source.parent == sources[0].parent for source in sources):
        metadata = sources[0].parent / "image-ref"
        if metadata.is_file():
            shutil.copyfile(metadata, target / "image-ref")
    validate_artifacts(target / "bin", target / "fift", target / "smartcont")
    for path in target.rglob("*"):
        path.chmod(path.stat().st_mode & ~0o222)
    target.chmod(0o555)
    return target


def check_binaries(active):
    for name in REQUIRED_BINARIES:
        binary = active / "bin" / name
        with binary.open("rb") as stream:
            header = stream.read(20)
        if header[:4] != b"\x7fELF":
            raise ValueError(f"{binary} is not a Linux ELF binary")
        machine = {"x86_64": 62, "aarch64": 183}.get(platform.machine())
        byteorder = "little" if header[5] == 1 else "big"
        if machine and int.from_bytes(header[18:20], byteorder) != machine:
            raise ValueError(f"{binary} does not match controller architecture {platform.machine()}")
        result = subprocess.run(["ldd", str(binary)], capture_output=True, text=True)
        if "not found" in result.stdout + result.stderr:
            raise ValueError(f"Missing runtime libraries for {binary}: {result.stdout}{result.stderr}")
    result = subprocess.run([str(active / "bin/validator-engine"), "--version"],
                            capture_output=True, text=True, check=True)
    print(result.stdout.strip(), flush=True)


def installer_args(env, validate_backup=True):
    mode = env.get("MODE", "validator")
    modes = ("validator", "liteserver", "collator", "single-nominator", "nominator-pool",
             "nominator-pool-v2", "liquid-staking", "alert-bot", "prometheus", "none")
    if mode not in modes:
        raise ValueError(f"Invalid MODE={mode}")
    only_mtc = boolean(env, "ONLY_MTC")
    only_node = boolean(env, "ONLY_NODE")
    backup = env.get("BACKUP") or "none"
    if only_mtc and backup == "none":
        raise ValueError("ONLY_MTC=true requires BACKUP to a mounted backup file")
    if only_mtc and only_node:
        raise ValueError("ONLY_MTC and ONLY_NODE cannot both be true")
    if validate_backup and backup != "none" and not Path(backup).is_file():
        raise ValueError(f"Backup file is missing: {backup}")
    if boolean(env, "ARCHIVE"):
        if mode != "liteserver":
            raise ValueError("ARCHIVE=true requires MODE=liteserver")
        env.update(ARCHIVE_BLOCKS="1", ARCHIVE_TTL="-1")
        env.pop("STATE_TTL", None)
    args = ["-u", env.get("MTC_USER", "root"), "-t", str(boolean(env, "TELEMETRY", True)).lower(),
            "--dump", str(boolean(env, "DUMP")).lower(), "-m", mode,
            "--only-mtc", str(only_mtc).lower(), "--only-node", str(only_node).lower(),
            "--backup", backup]
    for name, flag, default in (("BIN_DIR", "--bin-dir", "/usr/bin"),
                                 ("SRC_DIR", "--src-dir", "/usr/src"),
                                 ("TON_WORK_DIR", "--ton-work-dir", "/var/ton-work")):
        args.extend((flag, str(directory(env, name, default))))
    return args


def check_backup(path):
    """Check original MyTonCtrl backup metadata before starting initialization."""
    with tarfile.open(path, "r:gz") as archive:
        files = {}
        for member in archive.getmembers():
            normalized = Path(member.name)
            if normalized.is_absolute() or ".." in normalized.parts or member.issym() or member.islnk():
                raise ValueError(f"Invalid backup member: {member.name}")
            files[str(normalized)] = member
        for name in ("mytoncore/mytoncore.db", "db/config.json"):
            member = files.get(name)
            if name == "db/config.json" and member is None:
                member = files.get("config.json")  # Original backup layout.
            if member is None or not member.isfile():
                raise ValueError(f"Backup is missing {name}")
            value = json.load(archive.extractfile(member))
            required = ("fift", "liteClient", "validatorConsole") if name.startswith("mytoncore") else ("addrs", "control")
            if not isinstance(value, dict) or any(key not in value for key in required):
                raise ValueError(f"Invalid backup configuration: {name}")
        if not any(name.startswith("keys/") for name in files):
            raise ValueError("Backup is missing node keys")


def link(path, target):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        raise ValueError(f"Refusing to replace existing path {path}; use a clean controller container")
    path.symlink_to(target)


def prepare_layout(env, active, state):
    binaries = directory(env, "BIN_DIR", "/usr/bin") / "ton"
    resources = directory(env, "SRC_DIR", "/usr/src") / "ton/crypto"
    binaries.mkdir(parents=True, exist_ok=True)
    for binary in (active / "bin").iterdir():
        if binary.is_file():
            link(binaries / BINARY_LAYOUT.get(binary.name, binary.name), binary)
    link(resources / "fift/lib", active / "fift")
    link(resources / "smartcont", active / "smartcont")
    for name in ("global.config.json", "local.config.json"):
        link(binaries / name, state / name)
    os.environ["FIFTPATH"] = f"{resources}/fift/lib:{resources}/smartcont"
    for name in ("mytoncore", "mytonctrl"):
        data = state / name
        data.mkdir(exist_ok=True)
        link(Path("/usr/local/bin") / name, data)
    user = env.get("MTC_USER", "root")
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", user):
        raise ValueError("MTC_USER must be a Linux username")
    try:
        account = pwd.getpwnam(user)
    except KeyError:
        subprocess.run(["useradd", "--create-home", "--shell", "/bin/bash", user], check=True)
        account = pwd.getpwnam(user)
    if account.pw_uid:
        for name in ("mytoncore", "mytonctrl"):
            link(Path(account.pw_dir) / ".local/share" / name, state / name)
            shutil.chown(state / name, user=user)
            for child in (state / name).rglob("*"):
                if not child.is_symlink():
                    shutil.chown(child, user=user)
        # Runtime console and privileged service commands use sudo without prompts.
        Path("/etc/sudoers.d/mytonctrl").write_text(
            f"Defaults:{user} secure_path=/opt/mytonctrl/bin:/opt/mytonctrl/venv/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
            f'Defaults:{user} env_keep += "MYTONCTRL_CONTAINER MYTONCTRL_SERVICE_ENABLED_DIR '
            'MYTONCTRL_SERVICE_UNIT_DIR MYTONCTRL_SUPERVISOR_CONFIG_DIR MYTONCTRL_SUPERVISOR_SOCKET FIFTPATH"\n'
            f"{user} ALL=(root) NOPASSWD: ALL\n")
        Path("/etc/sudoers.d/mytonctrl").chmod(0o440)
    work = state.parent
    # A previous image or root-run first configuration may own node logs/state.
    # Repair node ownership without changing the controller user's databases.
    for node_path in (work / "db", work / "keys", *work.glob("log*")):
        if node_path.exists() and not node_path.is_symlink():
            shutil.chown(node_path, user="validator", group="validator")
    services = state / "services"
    services.mkdir(exist_ok=True)
    units = Path("/etc/systemd/system")
    if units.is_dir() and not units.is_symlink():
        # Image contains only distro unit files; use the controller's persisted units.
        shutil.rmtree(units)
    link(units, services)


def global_config(env, state):
    path = state / "global.config.json"
    if path.is_file():
        return
    network = env.get("NETWORK", "mainnet")
    if network not in ("mainnet", "testnet", "custom"):
        raise ValueError("NETWORK must be mainnet, testnet or custom")
    source = env.get("GLOBAL_CONFIG_FILE")
    if source:
        payload = Path(source).read_bytes()
    else:
        url = env.get("GLOBAL_CONFIG_URL") or env.get("CONFIG_URL")
        if not url:
            if network == "custom":
                raise ValueError("NETWORK=custom requires GLOBAL_CONFIG_FILE or GLOBAL_CONFIG_URL")
            prefix = "testnet-" if network == "testnet" else ""
            url = f"https://ton-blockchain.github.io/{prefix}global.config.json"
        with urlopen(url, timeout=30) as response:
            payload = response.read()
    config = json.loads(payload)
    if "validator" not in config or "dht" not in config:
        raise ValueError("Invalid TON global configuration (missing validator/dht)")
    temp = path.with_suffix(".tmp")
    temp.write_bytes(payload)
    temp.replace(path)


def check_requirements(env):
    if boolean(env, "IGNORE_MINIMAL_REQS", boolean(env, "IGNORE_REQS")):
        return
    cpus = len(os.sched_getaffinity(0))
    total_kb = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                        if line.startswith("MemTotal:")))
    memory_max = Path("/sys/fs/cgroup/memory.max")
    if memory_max.is_file() and memory_max.read_text().strip().isdigit():
        total_kb = min(total_kb, int(memory_max.read_text()) // 1024)
    cpu_max = Path("/sys/fs/cgroup/cpu.max")
    if cpu_max.is_file():
        quota, period = cpu_max.read_text().split()
        if quota != "max":
            cpus = min(cpus, int(quota) // int(period))
    required_cpu, required_memory = (8, 16000000) if env.get("NETWORK") == "testnet" else (16, 64000000)
    if cpus < required_cpu or total_kb < required_memory:
        raise ValueError(f"Insufficient resources ({cpus} CPUs, {total_kb} KiB). "
                         f"Requires {required_cpu} CPUs and {required_memory} KiB; "
                         "IGNORE_MINIMAL_REQS=true bypasses this installer check.")


def detect_public_ip():
    from mytoninstaller.config import get_own_ip
    return get_own_ip()


def resolve_public_ip(env):
    """Resolve the advertised IPv4 before any node initialization can be left partial."""
    if boolean(env, "ONLY_MTC"):
        return
    value = (env.get("PUBLIC_IP") or "").strip()
    if not value:
        try:
            value = detect_public_ip().strip()
        except Exception as error:
            raise ValueError("Cannot detect the node's public IPv4 address. Set PUBLIC_IP in .env "
                             "to the node's advertised IPv4 address and retry.") from error
    try:
        env["PUBLIC_IP"] = str(IPv4Address(value))
    except ValueError as error:
        raise ValueError("PUBLIC_IP must be an IPv4 address. Set PUBLIC_IP in .env to the node's "
                         "advertised IPv4 address and retry.") from error


def custom_validator_args(env):
    custom = shlex.split(env.get("CUSTOM_PARAMETERS", ""))
    # The controller owns binary selection, state paths and foreground supervision.
    reserved = ("--daemonize", "--db", "--global-config", "--logname", "--ip", "-D", "-C", "-l")
    if any(arg.split("=", 1)[0] in reserved for arg in custom):
        raise ValueError("CUSTOM_PARAMETERS cannot change daemonization or controller-managed paths")
    if env.get("VERBOSITY"):
        custom.extend(("--verbosity", str(int(env["VERBOSITY"]))))
    return custom


def customize_validator(env, state):
    unit = state / "services/validator.service"
    if not unit.exists():
        return False
    custom = custom_validator_args(env)
    text = unit.read_text()
    # Only add environment defaults on first install; later changes use set_node_argument.
    if custom:
        text = re.sub(r"(?m)^(ExecStart\s*=.*)$", lambda m: m[1] + " " + shlex.join(custom), text)
        unit.write_text(text)
    return bool(custom)


def main():
    argv = sys.argv[1:]
    command = argv.pop(0) if argv and not argv[0].startswith("-") else "run"
    if command not in ("run", "check", "console"):
        raise ValueError("Usage: image [run | check | console <mytonctrl arguments>]")
    env = installation_environment(os.environ, argv if command != "console" else ())
    for name in ("AUTHOR", "REPO", "BRANCH", "NODE_REPO", "NODE_VERSION", "MYTONCTRL_VERSION"):
        if env.get(name):
            raise ValueError(f"{name} selects sources on a host install. Select a controller or TON image tag instead.")
    args = installer_args(env, validate_backup=False)
    if boolean(env, "MYTONCTRL_PRINT_ENV"):
        settings = {key: env[key] for key in (
            "MODE", "NETWORK", "MTC_USER", "TELEMETRY", "IGNORE_MINIMAL_REQS", "DUMP", "ARCHIVE",
            "ONLY_MTC", "ONLY_NODE", "BACKUP", "BIN_DIR", "SRC_DIR", "TON_WORK_DIR", "PUBLIC_IP",
            "GLOBAL_CONFIG_URL", "GLOBAL_CONFIG_FILE", "VALIDATOR_PORT", "VALIDATOR_CONSOLE_PORT",
            "LITESERVER_PORT", "QUIC_PORT", "ARCHIVE_TTL", "STATE_TTL", "ADD_SHARD", "ARCHIVE_BLOCKS",
        ) if key in env}
        print(json.dumps({"settings": settings, "installer_args": args}, indent=2))
        return
    sources = artifact_sources(env)
    active = snapshot_artifacts(sources)
    check_binaries(active)
    if command == "check":
        print("TON artifact mounts and runtime dependencies are ready.", flush=True)
        return
    if os.getuid() != 0:
        raise ValueError("The container entrypoint must run as root; set MTC_USER for controller service ownership")
    custom_validator_args(env)
    work = directory(env, "TON_WORK_DIR", "/var/ton-work")
    default_work = Path("/var/ton-work")
    if work != default_work and mounted(default_work) and not mounted(work):
        # Compose can keep a fixed data mount while -W selects its in-container alias.
        link(work, default_work)
    work.mkdir(parents=True, exist_ok=True)
    state = work / "controller"
    state.mkdir(exist_ok=True)
    lock = (state / ".container.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError("Another MyTonCtrl container is already using this TON_WORK_DIR") from None
    initialized = state / "initialized.json"
    identity = {name: env.get(name, default) for name, default in
                (("MTC_USER", "root"), ("BIN_DIR", "/usr/bin"), ("SRC_DIR", "/usr/src"),
                 ("TON_WORK_DIR", "/var/ton-work"))}
    if initialized.exists() and json.loads(initialized.read_text()) != identity:
        raise ValueError("Persisted controller paths/user differ from .env; retain the original installation settings")
    pending = state / ".initializing"
    if initialized.exists():
        # A stop between committing completion and removing the pending marker
        # must not rerun installation or block an otherwise complete node.
        pending.unlink(missing_ok=True)
    else:
        resume_settings(env, pending, identity)
        args = installer_args(env)
        custom_validator_args(env)
    if not initialized.exists():
        check_requirements(env)
        backup = env.get("BACKUP") or "none"
        if backup != "none":
            check_backup(backup)
        if env.get("ARCHIVE_BLOCKS") and not (active / "bin/tonutils-storage").is_file():
            raise ValueError("ARCHIVE/ARCHIVE_BLOCKS requires a separately mounted prebuilt tonutils-storage "
                             "binary in TON binaries; official storage-daemon uses a different API.")
        resolve_public_ip(env)
        pin_installer_ports(env, work)
    # The native installer reads the process environment. Remove settings that
    # were absent from the saved installation before applying restored values.
    for name in INITIALIZATION_SETTINGS:
        if name not in env:
            os.environ.pop(name, None)
    os.environ.update(env)
    prepare_layout(env, active, state)
    Path("/run/mytonctrl-options.json").write_text(json.dumps({
        "MTC_USER": env["MTC_USER"], "TON_WORK_DIR": env["TON_WORK_DIR"],
        "MYTONCTRL_SKIP_STARTUP_CHECKS": env.get("MYTONCTRL_SKIP_STARTUP_CHECKS", "false"),
    }))
    os.environ["MYTONCTRL_SERVICE_ENABLED_DIR"] = str(state / "enabled")
    global_config(env, state)
    Path("/run/mytonctrl-supervisor").mkdir(exist_ok=True)
    children = []
    stopping = False

    def stop(signum, _frame):
        nonlocal stopping
        stopping = True
        for child in reversed(children):
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    Path("/run/supervisor.sock").unlink(missing_ok=True)
    supervisor = subprocess.Popen(["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/mytonctrl.conf"],
                                  start_new_session=True)
    children.append(supervisor)
    try:
        for _ in range(100):
            if supervisor.poll() is not None or stopping:
                raise RuntimeError("Service supervisor exited during startup")
            if Path("/run/supervisor.sock").exists():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Service supervisor did not become ready")
        if not initialized.exists():
            write_json(pending, {"version": 1, "identity": identity,
                       "installer_environment": {name: env[name] for name in INITIALIZATION_SETTINGS if name in env}})
            installer = subprocess.Popen([sys.executable, "-m", "mytoninstaller", *args], start_new_session=True)
            children.append(installer)
            result = installer.wait()
            if stopping:
                return
            if result != 0:
                raise RuntimeError("MyTonCtrl initialization failed; node data and dump cache were preserved. "
                                   "The next start resumes installation; inspect controller/installer-progress.json for the cause.")
            core = json.loads((state / "mytoncore/mytoncore.db").read_text())
            if not boolean(env, "ONLY_MTC"):
                if not (work / "db/config.json").is_file() or not core.get("validatorConsole") or not core.get("liteClient", {}).get("liteServer"):
                    raise RuntimeError("MyTonCtrl initialization did not create complete node/client configuration")
            if customize_validator(env, state):
                subprocess.run(["systemctl", "restart", "validator"], check=True)
            write_json(initialized, identity)
            pending.unlink()
        from mytoninstaller.dump import cleanup_completed_dump, get_dump_cache_dir
        try:
            cleanup_completed_dump(get_dump_cache_dir(str(work)), str(work / "db"))
        except (OSError, ValueError) as error:
            print(f"Could not remove completed dump cache: {error}. Node data are ready.", file=sys.stderr, flush=True)
        subprocess.run(["systemctl", "initialize"], check=True)
        print("MyTonCtrl ready. Open the console with: docker exec -it <container> mytonctrl", flush=True)
        if command == "console":
            console = subprocess.Popen(["/opt/mytonctrl/bin/mytonctrl", *argv], start_new_session=True)
            children.append(console)
            result = console.wait()
            if result:
                raise RuntimeError(f"MyTonCtrl console exited with status {result}")
        else:
            supervisor.wait()
            if not stopping:
                raise RuntimeError("Service supervisor exited unexpectedly")
    finally:
        stop(signal.SIGTERM, None)
        deadline = time.monotonic() + 65
        for child in reversed(children):
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, tarfile.TarError) as error:
        print(f"MyTonCtrl startup failed: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
