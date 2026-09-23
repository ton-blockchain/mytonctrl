import os
from pytest_mock import MockerFixture
from mypylib import Dict
from mytoncore.mytoncore import MyTonCore

from tests.helpers import create_pool_file


def test_pools_list(cli, ton, monkeypatch, mocker: MockerFixture):
    get_pools_mock = mocker.Mock()
    get_account_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, "GetPools", get_pools_mock)
    monkeypatch.setattr(MyTonCore, "GetAccount", get_account_mock)

    output = cli.execute("pools_list extra", no_color=True)
    assert "usage: pools_list [-h]" in output
    assert "pools_list: error: unrecognized arguments: extra" in output
    get_pools_mock.assert_not_called()

    # no pools
    get_pools_mock.return_value = []
    output = cli.execute("pools_list", no_color=True)
    assert "No data" in output
    get_account_mock.assert_not_called()
    get_pools_mock.assert_called_once()

    # happy path
    get_pools_mock.reset_mock()
    pool1 = Dict()
    pool1.name = "pool1"
    pool1.addrB64 = "pool1_addr"
    pool1.addrB64_init = "pool1_addr_init"
    pool2 = Dict()
    pool2.name = "pool2"
    pool2.addrB64 = "pool2_addr"
    pool2.addrB64_init = "pool2_addr_init"
    get_pools_mock.return_value = [pool1, pool2]

    account1 = Dict()
    account1.status = "active"
    account1.balance = 100.5
    account1.codeHash = "42bea8fea43bf803c652411976eb2981b9bdb10da84eb788a63ea7a01f2a044d"
    account2 = Dict()
    account2.status = "uninit"
    account2.balance = 0
    account2.codeHash = None

    get_account_mock.side_effect = [account1, account2]

    output = cli.execute("pools_list", no_color=True)
    assert output.splitlines()[1].split() == ["pool1", "active", "100.5", "spool_r2", "pool1_addr"]
    assert output.splitlines()[2].split() == ["pool2", "uninit", "0", "None", "pool2_addr_init"]

    assert get_pools_mock.call_count == 1
    assert get_account_mock.call_count == 2


def test_delete_pool(cli, ton):
    # Bad args
    output = cli.execute("delete_pool")
    assert "usage: delete_pool [-h] pool_name" in output
    assert "delete_pool: error: the following arguments are required: pool_name" in output
    output = cli.execute("delete_pool a b", no_color=True)
    assert "delete_pool: error: unrecognized arguments: b" in output

    pool_name = 'test_pool'
    pool_path = ton.poolsDir + pool_name
    create_pool_file(pool_path, b"\x00" * 32 + b'\xff\xff\xff\xff')

    # happy path
    output = cli.execute(f"delete_pool {pool_name}", no_color=True)
    assert "DeletePool - OK" in output
    assert not os.path.exists(pool_path + '.addr')


def test_import_pool(cli, ton, monkeypatch, mocker: MockerFixture):
    # Bad args
    output = cli.execute("import_pool", no_color=True)
    assert "usage: import_pool [-h] pool_name pool_addr" in output
    assert "import_pool: error: the following arguments are required: pool_name, pool_addr" in output
    output = cli.execute(f"import_pool abcd", no_color=True)
    assert "import_pool: error: the following arguments are required: pool_addr" in output
    output = cli.execute("import_pool abcd not_an_address", no_color=True)
    assert "import_pool: error: argument pool_addr: expected a TON address (in user-friendly or raw form), got 'not_an_address'" in output
    assert not os.path.exists(ton.poolsDir + "abcd.addr")

    # happy path
    download_contract_mock = mocker.Mock()
    monkeypatch.setattr(MyTonCore, 'DownloadContract', download_contract_mock)
    pool_name = "imported_pool"
    pool_addr = "Ef8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADAU"
    pool_path = ton.poolsDir + pool_name
    addr_file = pool_path + ".addr"
    assert not os.path.exists(addr_file)

    output = cli.execute(f"import_pool {pool_name} {pool_addr}", no_color=True)

    assert "import_pool - OK" in output
    download_contract_mock.assert_called_once()
    assert os.path.isfile(addr_file)
