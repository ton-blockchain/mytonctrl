import subprocess

import pytest
from pytest_mock import MockerFixture


def _completed(stdout=b"", stderr=b"", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------- Fift ----------

def test_fift_run_builds_args_and_returns_stdout(ton, mocker: MockerFixture):
    run_mock = mocker.patch("mytoncore.clients.subprocess.run", return_value=_completed(stdout=b"hello"))

    output = ton.fift.run(["script.fif", 42])

    assert output == "hello"
    assert run_mock.call_args.args[0] == [
        ton.fift.app_path,
        "-I", ton.fift.libs_path + ":" + ton.fift.smartconts_path,
        "-s",
        "script.fif",
        "42",  # non-string args coerced via str()
    ]
    assert run_mock.call_args.kwargs["timeout"] == 3


def test_fift_run_raises_on_nonzero_returncode(ton, mocker: MockerFixture):
    mocker.patch(
        "mytoncore.clients.subprocess.run",
        return_value=_completed(stderr=b"boom", returncode=1),
    )

    with pytest.raises(Exception, match="fift error: boom"):
        ton.fift.run(["x.fif"])


def test_fift_run_honors_db_timeout(ton, mocker: MockerFixture):
    ton.local.db.fift_timeout = 17
    run_mock = mocker.patch("mytoncore.clients.subprocess.run", return_value=_completed())

    ton.fift.run(["x.fif"])

    assert run_mock.call_args.kwargs["timeout"] == 17


# ---------- LiteClient ----------

def _stub_status(ton, out_of_sync):
    ton.liteClient.get_validator_status = lambda: {"out_of_sync": out_of_sync}


def test_liteclient_run_uses_explicit_index(ton, mocker: MockerFixture):
    _stub_status(ton, 0)
    run_mock = mocker.patch(
        "mytoncore.clients.subprocess.run", return_value=_completed(stdout=b"ok")
    )

    output = ton.liteClient.run("getconfig", index=5)

    assert output == "ok"
    assert run_mock.call_args.args[0] == [
        ton.liteClient.app_path,
        "--global-config", ton.liteClient.config_path,
        "--verbosity", "0",
        "--cmd", "getconfig",
        "-i", "5",
    ]


def test_liteclient_run_uses_local_liteserver_when_in_sync(ton, mocker: MockerFixture):
    _stub_status(ton, 5)
    run_mock = mocker.patch(
        "mytoncore.clients.subprocess.run", return_value=_completed(stdout=b"ok")
    )

    ton.liteClient.run("getconfig")

    assert run_mock.call_args.args[0] == [
        ton.liteClient.app_path,
        "--addr", ton.liteClient.addr,
        "--pub", ton.liteClient.pub_key_path,
        "--verbosity", "0",
        "--cmd", "getconfig",
    ]


def test_liteclient_run_falls_back_to_db_liteservers_when_out_of_sync(ton, mocker: MockerFixture):
    _stub_status(ton, 100)
    ton.local.db["liteServers"] = [7]
    run_mock = mocker.patch(
        "mytoncore.clients.subprocess.run", return_value=_completed(stdout=b"ok")
    )

    ton.liteClient.run("getconfig")

    assert run_mock.call_args.args[0][-2:] == ["-i", "7"]


def test_liteclient_run_local_connects_only_to_local_liteserver(ton, mocker: MockerFixture):
    run_mock = mocker.patch(
        "mytoncore.clients.subprocess.run", return_value=_completed(stdout=b"ok")
    )

    output = ton.liteClient.run_local("runmethodx addr method")

    assert output == "ok"
    assert run_mock.call_args.args[0] == [
        ton.liteClient.app_path,
        "--addr", ton.liteClient.addr,
        "--pub", ton.liteClient.pub_key_path,
        "--verbosity", "0",
        "--cmd", "runmethodx addr method",
    ]


def test_liteclient_run_local_raises_when_local_liteserver_not_configured(ton):
    ton.liteClient.addr = None

    with pytest.raises(Exception, match="local liteserver is not configured"):
        ton.liteClient.run_local("last")


def test_liteclient_run_raises_on_stderr(ton, mocker: MockerFixture):
    _stub_status(ton, 0)
    mocker.patch(
        "mytoncore.clients.subprocess.run", return_value=_completed(stderr=b"boom")
    )

    with pytest.raises(Exception, match="liteclient error: boom"):
        ton.liteClient.run("getconfig", index=0)


# ---------- ValidatorConsole ----------

def test_validator_console_run_builds_args_and_returns_stdout(ton, mocker: MockerFixture):
    run_mock = mocker.patch(
        "mytoncore.clients.subprocess.run",
        return_value=_completed(stdout=b"v-out"),
    )

    output = ton.validatorConsole.run("getstats")

    assert output == "v-out"
    assert run_mock.call_args.args[0] == [
        ton.validatorConsole.app_path,
        "-k", ton.validatorConsole.priv_key_path,
        "-p", ton.validatorConsole.pub_key_path,
        "-a", ton.validatorConsole.addr,
        "-v", "0",
        "--cmd", "getstats",
    ]


def test_validator_console_run_raises_when_unconfigured(ton):
    ton.validatorConsole.app_path = None
    with pytest.raises(Exception, match="console error: app_path is None"):
        ton.validatorConsole.run("getstats")


def test_validator_console_run_raises_on_stderr(ton, mocker: MockerFixture):
    mocker.patch(
        "mytoncore.clients.subprocess.run",
        return_value=_completed(stderr=b"oops"),
    )

    with pytest.raises(Exception, match="console error: oops"):
        ton.validatorConsole.run("getstats")
