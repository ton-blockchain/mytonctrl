import socket
import subprocess

from mytoncore import MyTonCore
from mytonctrl import mytonctrl
from pytest_mock import MockerFixture


def test_check_mytonctrl_update(cli, monkeypatch):
    monkeypatch.setattr(mytonctrl, 'warnings', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_installer_user', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_vport', lambda *_: None)
    monkeypatch.setattr(mytonctrl.os.path, 'exists', lambda _: True)

    monkeypatch.setattr(mytonctrl, 'check_git_update', lambda *_: True)
    output = cli.run_pre_up()
    assert 'MyTonCtrl update available' in output

    monkeypatch.setattr(mytonctrl, 'check_git_update', lambda *_: False)
    output = cli.run_pre_up()
    assert 'MyTonCtrl update available' not in output

    monkeypatch.setattr(mytonctrl.os.path, 'exists', lambda _: False)

    monkeypatch.setattr(mytonctrl, 'check_git_update', lambda *_: True)
    output = cli.run_pre_up()
    assert 'MyTonCtrl update available' not in output


def test_check_installer_user(cli, monkeypatch, mocker: MockerFixture):
    monkeypatch.setattr(mytonctrl, 'check_mytonctrl_update', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'warnings', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_vport', lambda *_: None)

    whoami_result = mocker.Mock()
    whoami_result.stdout = b'testuser\n'
    ls_result = mocker.Mock()
    ls_result.stdout = b'total 0\n-rw-r--r-- 1 testuser testuser 0 Jan 1 00:00 file\n'

    run_mock = mocker.Mock(side_effect=[whoami_result, ls_result])
    monkeypatch.setattr(subprocess, 'run', run_mock)
    output = cli.run_pre_up()
    assert 'mytonctrl was installed by another user' not in output

    whoami_result.stdout = b'currentuser\n'
    ls_result.stdout = b'total 0\n-rw-r--r-- 1 installeruser testuser 0 Jan 1 00:00 file\n'

    run_mock = mocker.Mock(side_effect=[whoami_result, ls_result])
    monkeypatch.setattr(subprocess, 'run', run_mock)
    output = cli.run_pre_up()
    assert 'mytonctrl was installed by another user' in output
    assert f'launch mtc with `installeruser` user' in output


def test_check_vport(cli, monkeypatch, mocker: MockerFixture):
    monkeypatch.setattr(mytonctrl, 'check_mytonctrl_update', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'warnings', lambda *_: None)
    monkeypatch.setattr(mytonctrl, 'check_installer_user', lambda *_: None)

    monkeypatch.setattr(MyTonCore, 'GetValidatorConfig', mocker.Mock(side_effect=Exception('test error')))
    output = cli.run_pre_up()
    assert 'GetValidatorConfig error' in output

    vconfig_mock = mocker.Mock()
    addr_mock = mocker.Mock()
    addr_mock.ip = 16777343  # 127.0.0.1
    addr_mock.port = 8080
    vconfig_mock.addrs = [addr_mock]
    monkeypatch.setattr(MyTonCore, 'GetValidatorConfig', lambda *_: vconfig_mock)

    socket_mock = mocker.Mock()
    socket_mock.connect_ex.return_value = 0
    socket_mock.__enter__ = mocker.Mock(return_value=socket_mock)
    socket_mock.__exit__ = mocker.Mock()
    monkeypatch.setattr(socket, 'socket', mocker.Mock(return_value=socket_mock))

    output = cli.run_pre_up()
    assert 'UDP port of the validator is not accessible' not in output

    vconfig_mock.addrs = [addr_mock]
    socket_mock.connect_ex.return_value = 1
    output = cli.run_pre_up()
    assert 'UDP port of the validator is not accessible' in output
