import os
import struct
import types
from typing import Any

from mytoncore.models import Config, ValidatorConfig, WorkchainConfig
import pytest

from mytoncore.mytoncore import MyTonCore, Account, raw_addr_to_b64


def test_getseqno(ton: MyTonCore, monkeypatch):
    wallet = types.SimpleNamespace(addrB64='addr')
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: 'some output without keyword')
    with pytest.raises(Exception) as e:
        ton.get_seqno(wallet)
    assert 'not found' in str(e.value)
    output = 'something\narguments:  [ 85143 ]\n result:  [ 297 ]'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: output)
    assert ton.get_seqno(wallet) == 297


def test_getaccount(ton: MyTonCore, monkeypatch):
    hex_addr = 'A' * 64
    addr_b64 = raw_addr_to_b64(f"0:{hex_addr}")

    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: '\naccount state is empty\n')
    acc = ton.GetAccount(addr_b64)
    assert isinstance(acc, Account)
    assert acc.workchain == 0 and acc.addr.lower() == hex_addr.lower()
    assert acc.status == 'empty' and acc.balance == 0

    hex_addr = '5' * 64
    addr_b64 = raw_addr_to_b64(f"-1:{hex_addr}")
    result = 'account state is (account\n  addr:(addr_std\n    anycast:nothing workchain_id:-1 address:x5555555555555555555555555555555555555555555555555555555555555555)\n  storage_stat:(storage_info\n    used:(storage_used\n      cells:(var_uint len:2 value:777)\n      bits:(var_uint len:3 value:128349))\n    storage_extra:storage_extra_none last_paid:0\n    due_payment:nothing)\n  storage:(account_storage last_trans_lt:38172562000004\n    balance:(currencies\n      grams:(nanograms\n        amount:(var_uint len:6 value:14800341552964))\n      other:(extra_currencies\n        dict:hme_empty))\n    state:(account_active\n      (\n        fixed_prefix_length:nothing\n        special:(just\n          value:(tick_tock tick:0 tock:1))\n        code:(just\n          value:(raw@^Cell \n            x{}\n             x{FF00F4A413F4BCF2C80B}\nlast transaction lt = 38172562000003 hash = A595A77E0DE9392C98AA04F9272B896FC9E444A7472462BA87F0E6E256F1C09E\naccount balance is 14800341552964ng'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    acc = ton.GetAccount(addr_b64)
    assert isinstance(acc, Account)
    assert acc.workchain == -1 and acc.addr == hex_addr
    assert acc.addrB64 == 'Ef9VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVbxn'
    assert acc.status == 'active'
    assert acc.balance == 14800.341552964
    assert acc.lt == '38172562000003'
    assert acc.hash == 'A595A77E0DE9392C98AA04F9272B896FC9E444A7472462BA87F0E6E256F1C09E'
    assert acc.codeHash == '57db8219f434d4aa2f4925fb8225c41414fc1957877c4034fd0a727022c40c52'


