
class MyTonCoreException(Exception):
    pass


class BalanceIsTooLow(MyTonCoreException):
    pass


class WalletAccountNotInitialized(MyTonCoreException):
    pass
