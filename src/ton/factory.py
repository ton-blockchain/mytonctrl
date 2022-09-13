import mytoncore


def get_ton_controller() -> mytoncore.MyTonCore:
    ton = mytoncore.MyTonCore()
    ton.Init()
    return ton