def test_getaccounthistory_iterates(ton: MyTonCore, monkeypatch):
    hex_addr = '5' * 64
    addr_b64 = raw_addr_to_b64(f"-1:{hex_addr}")
    result = 'account state is (account\n  addr:(addr_std\n    anycast:nothing workchain_id:-1 address:x5555555555555555555555555555555555555555555555555555555555555555)\n  storage_stat:(storage_info\n    used:(storage_used\n      cells:(var_uint len:2 value:777)\n      bits:(var_uint len:3 value:128349))\n    storage_extra:storage_extra_none last_paid:0\n    due_payment:nothing)\n  storage:(account_storage last_trans_lt:38172562000004\n    balance:(currencies\n      grams:(nanograms\n        amount:(var_uint len:6 value:14800341552964))\n      other:(extra_currencies\n        dict:hme_empty))\n    state:(account_active\n      (\n        fixed_prefix_length:nothing\n        special:(just\n          value:(tick_tock tick:0 tock:1))\n        code:(just\n          value:(raw@^Cell \n            x{}\n             x{FF00F4A413F4BCF2C80B}\nlast transaction lt = 38172562000003 hash = A595A77E0DE9392C98AA04F9272B896FC9E444A7472462BA87F0E6E256F1C09E\naccount balance is 14800341552964ng'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    acc = ton.GetAccount(addr_b64)

    result = 'transaction #0 from block (-1,8000000000000000,34531401):F5DD94863192A9052D5FC4052C4E5F0D25420F18EDC09C0669E6912887D7B0B8:FD957FD947FEC43CD1D18AB8EA7ABACA36D4DC4A5527B207AB464D28FA775273 is (transaction account_addr:x5555555555555555555555555555555555555555555555555555555555555555 lt:38172562000003 prev_trans_hash:x499DBB3F2DE5A8BADB760D7133D6D1C0BD31C289CDD318AC734ABFB29926E762 prev_trans_lt:38172561000003 now:1755791347 outmsg_cnt:0\n  orig_status:acc_state_active\n  end_status:acc_state_active\n  (\n    in_msg:nothing\n    out_msgs:hme_empty)\n  total_fees:(currencies\n    grams:(nanograms\n      amount:(var_uint len:0 value:0))\n    other:(extra_currencies\n      dict:hme_empty))\n  state_update:(update_hashes old_hash:x8138F460D03985367CF108CFFCB7734AB8227AC91BCB61F699784C3640EFE25A new_hash:x812706598B3B4E358E6B87766F2FAA7EFDCF013EE3F53D37432F38D8D138BAF7)\n  description:(trans_tick_tock is_tock:1\n    storage_ph:(tr_phase_storage\n      storage_fees_collected:(nanograms\n        amount:(var_uint len:0 value:0))\n      storage_fees_due:nothing\n      status_change:acst_unchanged)\n    compute_ph:(tr_phase_compute_vm success:1 msg_state_used:0 account_activated:0\n      gas_fees:(nanograms\n        amount:(var_uint len:0 value:0))\n      (\n        gas_used:(var_uint len:2 value:3436)\n        gas_limit:(var_uint len:4 value:35000000)\n        gas_credit:nothing mode:0 exit_code:0\n        exit_arg:nothing vm_steps:79 vm_init_state_hash:x0000000000000000000000000000000000000000000000000000000000000000 vm_final_state_hash:x0000000000000000000000000000000000000000000000000000000000000000))\n    action:(just\n      value:^(tr_phase_action success:1 valid:1 no_funds:0\n        status_change:acst_unchanged\n        total_fwd_fees:nothing\n        total_action_fees:nothing result_code:0\n        result_arg:nothing tot_actions:0 spec_actions:0 skipped_actions:0 msgs_created:0 action_list_hash:x96A296D224F285C67BEE93C30F8A309157F0DAA35DC5B87E410B78630A09CFC7\n        tot_msg_size:(storage_used\n          cells:(var_uint len:0 value:0)\n          bits:(var_uint len:0 value:0)))) aborted:0 destroyed:0))\nx{75555555555555555555555555555555555555555555555555555555555555555000022B7BDFF8883499DBB3F2DE5A8BADB760D7133D6D1C0BD31C289CDD318AC734ABFB29926E762000022B7BDF0464368A73FF3000140}\n x{2_}\n x{728138F460D03985367CF108CFFCB7734AB8227AC91BCB61F699784C3640EFE25A812706598B3B4E358E6B87766F2FAA7EFDCF013EE3F53D37432F38D8D138BAF7}\n x{303024_}\n  x{41AD9008583B0000000000000000004F00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}\n  x{C00000000000000000000000012D452DA449E50B8CF7DD27861F146122AFE1B546BB8B70FC8216F0C614139F8E04_}\n  time=1755791347 outmsg_cnt=0\n  (no inbound message)\ntransaction #0 from block (-1,8000000000000000,34531400):D46BED70DB9A9D565827125D36534F9BFF3640CB45A3D8A5462CD42899F0B760:DFF31409E08A6D83983E7CA2E2638B2420FD7AEBBC894137E5889E4B867DFC1E is (transaction account_addr:x5555555555555555555555555555555555555555555555555555555555555555 lt:38172561000003 prev_trans_hash:x4BFB25D30229F04A203299B98B0AEE18AC7966B9EB5FB38D04278EB09272A8D7 prev_trans_lt:38172560000003 now:1755791344 outmsg_cnt:0\n  orig_status:acc_state_active\n  end_status:acc_state_active\n  (\n    in_msg:nothing\n    out_msgs:hme_empty)\n  total_fees:(currencies\n    grams:(nanograms\n      amount:(var_uint len:0 value:0))\n    other:(extra_currencies\n      dict:hme_empty))\n  state_update:(update_hashes old_hash:xD38C26E72F216BB7F957E0EC6E5A1FCB4CC608F7C80DCB6D8238911A42C70662 new_hash:x8138F460D03985367CF108CFFCB7734AB8227AC91BCB61F699784C3640EFE25A)\n  description:(trans_tick_tock is_tock:1\n    storage_ph:(tr_phase_storage\n      storage_fees_collected:(nanograms\n        amount:(var_uint len:0 value:0))\n      storage_fees_due:nothing\n      status_change:acst_unchanged)\n    compute_ph:(tr_phase_compute_vm success:1 msg_state_used:0 account_activated:0\n      gas_fees:(nanograms\n        amount:(var_uint len:0 value:0))\n      (\n        gas_used:(var_uint len:2 value:3436)\n        gas_limit:(var_uint len:4 value:35000000)\n        gas_credit:nothing mode:0 exit_code:0\n        exit_arg:nothing vm_steps:79 vm_init_state_hash:x0000000000000000000000000000000000000000000000000000000000000000 vm_final_state_hash:x0000000000000000000000000000000000000000000000000000000000000000))\n    action:(just\n      value:^(tr_phase_action success:1 valid:1 no_funds:0\n        status_change:acst_unchanged\n        total_fwd_fees:nothing\n        total_action_fees:nothing result_code:0\n        result_arg:nothing tot_actions:0 spec_actions:0 skipped_actions:0 msgs_created:0 action_list_hash:x96A296D224F285C67BEE93C30F8A309157F0DAA35DC5B87E410B78630A09CFC7\n        tot_msg_size:(storage_used\n          cells:(var_uint len:0 value:0)\n          bits:(var_uint len:0 value:0)))) aborted:0 destroyed:0))\nx{75555555555555555555555555555555555555555555555555555555555555555000022B7BDF046434BFB25D30229F04A203299B98B0AEE18AC7966B9EB5FB38D04278EB09272A8D7000022B7BDE1040368A73FF0000140}\n x{2_}\n x{72D38C26E72F216BB7F957E0EC6E5A1FCB4CC608F7C80DCB6D8238911A42C706628138F460D03985367CF108CFFCB7734AB8227AC91BCB61F699784C3640EFE25A}\n x{303024_}\n  x{41AD9008583B0000000000000000004F00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}\n  x{C00000000000000000000000012D452DA449E50B8CF7DD27861F146122AFE1B546BB8B70FC8216F0C614139F8E04_}\n  time=1755791344 outmsg_cnt=0\n  (no inbound message)\nprevious transaction has lt 38172560000003 hash 4BFB25D30229F04A203299B98B0AEE18AC7966B9EB5FB38D04278EB09272A8D7'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    hist = ton.GetAccountHistory(acc, limit=2)
    assert len(hist) == 2
    assert hist[0].time == 1755791347
    assert hist[1].time == 1755791344

    result = 'transaction #0 from block (-1,8000000000000000,34555701):7DFC618427B030E9BD1A23BFC914377193D7282C4AE60472DAEAEB86FBFEA844:145236D8EA1E9B51454FA70825551A489FE8C338ABE7A51BD9F8613C783E6584 is (transaction account_addr:x3333333333333333333333333333333333333333333333333333333333333333 lt:38197929000002 prev_trans_hash:x00492E2C6BF182E448203E34D5F0AD9F426386AD50C492F016DE04FA2B261164 prev_trans_lt:38197929000001 now:1755851757 outmsg_cnt:0\n  orig_status:acc_state_active\n  end_status:acc_state_active\n  (\n    in_msg:(just\n      value:^(message\n        info:(int_msg_info ihr_disabled:1 bounce:1 bounced:0\n          src:(addr_std\n            anycast:nothing workchain_id:-1 address:x0000000000000000000000000000000000000000000000000000000000000000)\n          dest:(addr_std\n            anycast:nothing workchain_id:-1 address:x3333333333333333333333333333333333333333333333333333333333333333)\n          value:(currencies\n            grams:(nanograms\n              amount:(var_uint len:4 value:1700000000))\n            other:(extra_currencies\n              dict:hme_empty))\n          ihr_fee:(nanograms\n            amount:(var_uint len:0 value:0))\n          fwd_fee:(nanograms\n            amount:(var_uint len:0 value:0)) created_lt:38197929000000 created_at:1755851757)\n        init:nothing\n        body:(left\n          value:(raw@Any \n            x{}\n            ))))\n    out_msgs:hme_empty)\n  total_fees:(currencies\n    grams:(nanograms\n      amount:(var_uint len:0 value:0))\n    other:(extra_currencies\n      dict:hme_empty))\n  state_update:(update_hashes old_hash:xAA0A56725F74E1B04520072592C96E72C4C7850724B67F8151770D80AA0CDC6E new_hash:x2F8354F8D5A0154862F40792E2678F10BCBF8AE1B7C4BAFBF213C8E8AE126022)\n  description:(trans_ord credit_first:0\n    storage_ph:(just\n      value:(tr_phase_storage\n        storage_fees_collected:(nanograms\n          amount:(var_uint len:0 value:0))\n        storage_fees_due:nothing\n        status_change:acst_unchanged))\n    credit_ph:(just\n      value:(tr_phase_credit\n        due_fees_collected:nothing\n        credit:(currencies\n          grams:(nanograms\n            amount:(var_uint len:4 value:1700000000))\n          other:(extra_currencies\n            dict:hme_empty))))\n    compute_ph:(tr_phase_compute_vm success:1 msg_state_used:0 account_activated:0\n      gas_fees:(nanograms\n        amount:(var_uint len:0 value:0))\n      (\n        gas_used:(var_uint len:2 value:5499)\n        gas_limit:(var_uint len:4 value:35000000)\n        gas_credit:nothing mode:0 exit_code:0\n        exit_arg:nothing vm_steps:100 vm_init_state_hash:x0000000000000000000000000000000000000000000000000000000000000000 vm_final_state_hash:x0000000000000000000000000000000000000000000000000000000000000000))\n    action:(just\n      value:^(tr_phase_action success:1 valid:1 no_funds:0\n        status_change:acst_unchanged\n        total_fwd_fees:nothing\n        total_action_fees:nothing result_code:0\n        result_arg:nothing tot_actions:0 spec_actions:0 skipped_actions:0 msgs_created:0 action_list_hash:x96A296D224F285C67BEE93C30F8A309157F0DAA35DC5B87E410B78630A09CFC7\n        tot_msg_size:(storage_used\n          cells:(var_uint len:0 value:0)\n          bits:(var_uint len:0 value:0)))) aborted:0\n    bounce:nothing destroyed:0))\nx{73333333333333333333333333333333333333333333333333333333333333333000022BDA5FD3C4200492E2C6BF182E448203E34D5F0AD9F426386AD50C492F016DE04FA2B261164000022BDA5FD3C4168A82BED000140}\n x{A_}\n  x{69FE00000000000000000000000000000000000000000000000000000000000000013FCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCD1954FC400000000457B4BFA7880D15057DA4_}\n x{72AA0A56725F74E1B04520072592C96E72C4C7850724B67F8151770D80AA0CDC6E2F8354F8D5A0154862F40792E2678F10BCBF8AE1B7C4BAFBF213C8E8AE126022}\n x{04091954FC401811_}\n  x{42AF7008583B0000000000000000006400000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}\n  x{C00000000000000000000000012D452DA449E50B8CF7DD27861F146122AFE1B546BB8B70FC8216F0C614139F8E04_}\n  time=1755851757 outmsg_cnt=0\n  inbound message: INT-MSG FROM: -1:0000000000000000000000000000000000000000000000000000000000000000 TO: -1:3333333333333333333333333333333333333333333333333333333333333333 LT:38197929000000 UTIME:1755851757 VALUE:1700000000\n    (message\n      info:(int_msg_info ihr_disabled:1 bounce:1 bounced:0\n        src:(addr_std\n          anycast:nothing workchain_id:-1 address:x0000000000000000000000000000000000000000000000000000000000000000)\n        dest:(addr_std\n          anycast:nothing workchain_id:-1 address:x3333333333333333333333333333333333333333333333333333333333333333)\n        value:(currencies\n          grams:(nanograms\n            amount:(var_uint len:4 value:1700000000))\n          other:(extra_currencies\n            dict:hme_empty))\n        ihr_fee:(nanograms\n          amount:(var_uint len:0 value:0))\n        fwd_fee:(nanograms\n          amount:(var_uint len:0 value:0)) created_lt:38197929000000 created_at:1755851757)\n      init:nothing\n      body:(left\n        value:(raw@Any \n          x{}\n          )))\ntransaction #0 from block (-1,8000000000000000,34555701):7DFC618427B030E9BD1A23BFC914377193D7282C4AE60472DAEAEB86FBFEA844:145236D8EA1E9B51454FA70825551A489FE8C338ABE7A51BD9F8613C783E6584 is (transaction account_addr:x3333333333333333333333333333333333333333333333333333333333333333 lt:38197929000001 prev_trans_hash:x493F67696762FED8D00F3FD60A49339A4B98BDC9843CCE1DC63DA8F9EBB18A19 prev_trans_lt:38197928000002 now:1755851757 outmsg_cnt:0\n  orig_status:acc_state_active\n  end_status:acc_state_active\n  (\n    in_msg:nothing\n    out_msgs:hme_empty)\n  total_fees:(currencies\n    grams:(nanograms\n      amount:(var_uint len:0 value:0))\n    other:(extra_currencies\n      dict:hme_empty))\n  state_update:(update_hashes old_hash:x4E7A7453AD9EA289526418B3DA7A48923F34227225DF616D62C4BC5ED00452A1 new_hash:xAA0A56725F74E1B04520072592C96E72C4C7850724B67F8151770D80AA0CDC6E)\n  description:(trans_tick_tock is_tock:0\n    storage_ph:(tr_phase_storage\n      storage_fees_collected:(nanograms\n        amount:(var_uint len:0 value:0))\n      storage_fees_due:nothing\n      status_change:acst_unchanged)\n    compute_ph:(tr_phase_compute_vm success:1 msg_state_used:0 account_activated:0\n      gas_fees:(nanograms\n        amount:(var_uint len:0 value:0))\n      (\n        gas_used:(var_uint len:2 value:9011)\n        gas_limit:(var_uint len:4 value:35000000)\n        gas_credit:nothing mode:0 exit_code:0\n        exit_arg:nothing vm_steps:181 vm_init_state_hash:x0000000000000000000000000000000000000000000000000000000000000000 vm_final_state_hash:x0000000000000000000000000000000000000000000000000000000000000000))\n    action:(just\n      value:^(tr_phase_action success:1 valid:1 no_funds:0\n        status_change:acst_unchanged\n        total_fwd_fees:nothing\n        total_action_fees:nothing result_code:0\n        result_arg:nothing tot_actions:0 spec_actions:0 skipped_actions:0 msgs_created:0 action_list_hash:x96A296D224F285C67BEE93C30F8A309157F0DAA35DC5B87E410B78630A09CFC7\n        tot_msg_size:(storage_used\n          cells:(var_uint len:0 value:0)\n          bits:(var_uint len:0 value:0)))) aborted:0 destroyed:0))\nx{73333333333333333333333333333333333333333333333333333333333333333000022BDA5FD3C41493F67696762FED8D00F3FD60A49339A4B98BDC9843CCE1DC63DA8F9EBB18A19000022BDA5EDFA0268A82BED000140}\n x{2_}\n x{724E7A7453AD9EA289526418B3DA7A48923F34227225DF616D62C4BC5ED00452A1AA0A56725F74E1B04520072592C96E72C4C7850724B67F8151770D80AA0CDC6E}\n x{203024_}\n  x{44667008583B000000000000000000B500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000}\n  x{C00000000000000000000000012D452DA449E50B8CF7DD27861F146122AFE1B546BB8B70FC8216F0C614139F8E04_}\n  time=1755851757 outmsg_cnt=0\n  (no inbound message)\nprevious transaction has lt 38197928000002 hash 493F67696762FED8D00F3FD60A49339A4B98BDC9843CCE1DC63DA8F9EBB18A19'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    hist = ton.GetAccountHistory(acc, limit=2)
    assert len(hist) == 2
    assert hist[0].time == 1755851757
    assert hist[1].time == 1755851757
    assert hist[0].src_workchain == -1 and hist[0].dest_workchain == -1
    assert hist[0].src_addr == '0000000000000000000000000000000000000000000000000000000000000000' and hist[0].dest_addr == '3333333333333333333333333333333333333333333333333333333333333333'
    assert hist[0].value == 1.7
    assert hist[0].body is None and hist[0].comment is None
    assert hist[0].ihr_disabled == 1


