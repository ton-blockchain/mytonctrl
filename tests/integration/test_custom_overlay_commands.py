import json

import pytest
from pytest_mock import MockerFixture

from mytoncore.mytoncore import MyTonCore
from mytoncore.utils import hex2base64
from modules.custom_overlays import CustomOverlayModule


STATIC_NODE_HEX = "aa" * 32
VALIDATOR_NODE_HEX = "bb" * 32


@pytest.fixture()
def overlay_module(ton):
    return CustomOverlayModule(ton, ton.local)


def _write_config(tmp_path, name, config):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(config))
    return str(path)


def _mock_validator_console(mocker, ton, run_return="success"):
    vc = mocker.Mock()
    vc.run.return_value = run_return
    ton._validator_console = vc
    return vc


def _mock_validator_config(monkeypatch, adnl_ids):
    adnls = [type("A", (), {"id": i})() for i in adnl_ids]
    monkeypatch.setattr(
        MyTonCore, "GetValidatorConfig",
        lambda self: type("C", (), {"adnl": adnls})(),
    )


def test_parse_config_static_nodes(overlay_module):
    config = {
        STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 5},
        "cc" * 32: {"block_sender": True},
    }
    result = overlay_module.parse_config("myoverlay", config)
    assert result["name"] == "myoverlay"
    assert len(result["nodes"]) == 2
    msg_node = next(n for n in result["nodes"] if "msg_sender" in n)
    assert msg_node["adnl_id"] == hex2base64(STATIC_NODE_HEX)
    assert msg_node["msg_sender"] is True
    assert msg_node["msg_sender_priority"] == 5
    block_node = next(n for n in result["nodes"] if "block_sender" in n)
    assert block_node["adnl_id"] == hex2base64("cc" * 32)
    assert block_node["block_sender"] is True


def test_parse_config_validators_expands_vset(overlay_module):
    config = {"@validators": True}
    vset = [VALIDATOR_NODE_HEX, "dd" * 32]
    result = overlay_module.parse_config("dyn", config, vset=vset)
    assert result["name"] == "dyn"
    assert [n["adnl_id"] for n in result["nodes"]] == [hex2base64(v) for v in vset]
    assert all(n["msg_sender"] is False for n in result["nodes"])


def test_parse_config_use_quic_default_true_when_absent(overlay_module):
    config = {STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1}}
    result = overlay_module.parse_config("o", config)
    assert result["use_quic"] is True


def test_parse_config_use_quic_default_false_when_absent(overlay_module, ton):
    ton.local.db['customOverlaysUseQuic'] = False
    config = {STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1}}
    result = overlay_module.parse_config("o", config)
    assert result["use_quic"] is False


def test_parse_config_use_quic_from_config_wins_over_default(overlay_module, ton):
    ton.local.db['customOverlaysUseQuic'] = True
    config = {
        "use_quic": False,
        STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1},
    }
    result = overlay_module.parse_config("o", config)
    assert result["use_quic"] is False
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["adnl_id"] == hex2base64(STATIC_NODE_HEX)


def test_parse_config_use_quic_with_validators(overlay_module, ton):
    ton.local.db['customOverlaysUseQuic'] = True
    config = {"@validators": True, "use_quic": False}
    vset = [VALIDATOR_NODE_HEX]
    result = overlay_module.parse_config("dyn", config, vset=vset)
    assert result["use_quic"] is False
    assert len(result["nodes"]) == 1


def test_add_custom_overlay_bad_args(cli):
    output = cli.execute("add_custom_overlay", no_color=True)
    assert "Bad args" in output
    output = cli.execute("add_custom_overlay only_name", no_color=True)
    assert "Bad args" in output


def test_add_custom_overlay_static(cli, ton, tmp_path, monkeypatch, mocker: MockerFixture):
    config = {STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1}}
    path = _write_config(tmp_path, "static_cfg", config)
    vc = _mock_validator_console(mocker, ton)
    _mock_validator_config(monkeypatch, [hex2base64(STATIC_NODE_HEX)])

    output = cli.execute(f"add_custom_overlay myoverlay {path}", no_color=True)
    assert "add_custom_overlay - OK" in output
    assert ton.get_custom_overlays()["myoverlay"] == config
    vc.run.assert_called_once()
    assert vc.run.call_args[0][0].startswith("addcustomoverlay ")


