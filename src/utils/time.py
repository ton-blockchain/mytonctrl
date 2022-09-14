from datetime import datetime, timedelta


def format_timestamp_as_delta(timestamp: float) -> str:
    return str(timedelta(seconds=timestamp))


def format_timestamp_as_date(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')