def test_getaccounthistory_paginates(ton: MyTonCore, monkeypatch):
    from mytoncore.models import Block, Message, Transaction
    acc = Account(-1, '5' * 64, status='active', lt='100', hash='HASH0')

    def make_msg(t):
        tr = Transaction(block=Block(-1, '8000000000000000', 1, 'r', 'f'), type='ord', time=t, total_fees=0.0)
        return Message(transaction=tr, src_workchain=-1, dest_workchain=-1, src_addr='', dest_addr='',
                       value=0.0, body=None, comment=None, ihr_fee=0.0, fwd_fee=0.0, ihr_disabled=1)

    calls = []
    batches = [
        ([make_msg(1), make_msg(2)], '90', 'HASH1'),
        ([make_msg(3), make_msg(4)], '80', 'HASH2'),
        ([make_msg(5)], None, None),
    ]

    def fake_last_trans_dump(addr, lt, trans_hash, count=10):
        calls.append((addr, lt, trans_hash))
        return batches[len(calls) - 1]

    monkeypatch.setattr(ton, 'LastTransDump', fake_last_trans_dump)

    hist = ton.GetAccountHistory(acc, limit=100)
    assert len(calls) == 3  # loop iterated until prev-trans lt was None
    assert [m.time for m in hist] == [1, 2, 3, 4, 5]
    assert calls[0] == ('-1:' + '5' * 64, '100', 'HASH0')  # seeded from account
    assert calls[1] == ('-1:' + '5' * 64, '90', 'HASH1')   # threaded from batch 0
    assert calls[2] == ('-1:' + '5' * 64, '80', 'HASH2')   # threaded from batch 1