def _read_emitted_vc_config(ton, name):
    with open(ton.tempDir + f'/custom_overlay_{name}.json', 'r') as f:
        return json.load(f)


def test_add_custom_overlay_emits_use_quic_true_by_default(cli, ton, tmp_path, monkeypatch, mocker: MockerFixture):
    config = {STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1}}
    path = _write_config(tmp_path, "quic_def_cfg", config)
    _mock_validator_console(mocker, ton)
    _mock_validator_config(monkeypatch, [hex2base64(STATIC_NODE_HEX)])

    cli.execute(f"add_custom_overlay quic_def {path}", no_color=True)
    assert _read_emitted_vc_config(ton, "quic_def")["use_quic"] is True


def test_add_custom_overlay_global_setting_disables_use_quic(cli, ton, tmp_path, monkeypatch, mocker: MockerFixture):
    ton.local.db['customOverlaysUseQuic'] = False
    config = {STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1}}
    path = _write_config(tmp_path, "quic_off_cfg", config)
    _mock_validator_console(mocker, ton)
    _mock_validator_config(monkeypatch, [hex2base64(STATIC_NODE_HEX)])

    cli.execute(f"add_custom_overlay quic_off {path}", no_color=True)
    assert _read_emitted_vc_config(ton, "quic_off")["use_quic"] is False


def test_add_custom_overlay_per_overlay_use_quic_wins_over_global(cli, ton, tmp_path, monkeypatch, mocker: MockerFixture):
    ton.local.db['customOverlaysUseQuic'] = False
    config = {
        "use_quic": True,
        STATIC_NODE_HEX: {"msg_sender": True, "msg_sender_priority": 1},
    }
    path = _write_config(tmp_path, "quic_per_cfg", config)
    _mock_validator_console(mocker, ton)
    _mock_validator_config(monkeypatch, [hex2base64(STATIC_NODE_HEX)])

    cli.execute(f"add_custom_overlay quic_per {path}", no_color=True)
    assert _read_emitted_vc_config(ton, "quic_per")["use_quic"] is True


def test_add_custom_overlay_dynamic_validators(cli, ton, tmp_path, mocker: MockerFixture):
    config = {"@validators": True}
    path = _write_config(tmp_path, "dyn_cfg", config)
    vc = _mock_validator_console(mocker, ton)

    output = cli.execute(f"add_custom_overlay dyn {path}", no_color=True)
    assert "Dynamic overlay will be added within 1 minute" in output
    assert "add_custom_overlay - OK" in output
    assert ton.get_custom_overlays()["dyn"] == config
    vc.run.assert_not_called()


def test_list_custom_overlays(cli, ton):
    output = cli.execute("list_custom_overlays", no_color=True)
    assert "No custom overlays" in output

    ton.set_custom_overlay("foo", {STATIC_NODE_HEX: {"block_sender": True}})
    output = cli.execute("list_custom_overlays", no_color=True)
    assert "Custom overlay foo" in output
    assert STATIC_NODE_HEX in output


def test_delete_custom_overlay(cli, ton, monkeypatch, mocker: MockerFixture):
    ton.set_custom_overlay("static_one", {STATIC_NODE_HEX: {"block_sender": True}})
    ton.set_custom_overlay("dyn_one", {"@validators": True})
    vc = _mock_validator_console(mocker, ton)

    output = cli.execute("delete_custom_overlay", no_color=True)
    assert "Bad args" in output

    output = cli.execute("delete_custom_overlay static_one", no_color=True)
    assert "delete_custom_overlay - OK" in output
    assert "static_one" not in ton.get_custom_overlays()
    vc.run.assert_called_once_with("delcustomoverlay static_one")

    vc.run.reset_mock()
    output = cli.execute("delete_custom_overlay dyn_one", no_color=True)
    assert "Dynamic overlay will be deleted within 1 minute" in output
    assert "delete_custom_overlay - OK" in output
    assert "dyn_one" not in ton.get_custom_overlays()
    vc.run.assert_not_called()
