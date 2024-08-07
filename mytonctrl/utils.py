import subprocess
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


def fix_git_config(git_path: str):
    args = ["git", "status"]
    try:
        process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=git_path, timeout=3)
        err = process.stderr.decode("utf-8")
    except Exception as e:
        err = str(e)
    if err:
        if 'git config --global --add safe.directory' in err:
            args = ["git", "config", "--global", "--add", "safe.directory", git_path]
            subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        else:
            raise Exception(f'Failed to check git status: {err}')
#end define