def test_getaccounthistory_stops_at_limit(ton: MyTonCore, monkeypatch):
    from mytoncore.models import Block, Message, Transaction
    acc = Account(-1, '5' * 64, status='active', lt='100', hash='HASH0')

    def make_msg(t):
        tr = Transaction(block=Block(-1, '8000000000000000', 1, 'r', 'f'), type='ord', time=t, total_fees=0.0)
        return Message(transaction=tr, src_workchain=-1, dest_workchain=-1, src_addr='', dest_addr='',
                       value=0.0, body=None, comment=None, ihr_fee=0.0, fwd_fee=0.0, ihr_disabled=1)

    calls = []

    def fake_last_trans_dump(addr, lt, trans_hash, count=10):
        calls.append((addr, lt, trans_hash))
        return [make_msg(len(calls))], str(100 - len(calls)), f'HASH{len(calls)}'

    monkeypatch.setattr(ton, 'LastTransDump', fake_last_trans_dump)

    hist = ton.GetAccountHistory(acc, limit=3)
    assert len(calls) == 3  # stopped because len(history) >= limit, not because lt was None
    assert len(hist) == 3


def _write_addr_file(path: str, addr_hex: str, workchain: int):
    with open(path, 'wb') as f:
        f.write(bytes.fromhex(addr_hex))
        f.write(struct.pack('i', workchain))


def test_getlocalwallet(ton: MyTonCore, tmp_path):
    # prepare wallet files
    name = 'w1'
    addr_hex = '5' * 64
    workchain = 0
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, addr_hex, workchain)

    w = ton.GetLocalWallet(name, version='v1')
    assert w.name == name and w.version == 'v1'
    assert w.addr.lower() == addr_hex.lower()
    assert w.workchain == workchain
    assert w.addrB64 == 'EQBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVUMv' and w.addrB64_init == 'UQBVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVR7q'


def test_getwalletfromfile_requires_pk(ton: MyTonCore):
    name = 'w_no_pk'
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    _write_addr_file(addr_path, 'CD' * 32, -1)
    with pytest.raises(Exception):
        ton.GetLocalWallet(name, version='v2')


def test_gethighwalletfromfile(ton: MyTonCore):
    name = 'hw1'
    sub = 777
    addr_hex = 'EF' * 32
    workchain = -1
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}{sub}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, addr_hex, workchain)

    w = ton.GetLocalWallet(name, version='hv1', subwallet=sub)
    assert w.subwallet == sub and w.version == 'hv1'
    assert w.addr.lower() == addr_hex.lower() and w.workchain == workchain
    assert w.addrFilePath.endswith(f'{name}{sub}.addr')
    assert w.bocFilePath.endswith(f'{name}{sub}-query.boc')


def test_getlocalwallet_version(ton: MyTonCore, monkeypatch):
    name = 'w2'
    addr_hex = '11' * 32
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, addr_hex, 0)

    addr_b64 = raw_addr_to_b64(f'0:{addr_hex}')
    versions = ton.GetWalletsVersionList()
    versions[addr_b64] = 'v3r2'

    w = ton.GetLocalWallet(name)
    monkeypatch.setattr(ton, 'GetAccount', lambda a: (_ for _ in ()).throw(Exception('should not be called')))
    assert w.version == 'v3r2'


def test_getlocalwallet_version_from_codehash(ton: MyTonCore, monkeypatch):
    name = 'w_uncached'
    addr_hex = '33' * 32
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, addr_hex, 0)

    addr_b64 = raw_addr_to_b64(f'0:{addr_hex}')
    assert addr_b64 not in ton.GetWalletsVersionList()

    v3r2_hash = '8a6d73bdd8704894f17d8c76ce6139034b8a51b1802907ca36283417798a219b'
    get_account_calls = []

    def fake_get_account(arg):
        get_account_calls.append(arg)
        acc = Account(0, addr_hex)
        acc.status = 'active'
        acc.codeHash = v3r2_hash
        return acc

    monkeypatch.setattr(ton, 'GetAccount', fake_get_account)

    w = ton.GetLocalWallet(name)
    assert w.version == 'v3r2'
    assert get_account_calls == [addr_b64]
    assert ton.GetWalletsVersionList()[addr_b64] == 'v3r2'  # cached for next time


def test_getlocalwallet_version_unknown_codehash(ton: MyTonCore, monkeypatch):
    name = 'w_unknown_hash'
    addr_hex = '44' * 32
    pk_path = os.path.join(ton.walletsDir, f'{name}.pk')
    addr_path = os.path.join(ton.walletsDir, f'{name}.addr')
    open(pk_path, 'wb').close()
    _write_addr_file(addr_path, addr_hex, 0)

    def fake_get_account(arg):
        acc = Account(0, addr_hex)
        acc.status = 'active'
        acc.codeHash = '0' * 64  # unmapped
        return acc

    monkeypatch.setattr(ton, 'GetAccount', fake_get_account)

    w = ton.GetLocalWallet(name)
    assert w.version is None  # warning logged, version stays unset


def test_setwalletversion_and_getwalletsversionlist(ton: MyTonCore):
    versions = ton.GetWalletsVersionList()
    assert isinstance(versions, dict)
    addr_hex = '22' * 32
    addr_b64 = raw_addr_to_b64(f'0:{addr_hex}')

    ton.SetWalletVersion(addr_b64, 'v2r2')
    versions2 = ton.GetWalletsVersionList()
    assert versions2[addr_b64] == 'v2r2'


def test_getversionfromcodehash_mapping(ton: MyTonCore):
    # use known mapping from implementation
    mapping = {
        'v1r1': 'd670136510daff4fee1889b8872c4c1e89872ffa1fe58a23a5f5d99cef8edf32',
        'v1r2': '2705a31a7ac162295c8aed0761cc6e031ab65521dd7b4a14631099e02de99e18',
        'v3r2': '8a6d73bdd8704894f17d8c76ce6139034b8a51b1802907ca36283417798a219b',
    }
    for ver, h in mapping.items():
        assert ton.GetVersionFromCodeHash(h) == ver
    assert ton.GetVersionFromCodeHash('0' * 64) is None


