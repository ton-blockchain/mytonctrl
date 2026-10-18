"""Run with python -m unittest discover -s tests/docker -p test_services.py.

The lifecycle tests use a private unprivileged supervisord instance. They are
skipped when Supervisor is unavailable; parsing and runner tests always run.
"""

import importlib.util
import io
import json
import os
from pathlib import Path
import pwd
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT / "docker/systemctl.py"
RUNNER = ROOT / "docker/run-service.py"
MODULE_SPEC = importlib.util.spec_from_file_location("docker_systemctl", SHIM)
systemctl = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(systemctl)


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def unit(self, service, body):
        path = self.directory / f"{service}.service"
        path.write_text("[Service]\n" + body)
        return path

    def test_validator_arguments_and_service_identity(self):
        unit = self.unit("validator", """Type = simple
ExecStart = /opt/ton/validator-engine --daemonize --db '/var/ton db' --logname /tmp/100%.log
ExecStartPre = /bin/sleep 2
ExecStartPre = -/bin/false
User = validator
Group = ton
WorkingDirectory = /var/ton-work
Environment = 'VALUE=a b' OTHER=literal
Restart = always
LimitNOFILE = infinity
""")
        parsed = systemctl.read_unit(unit)
        self.assertEqual(parsed["argv"], ["/opt/ton/validator-engine", "--db", "/var/ton db", "--logname", "/tmp/100%.log"])
        self.assertEqual(parsed["user"], "validator")
        self.assertEqual(parsed["group"], "ton")
        self.assertEqual(parsed["directory"], "/var/ton-work")
        self.assertEqual(parsed["environment"], {"VALUE": "a b", "OTHER": "literal"})
        self.assertEqual(parsed["nofile"], "infinity")
        self.assertEqual(parsed["pre"][1], {"argv": ["/bin/false"], "ignore_failure": True})

    def test_empty_directive_resets_pre_commands(self):
        unit = self.unit("example", "ExecStart=/bin/sleep 30\nExecStartPre=/bin/false\nExecStartPre=\nExecStartPre=/bin/true\n")
        self.assertEqual(systemctl.read_unit(unit)["pre"], [{"argv": ["/bin/true"], "ignore_failure": False}])

    def test_rejects_unsupported_units_and_service_paths(self):
        unit = self.unit("example", "Type=forking\nExecStart=/bin/true\n")
        with self.assertRaisesRegex(ValueError, "Unsupported service Type"):
            systemctl.read_unit(unit)
        for name in ("../validator", "x/y", "name;command", ""):
            with self.subTest(name=name), self.assertRaises(ValueError):
                systemctl.service_name(name)
        with self.assertRaises(ValueError):
            systemctl.parse_command("sleep 1")

    def test_runner_uses_literal_arguments_and_pre_commands(self):
        marker = self.directory / "pre-ran"
        program = self.directory / "capture.py"
        program.write_text("import json, os, sys\nprint(json.dumps([sys.argv[1:], os.getenv('EXAMPLE'), os.getcwd(), os.getenv('XDG_DATA_HOME')]))\n")
        spec = {
            "argv": [sys.executable, str(program), "$(touch unexpected)", "$HOME", "a;b"],
            "pre": [{"argv": [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"], "ignore_failure": False}],
            "directory": str(self.directory),
            "environment": {"EXAMPLE": "some value"},
            "user": str(os.getuid()),
            "group": str(os.getgid()),
        }
        spec_path = self.directory / "service.json"
        spec_path.write_text(json.dumps(spec))
        result = subprocess.run([sys.executable, str(RUNNER), str(spec_path)], text=True, capture_output=True, check=True,
                                env={**os.environ, "XDG_DATA_HOME": "/wrong/user/data"})
        self.assertTrue(marker.is_file())
        self.assertFalse((self.directory / "unexpected").exists())
        self.assertEqual(json.loads(result.stdout), [["$(touch unexpected)", "$HOME", "a;b"], "some value", str(self.directory),
                                                    pwd.getpwuid(os.getuid()).pw_dir + "/.local/share"])

    def test_runner_stops_after_failed_pre_command(self):
        spec_path = self.directory / "service.json"
        spec_path.write_text(json.dumps({"argv": ["/bin/echo", "unexpected"], "pre": [{"argv": ["/bin/false"], "ignore_failure": False}]}))
        result = subprocess.run([sys.executable, str(RUNNER), str(spec_path)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def test_runner_restores_unit_nofile_limit_before_start(self):
        spec_path = self.directory / "service.json"
        spec_path.write_text(json.dumps({
            "argv": [sys.executable, "-c", "import resource; print(resource.getrlimit(resource.RLIMIT_NOFILE)[0])"],
            "nofile": "infinity",
        }))
        hard = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
        code = (
            "import os, resource, sys; "
            "soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE); "
            "resource.setrlimit(resource.RLIMIT_NOFILE, (min(1024, soft), hard)); "
            "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])"
        )
        result = subprocess.run([sys.executable, "-c", code, str(RUNNER), str(spec_path)],
                                text=True, capture_output=True, check=True)
        self.assertEqual(int(result.stdout), hard)

    def test_program_keeps_children_in_one_shutdown_group(self):
        rendered = systemctl.render_program("validator", "/tmp/100%/service.json", {"restart": "always"}, RUNNER)
        self.assertIn("/tmp/100%%/service.json", rendered)
        self.assertIn("autostart=false", rendered)
        self.assertIn("startsecs=5", rendered)
        self.assertIn("stopasgroup=true", rendered)
        self.assertIn("killasgroup=true", rendered)
        self.assertIn("stdout_logfile_maxbytes=0", rendered)

    def test_monotonic_start_time_reads_process_not_supervisor_time(self):
        start = systemctl.process_start_monotonic(os.getpid())
        self.assertGreater(start, 0)
        self.assertLessEqual(start, int(time.clock_gettime(time.CLOCK_BOOTTIME) * 1_000_000))
        self.assertEqual(systemctl.process_start_monotonic(0), 0)

    def test_show_preserves_supervisor_state_and_exit_status(self):
        for state, exit_status in (("STARTING", 0), ("BACKOFF", 1), ("FATAL", 1), ("RUNNING", 0)):
            with self.subTest(state=state), patch.object(systemctl, "ServiceManager") as manager:
                manager.return_value.info.return_value = {"statename": state, "exitstatus": exit_status, "pid": 0}
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(systemctl.main(["show", "validator", "--property=SubState,ExecMainStatus", "--value"]), 0)
                self.assertEqual(output.getvalue().splitlines(), [state, str(exit_status)])


def supervisor_command():
    if importlib.util.find_spec("supervisor"):
        return [sys.executable, "-m", "supervisor.supervisord"]
    executable = shutil.which("supervisord")
    return [executable] if executable else None


@unittest.skipUnless(supervisor_command(), "Supervisor is not installed")
class SupervisorLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mtc-service-")
        self.directory = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.units = self.directory / "units"
        self.enabled = self.directory / "enabled"
        self.configs = self.directory / "programs"
        for directory in (self.units, self.enabled, self.configs):
            directory.mkdir()
        self.socket = self.directory / "supervisor.sock"
        self.environment = {
            **os.environ,
            "MYTONCTRL_SERVICE_UNIT_DIR": str(self.units),
            "MYTONCTRL_SERVICE_ENABLED_DIR": str(self.enabled),
            "MYTONCTRL_SUPERVISOR_CONFIG_DIR": str(self.configs),
            "MYTONCTRL_SUPERVISOR_SOCKET": str(self.socket),
            "MYTONCTRL_SERVICE_RUNNER": str(RUNNER),
        }
        self.supervisor_config = self.directory / "supervisord.conf"
        self.supervisor_config.write_text(f"""[unix_http_server]
file={self.socket}
chmod=0700
[supervisord]
nodaemon=true
logfile={self.directory}/supervisor.log
pidfile={self.directory}/supervisor.pid
childlogdir={self.directory}
[rpcinterface:supervisor]
supervisor.rpcinterface_factory=supervisor.rpcinterface:make_main_rpcinterface
[include]
files={self.configs}/*.conf
""")
        self.output = (self.directory / "output.log").open("w")
        self.addCleanup(self.output.close)
        self.start_supervisor()
        self.addCleanup(self.stop_supervisor)

    def start_supervisor(self):
        self.supervisor = subprocess.Popen(supervisor_command() + ["-n", "-c", str(self.supervisor_config)], stdout=self.output, stderr=self.output)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.supervisor.poll() is not None:
                self.fail((self.directory / "output.log").read_text())
            if self.socket.exists():
                return
            time.sleep(0.05)
        self.fail("Supervisor did not create its socket")

    def stop_supervisor(self):
        if self.supervisor.poll() is None:
            self.supervisor.terminate()
            try:
                self.supervisor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.supervisor.kill()
                self.supervisor.wait(timeout=5)

    def ctl(self, *arguments, expected=0):
        result = subprocess.run([sys.executable, str(SHIM), *arguments], env=self.environment, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result.stdout.strip()

    def unit(self, name, args="100"):
        path = self.units / f"{name}.service"
        path.write_text(f"[Service]\nType=simple\nExecStart=/bin/sleep {args}\nRestart=always\n")
        return path

    def pid(self, name):
        return int(self.ctl("show", name, "--property=MainPID", "--value"))

    def test_enable_reload_restart_metadata_and_persistent_startup(self):
        self.unit("validator")
        self.unit("mytoncore")
        self.ctl("daemon-reload")
        self.ctl("is-active", "--quiet", "validator", expected=3)
        self.ctl("enable", "validator.service")
        self.assertEqual(self.ctl("is-enabled", "validator"), "enabled")
        self.ctl("start", "validator")
        self.ctl("start", "mytoncore")
        first_pid = self.pid("validator")
        controller_pid = self.pid("mytoncore")
        self.assertGreater(first_pid, 0)
        self.assertGreater(int(self.ctl("show", "validator", "--property=ExecMainStartTimestampMonotonic", "--value")), 0)
        self.ctl("is-active", "--quiet", "validator.service")
        self.assertEqual(self.ctl("show", "validator", "--property=SubState", "--value"), "RUNNING")
        self.assertEqual(self.ctl("show", "validator", "--property=ExecMainStatus", "--value"), "0")
        self.assertIn("ExecStart=/bin/sleep 100", self.ctl("cat", "validator"))
        self.unit("validator", "120")
        self.ctl("daemon-reload")
        self.assertEqual(self.pid("validator"), first_pid)
        self.assertEqual(self.pid("mytoncore"), controller_pid)
        self.ctl("restart", "validator")
        second_pid = self.pid("validator")
        self.assertNotEqual(second_pid, first_pid)
        self.assertEqual(Path(f"/proc/{second_pid}/cmdline").read_bytes(), b"/bin/sleep\x00120\x00")
        self.assertEqual(self.pid("mytoncore"), controller_pid)
        self.ctl("stop", "validator")
        self.ctl("is-active", "--quiet", "validator", expected=3)
        self.assertEqual(self.pid("validator"), 0)
        self.stop_supervisor()
        self.start_supervisor()
        self.ctl("initialize")
        self.ctl("is-active", "--quiet", "validator")
        self.ctl("is-active", "--quiet", "mytoncore", expected=3)
        self.ctl("disable", "--now", "validator")
        self.assertEqual(self.ctl("is-enabled", "validator", expected=1), "disabled")
        self.ctl("is-active", "--quiet", "validator", expected=3)

    def test_removed_running_unit_continues_until_stopped(self):
        path = self.unit("validator")
        self.ctl("start", "validator")
        pid = self.pid("validator")
        path.unlink()
        self.ctl("daemon-reload")
        self.assertEqual(self.pid("validator"), pid)
        self.ctl("stop", "validator")
        self.ctl("daemon-reload")
        self.ctl("is-active", "--quiet", "validator", expected=3)

    def test_pre_start_sleep_is_not_reported_as_successful_validator_launch(self):
        path = self.units / "validator.service"
        path.write_text("[Service]\nType=simple\nExecStartPre=/bin/sleep 2\nExecStart=/bin/false\nRestart=always\n")
        result = subprocess.run([sys.executable, str(SHIM), "start", "validator"], env=self.environment,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("SPAWN_ERROR", result.stderr)
        self.assertIn(self.ctl("show", "validator", "--property=SubState", "--value"), ("BACKOFF", "FATAL"))
        self.ctl("is-active", "--quiet", "validator", expected=3)


if __name__ == "__main__":
    unittest.main()
