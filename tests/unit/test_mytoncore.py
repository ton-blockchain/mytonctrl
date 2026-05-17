import os
import struct
import types

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
    testnet_result = 'ConfigParam(12) = (\n  workchains:(hme_root\n    root:(hm_edge\n      label:(hml_same v:0 n:32)\n      node:(hmn_leaf\n        value:(workchain enabled_since:1573821854 monitor_min_split:2 min_split:2 max_split:4 basic:1 active:1 accept_msgs:1 flags:0 zerostate_root_hash:x55B13F6D0E1D0C34C9C2160F6F918E92D82BF9DDCF8DE2E4C94A3FDF39D15446 zerostate_file_hash:xEE0BEDFE4B32761FB35E9E1D8818EA720CAD1A0E7B4D2ED673C488E72E910342 version:0\n          format:(wfmt_basic vm_version:-1 vm_mode:0))))))\n\nx{C_}\n x{D0532EE74ECF01010270002AD89FB6870E861A64E10B07B7C8C7496C15FCEEE7C6F17264A51FEF9CE8AA237705F6FF25993B0FD9AF4F0EC40C753906568D073DA6976B39E24473974881A1000000000FFFFFFFF80000000000000004_}'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: testnet_result)
    basechain_config = ton.get_basechain_config()
    print(basechain_config)
    assert basechain_config["enabled_since"] == 1573821854
    assert basechain_config["min_split"] == 2
    assert basechain_config["max_split"] == 4
    assert basechain_config["monitor_min_split"] == 2

    ton.SetFunctionBuffer('config12', None)

    mainnet_result = 'ConfigParam(12) = (\n  workchains:(hme_root\n    root:(hm_edge\n      label:(hml_same v:0 n:32)\n      node:(hmn_leaf\n        value:(workchain_v2 enabled_since:1573821854 monitor_min_split:0 min_split:0 max_split:4 basic:1 active:1 accept_msgs:1 flags:0 zerostate_root_hash:x55B13F6D0E1D0C34C9C2160F6F918E92D82BF9DDCF8DE2E4C94A3FDF39D15446 zerostate_file_hash:xEE0BEDFE4B32761FB35E9E1D8818EA720CAD1A0E7B4D2ED673C488E72E910342 version:0\n          format:(wfmt_basic vm_version:-1 vm_mode:0)\n          split_merge_timings:(wc_split_merge_timings split_merge_delay:100 split_merge_interval:100 min_split_merge_interval:30 max_split_merge_delay:1000) persistent_state_split_depth:4)))))\nx{C_}\n x{D053AEE74ECF00000270002AD89FB6870E861A64E10B07B7C8C7496C15FCEEE7C6F17264A51FEF9CE8AA237705F6FF25993B0FD9AF4F0EC40C753906568D073DA6976B39E24473974881A1000000000FFFFFFFF8000000000000000000000032000000320000000F000001F4024_}\n'
    monkeypatch.setattr(ton.liteClient, 'run', lambda cmd, **kw: mainnet_result)
    basechain_config = ton.get_basechain_config()
    assert basechain_config["enabled_since"] == 1573821854
    assert basechain_config["min_split"] == 0
    assert basechain_config["max_split"] == 4
    assert basechain_config["monitor_min_split"] == 0