def test_sign_boc_with_wallet(ton: MyTonCore, monkeypatch, tmp_path):
    ton.tempDir = str(tmp_path)
    ton.nodeName = "node_"

    # Patch GetAccount and IsBounceableAddrB64 dynamically per wallet inside loop
    def make_wallet(version, name):
        from mytoncore.models import Wallet
        w = Wallet(0, 'A'*64, name, f"/tmp/{name}", version)
        w.name = name
        w.path = f"/tmp/{name}"
        w.workchain = 0
        return w

    versions = ["v1r1", "v2r1", "v3r2"]
    expected_scripts = {
        "v1r1": "wallet.fif",
        "v2r1": "wallet-v2.fif",
        "v3r2": "wallet-v3.fif",
    }

    for ver in versions:
        wallet = make_wallet(ver, f"w_{ver}")
        wallet_account = Account(0, "A" * 64)
        wallet_account.status = "active"
        wallet_account.balance = 10.0
        dest_account = Account(0, "B" * 64)
        dest_account.status = "active"
        # Balance & dest account patches
        def fake_get_account(arg):
            if arg == wallet.addrB64:
                return wallet_account
            if arg == dest_account.addrB64:
                return dest_account
            raise Exception("unexpected addr")
        monkeypatch.setattr(ton, 'GetAccount', fake_get_account)
        monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda *_: True)
        monkeypatch.setattr(ton, 'get_seqno', lambda *_: 7)
        captured = {}
        def fake_fift_run(args):
            captured['args'] = args
            return f"Some output\nSaved to file {tmp_path}/{wallet.name}-signed.boc)"
        monkeypatch.setattr(ton.fift, 'run', fake_fift_run)
        result = ton.SignBocWithWallet(wallet, "/tmp/input.boc", dest_account.addrB64, 1.0, boc_mode='--init')
        assert result == f"{tmp_path}/{wallet.name}-signed.boc"
        assert captured['args'][0] == expected_scripts[ver]
        assert '--init' in captured['args']
        if 'v3' in ver:
            assert captured['args'][4] == '7'
        else:
            assert captured['args'][3] == '7'


def _setup_sign_boc_wallet(ton, monkeypatch, tmp_path, version, bounceable, dest_status):
    from mytoncore.models import Wallet
    ton.tempDir = str(tmp_path)
    ton.nodeName = "node_"

    wallet = Wallet(0, 'A' * 64, f"w_{version}", f"/tmp/w_{version}", version)
    wallet_account = Account(0, "A" * 64)
    wallet_account.status = "active"
    wallet_account.balance = 10.0
    dest_account = Account(0, "B" * 64)
    dest_account.status = dest_status

    def fake_get_account(arg):
        if arg == wallet.addrB64:
            return wallet_account
        if arg == dest_account.addrB64:
            return dest_account
        raise Exception("unexpected addr")

    monkeypatch.setattr(ton, 'GetAccount', fake_get_account)
    monkeypatch.setattr(ton, 'IsBounceableAddrB64', lambda *_: bounceable)
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: 7)
    return wallet, dest_account


def test_sign_boc_with_wallet_force_bounce(ton: MyTonCore, monkeypatch, tmp_path):
    wallet, dest_account = _setup_sign_boc_wallet(
        ton, monkeypatch, tmp_path, version="v3r2", bounceable=False, dest_status="active"
    )
    captured = {}

    def fake_fift_run(args):
        captured['args'] = args
        return f"Some output\nSaved to file {tmp_path}/{wallet.name}-signed.boc)"

    monkeypatch.setattr(ton.fift, 'run', fake_fift_run)
    ton.SignBocWithWallet(wallet, "/tmp/input.boc", dest_account.addrB64, 1.0)
    assert '--force-bounce' in captured['args']


def test_sign_boc_with_wallet_bounceable_inactive_raises(ton: MyTonCore, monkeypatch, tmp_path):
    wallet, dest_account = _setup_sign_boc_wallet(
        ton, monkeypatch, tmp_path, version="v3r2", bounceable=True, dest_status="uninit"
    )
    monkeypatch.setattr(ton.fift, 'run', lambda args: "should not run")
    with pytest.raises(Exception) as e:
        ton.SignBocWithWallet(wallet, "/tmp/input.boc", dest_account.addrB64, 1.0)
    assert "non-bounceable" in str(e.value)


def test_sign_boc_with_wallet_unsupported_version_raises(ton: MyTonCore, monkeypatch, tmp_path):
    wallet, dest_account = _setup_sign_boc_wallet(
        ton, monkeypatch, tmp_path, version="unknown", bounceable=True, dest_status="active"
    )
    monkeypatch.setattr(ton.fift, 'run', lambda args: "should not run")
    with pytest.raises(Exception) as e:
        ton.SignBocWithWallet(wallet, "/tmp/input.boc", dest_account.addrB64, 1.0)
    assert "not supported" in str(e.value)


def test_send_file(ton: MyTonCore, monkeypatch, mocker, tmp_path):
    file_path = tmp_path / 'msg.boc'
    file_path.write_bytes(b'test')
    from types import SimpleNamespace
    wallet = SimpleNamespace(addrB64='ADDR_W', name='w1', seqno=10)
    commands = []
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: commands.append(cmd))
    wt_mock = mocker.Mock()
    monkeypatch.setattr(ton, 'WaitTransaction', wt_mock)

    ton.SendFile(str(file_path), wallet=wallet, timeout=9, remove=True)
    assert len(commands) >= 1
    assert not file_path.exists()
    wt_mock.assert_called_once_with(wallet, wallet.seqno, 9)


    file_path2 = tmp_path / 'msg2.boc'
    file_path2.write_bytes(b'test2')
    ton.local.db['duplicateApi'] = True
    sent = {}
    monkeypatch.setattr(ton, 'send_boc_toncenter', lambda p: sent.setdefault('boc', p))
    ton.SendFile(str(file_path2), wallet=None, timeout=0, remove=False)
    assert sent['boc'] == str(file_path2)
    assert file_path2.exists()
    assert wt_mock.call_count == 1  # not called again when wallet=None / timeout=0

    with pytest.raises(Exception):
        ton.SendFile(str(tmp_path / 'missing.boc'))


def test_send_boc_toncenter(ton: MyTonCore, monkeypatch, tmp_path):
    boc_path = tmp_path / 'data.boc'
    boc_path.write_bytes(b'BINARY')

    class Resp:
        def __init__(self, status, content=b''):
            self.status_code = status
            self.content = content

    captured = {}
    def fake_post_200(url, json, timeout):
        captured['url'] = url
        captured['json'] = json
        captured['timeout'] = timeout
        return Resp(200)
    def fake_post_500(url, json, timeout):
        captured['url'] = url
        captured['json'] = json
        captured['timeout'] = timeout
        return Resp(500, b'err')
    monkeypatch.setattr('mytoncore.mytoncore.requests.post', fake_post_200)
    assert ton.send_boc_toncenter(str(boc_path)) is True
    assert captured['url'] == 'https://toncenter.com/api/v2/sendBoc'
    assert 'boc' in captured['json']

    ton.local.db['duplicateApiUrl'] = 'TestUrl'
    ton.send_boc_toncenter(str(boc_path))
    assert captured['url'] == 'TestUrl'

    ton.local.db.pop('duplicateApiUrl')
    monkeypatch.setattr(ton, 'GetNetworkName', lambda: 'testnet')
    monkeypatch.setattr('mytoncore.mytoncore.requests.post', fake_post_500)
    assert ton.send_boc_toncenter(str(boc_path)) is False
    assert captured['url'] == 'https://testnet.toncenter.com/api/v2/sendBoc'


