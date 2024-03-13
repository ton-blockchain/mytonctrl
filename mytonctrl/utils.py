import time


def timestamp2utcdatetime(timestamp, format="%d.%m.%Y %H:%M:%S"):
    datetime = time.gmtime(timestamp)
    result = time.strftime(format, datetime) + ' UTC'
    return result


def GetItemFromList(data, index):
    try:
        return data[index]
    except:
        pass
