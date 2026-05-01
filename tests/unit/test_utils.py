from mytoncore.utils import raw_addr_to_b64


def test_raw_addr_to_b64():
    a = '0:0000000000000000000000000000000000000000000000000000000000000000'
    assert raw_addr_to_b64(a) == 'EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c'
    assert raw_addr_to_b64(a, bounceable=False) == 'UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJKZ'
    assert raw_addr_to_b64(a, is_testnet=True) == 'kQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHTW'
    assert raw_addr_to_b64(a, is_testnet=True, bounceable=False) == '0QAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACkT'

    a = '0:9dd5ec3ec8a3233ab56b22457ef8b0540d59fb5567fe84c4d548eda03c2e8535'
    assert raw_addr_to_b64(a) == 'EQCd1ew-yKMjOrVrIkV--LBUDVn7VWf-hMTVSO2gPC6FNYNB'
    assert raw_addr_to_b64(a, bounceable=False) == 'UQCd1ew-yKMjOrVrIkV--LBUDVn7VWf-hMTVSO2gPC6FNd6E'
    assert raw_addr_to_b64(a, is_testnet=True) == 'kQCd1ew-yKMjOrVrIkV--LBUDVn7VWf-hMTVSO2gPC6FNTjL'
    assert raw_addr_to_b64(a, is_testnet=True, bounceable=False) == '0QCd1ew-yKMjOrVrIkV--LBUDVn7VWf-hMTVSO2gPC6FNWUO'

    a = '-1:3333333333333333333333333333333333333333333333333333333333333333'
    assert raw_addr_to_b64(a) == 'Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF'
    assert raw_addr_to_b64(a, bounceable=False) == 'Uf8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMxYA'
    assert raw_addr_to_b64(a, is_testnet=True) == 'kf8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM_BP'
    assert raw_addr_to_b64(a, is_testnet=True, bounceable=False) == '0f8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM62K'