def test_wait_transaction(ton: MyTonCore, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('mytoncore.mytoncore.time.sleep', lambda *_: None)

    seqs = [5, 5, 6]
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: seqs.pop(0))
    wallet = SimpleNamespace(addrB64='ADDR1')
    ton.WaitTransaction(wallet, old_seqno=5, timeout=9)  # 3 steps

    # Timeout case
    monkeypatch.setattr(ton, 'get_seqno', lambda *_: 7)
    wallet2 = SimpleNamespace(addrB64='ADDR2')
    with pytest.raises(Exception) as e:
        ton.WaitTransaction(wallet2, old_seqno=7, timeout=6)
    assert 'time out' in str(e.value)


def test_get_returned_stake(ton: MyTonCore, monkeypatch):
    full_elector = '-1:' + 'AA'*32
    monkeypatch.setattr(ton, 'ParseInputAddr', lambda a: (0, 'BBBB'))
    output = '\nstarting VM to run method `compute_returned_stake` (130944) of smart contract -1:3333333333333333333333333333333333333333333333333333333333333333\narguments:  [ 1234 130944 ] \nresult:  [ 1234500000000 ] \n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: output)
    stake = ton.get_returned_stake(full_elector, 'ignored')
    assert stake == 1234.5


def test_get_basechain_config(ton: MyTonCore, monkeypatch):
    testnet_result = 'ConfigParam(12) = (\n  workchains:(hme_root\n    root:(hm_edge\n      label:(hml_same v:0 n:32)\n      node:(hmn_leaf\n        value:(workchain enabled_since:1573821854 monitor_min_split:2 min_split:1 max_split:4 basic:1 active:1 accept_msgs:1 flags:0 zerostate_root_hash:x55B13F6D0E1D0C34C9C2160F6F918E92D82BF9DDCF8DE2E4C94A3FDF39D15446 zerostate_file_hash:xEE0BEDFE4B32761FB35E9E1D8818EA720CAD1A0E7B4D2ED673C488E72E910342 version:0\n          format:(wfmt_basic vm_version:-1 vm_mode:0))))))\n\nx{C_}\n x{D0532EE74ECF01010270002AD89FB6870E861A64E10B07B7C8C7496C15FCEEE7C6F17264A51FEF9CE8AA237705F6FF25993B0FD9AF4F0EC40C753906568D073DA6976B39E24473974881A1000000000FFFFFFFF80000000000000004_}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: testnet_result)
    basechain_config = ton.get_basechain_config()
    print(basechain_config)
    assert basechain_config.enabled_since == 1573821854
    assert basechain_config.min_split == 1
    assert basechain_config.max_split == 4
    assert basechain_config.monitor_min_split == 2

    ton.SetFunctionBuffer('config12', None)

    mainnet_result = 'ConfigParam(12) = (\n  workchains:(hme_root\n    root:(hm_edge\n      label:(hml_same v:0 n:32)\n      node:(hmn_leaf\n        value:(workchain_v2 enabled_since:1573821854 monitor_min_split:0 min_split:0 max_split:4 basic:1 active:1 accept_msgs:1 flags:0 zerostate_root_hash:x55B13F6D0E1D0C34C9C2160F6F918E92D82BF9DDCF8DE2E4C94A3FDF39D15446 zerostate_file_hash:xEE0BEDFE4B32761FB35E9E1D8818EA720CAD1A0E7B4D2ED673C488E72E910342 version:0\n          format:(wfmt_basic vm_version:-1 vm_mode:0)\n          split_merge_timings:(wc_split_merge_timings split_merge_delay:100 split_merge_interval:100 min_split_merge_interval:30 max_split_merge_delay:1000) persistent_state_split_depth:4)))))\nx{C_}\n x{D053AEE74ECF00000270002AD89FB6870E861A64E10B07B7C8C7496C15FCEEE7C6F17264A51FEF9CE8AA237705F6FF25993B0FD9AF4F0EC40C753906568D073DA6976B39E24473974881A1000000000FFFFFFFF8000000000000000000000032000000320000000F000001F4024_}\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: mainnet_result)
    basechain_config = ton.get_basechain_config()
    assert basechain_config.enabled_since == 1573821854
    assert basechain_config.min_split == 0
    assert basechain_config.max_split == 4
    assert basechain_config.monitor_min_split == 0


def test_getconfig(ton: MyTonCore, monkeypatch):
    result = '\nConfigParam(15) = ( validators_elected_for:65536 elections_start_before:32768 elections_end_before:8192 stake_held_for:32768)\nx{00010000000080000000200000008000}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(15)
    assert cfg == {'validators_elected_for': 65536, 'elections_start_before': 32768, 'elections_end_before': 8192, 'stake_held_for': 32768}

    result = '\nConfigParam(8) = (\n  (capabilities version:11 capabilities:494))\n\nx{C40000000B00000000000001EE}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(8)
    assert cfg == {'_': {'_': 'capabilities', 'version': 11, 'capabilities': 494}}

    result = 'ConfigParam(9) = (\n  mandatory_params:(hm_edge\n    label:(hml_same v:0 n:26)\n    node:(hmn_fork\n      left:(hm_edge\n        label:(hml_short\n          len:unary_zero s:x)\n        node:(hmn_fork\n          left:(hm_edge\n            label:(hml_short\n              len:unary_zero s:x)\n            node:(hmn_fork\n              left:(hm_edge\n                label:(hml_same v:0 n:2)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_leaf\n                      value:true))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_leaf\n                      value:true))))\n              right:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:(unary_succ\n                            x:unary_zero) s:xC_)\n                        node:(hmn_leaf\n                          value:true))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:(unary_succ\n                            x:unary_zero) s:x4_)\n                        node:(hmn_leaf\n                          value:true))))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:(unary_succ\n                            x:unary_zero) s:x4_)\n                        node:(hmn_leaf\n                          value:true))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))))))))))\n          right:(hm_edge\n            label:(hml_short\n              len:unary_zero s:x)\n            node:(hmn_fork\n              left:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:(unary_succ\n                            x:unary_zero) s:x4_)\n                        node:(hmn_leaf\n                          value:true))))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:true))))))))\n              right:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:(unary_succ\n                        x:unary_zero) s:x4_)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:true))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:true))))\n                  right:(hm_edge\n                    label:(hml_same v:0 n:2)\n                    node:(hmn_leaf\n                      value:true))))))))\n      right:(hm_edge\n        label:(hml_long n:5 s:x14_)\n        node:(hmn_leaf\n          value:true)))))'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(9)
    assert 'mandatory_params' in cfg
    assert isinstance(cfg['mandatory_params'], dict)

    result = '  ConfigParam(20) = (config_mc_gas_prices\n  (gas_flat_pfx flat_gas_limit:100 flat_gas_price:1000000\n    other:(gas_prices_ext gas_price:655360000 gas_limit:1000000 special_gas_limit:70000000 gas_credit:10000 block_gas_limit:2500000 freeze_due_limit:100000000 delete_due_limit:1000000000)))\n\nx{D1000000000000006400000000000F4240DE000000002710000000000000000F424000000000042C1D80000000000000271000000000002625A00000000005F5E100000000003B9ACA00}\n\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(20)
    assert cfg == {'_': {'_': 'gas_flat_pfx', 'flat_gas_limit': 100, 'flat_gas_price': 1000000, 'other': {'_': 'gas_prices_ext', 'gas_price': 655360000, 'gas_limit': 1000000, 'special_gas_limit': 70000000, 'gas_credit': 10000, 'block_gas_limit': 2500000, 'freeze_due_limit': 100000000, 'delete_due_limit': 1000000000}}}

    value = 'x{01BC53C758DC041462D4D98A17CEA2187EF45174209271E6538CE04C2E3D5C873D}\n x{8017547C8C5C21BA3B8FAE2726D1ED60CFBD711550B5BA79923013531790F0BD4E074B6C878C9BF88531980D6876F3BF82E13F907CB129670DE92E3D3416695893E000100000BB8000003E8}\n x{9FFD5AFB47137BC62F8BF650B00F9CA0F755A6386BFCAA69678830F0BD203EC98D1765645DB798D73D99F07D19960718C92317EFD5D6E6D188E300D8F5755F345AC}\n x{80023F91FCA84DCE1388F1F040A14FC5420A0B66B79BAB0C4856A54BBACA807C4160000000000000000000000000000000000000000000000000000000000000000}\n x{801A97FEA1958FEE5DBA364D0278872D88D7A2F8808713C7E478539AC0A5FE8D631002EA8F918B84374771F5C4E4DA3DAC19F7AE22AA16B74F3246026A62F21E17A9C0D46593342D49ED49648021DD7812E635DADB4BABA598A641B1B50D56471BA4FE_}'
    result = f'ConfigParam(-90) = {value}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(-90)
    assert cfg['_'] == value

    result = '\nConfigParam(-900) = (null)\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config(-900)
    assert cfg == {'_': 'null'}


def test_getrootworkchainsenabledtime(ton: MyTonCore, monkeypatch):
    monkeypatch.setattr(ton, 'get_basechain_config', lambda: WorkchainConfig(enabled_since=12345, monitor_min_split=0, min_split=0, max_split=0))
    enabled_time = ton.get_root_workchain_enabled_time()
    assert enabled_time == 12345


def test_getconfig15(ton: MyTonCore, monkeypatch):
    result = '\nConfigParam(15) = ( validators_elected_for:65536 elections_start_before:32768 elections_end_before:8192 stake_held_for:32768)\nx{00010000000080000000200000008000}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_15()
    assert cfg.validators_elected_for == 65536
    assert cfg.elections_start_before == 32768
    assert cfg.elections_end_before == 8192
    assert cfg.stake_held_for == 32768



def test_getconfig17(ton: MyTonCore, monkeypatch):
    result = 'ConfigParam(17) = (\n  min_stake:(nanograms\n    amount:(var_uint len:6 value:10000000000000))\n  max_stake:(nanograms\n    amount:(var_uint len:7 value:10000000000000000))\n  min_total_stake:(nanograms\n    amount:(var_uint len:6 value:200000000000000)) max_stake_factor:1966080)\n\nx{609184E72A00072386F26FC100006B5E620F48000001E0000}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_17()
    assert cfg.min_stake == 10_000.0
    assert cfg.max_stake == 10_000_000.0
    assert cfg.max_stake_factor == 1_966_080
    assert cfg.min_total_stake == 200_000.0

    ton.SetFunctionBuffer("config17", None)
    result = 'ConfigParam(17) = (\n  min_stake:(nanograms\n    amount:(var_uint len:7 value:300000000000000))\n  max_stake:(nanograms\n    amount:(var_uint len:7 value:10000000000000000))\n  min_total_stake:(nanograms\n    amount:(var_uint len:8 value:75000000000000000)) max_stake_factor:196608)\n\nx{70110D9316EC00072386F26FC100008010A741A4627800000030000}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_17()
    assert cfg.min_stake == 300_000.0
    assert cfg.max_stake == 10_000_000.0
    assert cfg.max_stake_factor == 196_608
    assert cfg.min_total_stake == 75_000_000.0


_VALIDATORS_EXT = 'validators_ext utime_since:1756784978 utime_until:1756799378 total:22 main:15 total_weight:1152921504606846963\n    list:(hme_root\n      root:(hm_edge\n        label:(hml_same v:0 n:11)\n        node:(hmn_fork\n          left:(hm_edge\n            label:(hml_short\n              len:unary_zero s:x)\n            node:(hmn_fork\n              left:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x46AD98CE0D7E345D5669015A75FD835BC8B138682E5E62638284FAA3F536AE42) weight:124039862731926336 adnl_addr:x151CDD00CCA9C3A4A2D7E4FED39DACBF3A0738AF17A892CFF2854DDA5A112718)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xB48347D8C4CAE43443D38209B7431EF96D8ACE91BE8A6221E5212B7F232D30B9) weight:124039862731926336 adnl_addr:x63D851287431C3B28EC2CBF29ADCB05E5135A6FEEE32CDFF96CE99ED6BF7C73C)))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x39F62B968BD7ACB92CCF7494C8AA8848AF1DC7757AEF78DA4E328F602E179D07) weight:124039862731926336 adnl_addr:x9835BBF9637BD12A50B1F5F90DEB4E0C53A95BACE3081C7B7037FA13EAC48A92)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xD08C12162561B2785E717352DE2B38921B7EFD3AE70CB8E4FD8786B80E708A5A) weight:124039862731926336 adnl_addr:x56AB95B527438348FC6E64A9A5D63F012A7B0393CCD6261C9AC7499D9668CA83)))))))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xDE3BA96EA592F890A691D68AB65EED4ABF5A5406446CAF375982B37768567FD6) weight:124039862731926336 adnl_addr:xD41D1269D0035B68A402C2E810FC00591032ED60D15BA9DEFDA3807F81B268E1)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x32D6DE480EA6E614FA511F9D71019B0E1F7ACE64716E31550A0BB8CC9FC62235) weight:124039862731926336 adnl_addr:x255801D2220221957B7E954C908E69DD779D2D7A67882C177B589C238D605E20)))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x61A7DD0C4C2B8DD9C5F170A4CCC6C082C6D221F994D6AE777190A51A2498AE86) weight:124039862731926336 adnl_addr:x794993420B1B72C6F73B26C577FEAF63936B2AABF4548A2C1B7D2C9028C3E681)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xDA229AA39C81414C52EB21FB002B2B8E38A6CD71B6946E06D831C38FAE1C335D) weight:124039821385305426 adnl_addr:xA63F5117B93AF660A7BF990F38241FBAE74E4B8A3E0386F372F03E171DC73217)))))))))\n              right:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xDE8AC477AF70069F93B0E5876CDF30A70C66401496AE53111FD7B5B2FDD1E91C) weight:57885227928278046 adnl_addr:x9FCAAFF3B35DDC22FF4D7EC2EE4DFD2A9913EF79E23F30884CE99C52D7364374)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x42A418FA2F1E8CAE45330D46438A2D2916382024D519DB87646DEE7406BC2B7C) weight:12460072769944933 adnl_addr:xA46E8662F24DEEBC973E21725A0D7832D9D3DD06ED198254E670F9E49F357844)))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x2877F6A9002C682FCA64CCED7F7EC93D591FCABBA774B1102B44AE1A5095362B) weight:10244102642115605 adnl_addr:x6E4E253523B5A3B59811A492E9A0B9461CA6FBF797D4156C198B2F93399080C6)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xBD685EE2C6E7C13F54E29DED42218065A2CA16F8827C3401F7EDCC3EF58CC0FA) weight:8346479657513567 adnl_addr:x523AB850585AA93A7AC45DE8D2E7C3C691ECEDCB483C5859A50297BDA8ADA084)))))))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x94BED6A1D43A5F3AEBDE0CCCA3E140A417201BBFF8288820F0869AA41D55985C) weight:8269373881593689 adnl_addr:x98C8552B9D35CB2FC820086E23B234F6268FF3091B994C8D52E462DE132040C2)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:xE2CB33BC29526191E68320575EB91C1561BA02DE253381DD1DAD911EAC5862C0) weight:8269324182128422 adnl_addr:xD8A5A4F1CA99802D3A280A6185FCC4DD571E416B69A401846F26E4D3AB333BD2)))))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_fork\n                          left:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x46DF027B734BB596B45439E24C31B90CDE318C752702679811BAFF64C67A764F) weight:8269324182128422 adnl_addr:x1F84AAA426CA904EAFEB48F26B038461F55624380783990368B316ABB916432E)))\n                          right:(hm_edge\n                            label:(hml_short\n                              len:unary_zero s:x)\n                            node:(hmn_leaf\n                              value:(validator_addr\n                                public_key:(ed25519_pubkey pubkey:x219FD27A9C4882D8C91CE748873D93AFDF107A70ADF444D5F15B5B16F67F5817) weight:8269324182128422 adnl_addr:x9660710D3D90261A0431FF104DA3760E852AE84C9EADD0280ACB0A4AB1B6E43C)))))))))))\n          right:(hm_edge\n            label:(hml_short\n              len:(unary_succ\n                x:unary_zero) s:x4_)\n            node:(hmn_fork\n              left:(hm_edge\n                label:(hml_short\n                  len:unary_zero s:x)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:(validator_addr\n                            public_key:(ed25519_pubkey pubkey:x0017FECB093AF638CAD0B0BB130B133AEDC12830B136CBFAF84982D8029B6502) weight:8269324182128422 adnl_addr:xA6EA2902ED5CF2246980DA2AFBA907C10EC450D6A6E31A24956A69F8F0E21E2C)))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:(validator_addr\n                            public_key:(ed25519_pubkey pubkey:x22D61B5FC0DDC5F54CC586B23CD03D56A0F6AAD632F25545FE8231BB814865A2) weight:7677793672279361 adnl_addr:x654EF8D2DFF3CA6F13075E70C77E91D164C0360EC951D942D78B3883314C86B2)))))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_fork\n                      left:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:(validator_addr\n                            public_key:(ed25519_pubkey pubkey:x5D6C7818405AD8DC13D3A87A9FE5D727B045D9B8A166B59F8A1E99AF66D22074) weight:7114955125701191 adnl_addr:x60F6ADB0FF08A0BE4B271F02265AAEA111397212BCB3BBA604D93E31DD0CB2D0)))\n                      right:(hm_edge\n                        label:(hml_short\n                          len:unary_zero s:x)\n                        node:(hmn_leaf\n                          value:(validator_addr\n                            public_key:(ed25519_pubkey pubkey:xCE1C47205C8D522A435BC1515E8514D93D787E1C117149F71D8DA948456DC5D6) weight:5692273333090652 adnl_addr:x458AF768CB916259B14561D119BE61D922FD80DBEBCC495C92D69EF723530A64)))))))\n              right:(hm_edge\n                label:(hml_short\n                  len:(unary_succ\n                    x:unary_zero) s:x4_)\n                node:(hmn_fork\n                  left:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_leaf\n                      value:(validator_addr\n                        public_key:(ed25519_pubkey pubkey:xA471BBDD592E71CD372BD3EC616981E0C0FFE9D5B1F774849669366F70848BC1) weight:5113641242815115 adnl_addr:xDD7565355FFCD1C879B84740017F18FA066DCEF6F3DA0A2F4471361C8446930F)))\n                  right:(hm_edge\n                    label:(hml_short\n                      len:unary_zero s:x)\n                    node:(hmn_leaf\n                      value:(validator_addr\n                        public_key:(ed25519_pubkey pubkey:x96718F0822DE60B35FCA345A6419CE109DBEDC8DCEE1DE0E8A091DE414A29132) weight:4721427116211338 adnl_addr:x10C9715D89ABC8D32C490BB5A5788E04EBE5FD193EC11860BBEC5029967C9737))))))))))'


def _test_config(cfg: Config):
    assert cfg.total_validators == 22
    assert cfg.main_validators == 15
    assert cfg.start_work_time == 1756784978
    assert cfg.end_work_time == 1756799378
    assert cfg.total_weight == 1152921504606846963
    assert isinstance(cfg.validators, list) and len(cfg.validators) == 22
    assert cfg.validators[0] == ValidatorConfig(
        adnl_addr="151CDD00CCA9C3A4A2D7E4FED39DACBF3A0738AF17A892CFF2854DDA5A112718", pubkey="46AD98CE0D7E345D5669015A75FD835BC8B138682E5E62638284FAA3F536AE42", weight=124039862731926336)
    assert cfg.validators[21] == ValidatorConfig(
        adnl_addr="10C9715D89ABC8D32C490BB5A5788E04EBE5FD193EC11860BBEC5029967C9737", pubkey="96718F0822DE60B35FCA345A6419CE109DBEDC8DCEE1DE0E8A091DE414A29132", weight=4721427116211338)


def test_getconfig32(ton: MyTonCore, monkeypatch):
    result = f'ConfigParam(32) = (\n  prev_validators:({_VALIDATORS_EXT}))\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_32()
    _test_config(cfg)

    result = f'ConfigParam(32) = (null)\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg_new = ton.get_config_32()
    assert cfg_new == cfg

    ton.SetFunctionBuffer("typed_config32", None)
    with pytest.raises(Exception):
        ton.get_config_32()


def test_getconfig34(ton: MyTonCore, monkeypatch):
    result = f'ConfigParam(34) = (\n  cur_validators:({_VALIDATORS_EXT}))\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_34()
    _test_config(cfg)

    result = f'ConfigParam(34) = (null)\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg_new = ton.get_config_34()
    assert cfg_new == cfg

    ton.SetFunctionBuffer("typed_config34", None)
    with pytest.raises(Exception):
        ton.get_config_34()

def test_getconfig36(ton: MyTonCore, monkeypatch):
    result = f'ConfigParam(36) = (\n  next_validators:({_VALIDATORS_EXT}))\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_36()
    _test_config(cfg)

    result = f'ConfigParam(36) = (null)\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: result)
    cfg = ton.get_config_36()
    assert cfg is None
