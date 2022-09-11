#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import sys
import time
import json
import zlib
import copy
import base64
import psutil
import struct
import socket
import hashlib
import platform
import threading
import subprocess
import datetime as DateTimeLibrary
from urllib.request import urlopen
from urllib.error import URLError
from shutil import copyfile

import re 

# self.buffer
_myName = "myName"
_myDir = "myDir"
_myFullName = "myFullName"
_myPath = "myPath"
_myWorkDir = "myWorkDir"
_myTempDir = "myTempDir"
_logFileName = "logFileName"
_localdbFileName = "localdbFileName"
_pidFilePath = "pidFilePath"
_logList = "logList"
_memoryUsing = "memoryUsing"
_freeSpaceMemory = "freeSpaceMemory"
_threadCount = "threadCount"
_threadCountOld = "threadCountOld"

# self.db
_config = "config"

# self.db.config
_logLevel = "logLevel"
_isLimitLogFile = "isLimitLogFile"
_isDeleteOldLogFile = "isDeleteOldLogFile"
_isIgnorLogWarning = "isIgnorLogWarning"
_isStartOnlyOneProcess = "isStartOnlyOneProcess"
_memoryUsinglimit = "memoryUsinglimit"
_isLocaldbSaving = "isLocaldbSaving"
_isWritingLogFile = "isWritingLogFile"
_programFiles = "programFiles"
INFO = "info"
WARNING = "warning"
ERROR = "error"
DEBUG = "debug"

class gcolors:
	'''This class is designed to display text in color format'''
	red = "\033[41m"
	green = "\033[42m"
	yellow = "\033[43m"
	blue = "\033[44m"
	magenta = "\033[45m"
	cyan = "\033[46m"
	endc = "\033[0m"
	default = "\033[49m"
#end class

class bcolors:
	'''This class is designed to display text in color format'''
	red = "\033[31m"
	green = "\033[32m"
	yellow = "\033[33m"
	blue = "\033[34m"
	magenta = "\033[35m"
	cyan = "\033[36m"
	endc = "\033[0m"
	bold = "\033[1m"
	underline = "\033[4m"
	default = "\033[39m"

	DEBUG = magenta
	INFO = blue
	OKGREEN = green
	WARNING = yellow
	ERROR = red
	ENDC = endc
	BOLD = bold
	UNDERLINE = underline
	
	def GetArgs(*args):
		text = ""
		for item in args:
			if item is None:
				continue
			text += str(item)
		return text
	#end define

	def Magenta(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.magenta + text + bcolors.endc
		return text
	#end define

	def Blue(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.blue + text + bcolors.endc
		return text
	#end define

	def Green(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.green + text + bcolors.endc
		return text
	#end define

	def Yellow(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.yellow + text + bcolors.endc
		return text
	#end define

	def Red(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.red + text + bcolors.endc
		return text
	#end define

	def Bold(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.bold + text + bcolors.endc
		return text
	#end define

	def Underline(*args):
		text = bcolors.GetArgs(*args)
		text = bcolors.underline + text + bcolors.endc
		return text
	#end define

	colors = {"red": red, "green": green, "yellow": yellow, "blue": blue, "magenta": magenta, "cyan": cyan, "endc": endc, "bold": bold, "underline": underline}
#end class

class MyPyClass:
	def __init__(self, file):
		self.file = file
		self.db = dict()
		self.db[_config] = dict()

		self.buffer = dict()
		self.buffer[_logList] = list()
		self.buffer[_threadCount] = None
		self.buffer[_memoryUsing] = None
		self.buffer[_freeSpaceMemory] = None

		# Set default settings
		self.SetDefaultConfig()
		self.Refresh()
	#end define

	def Refresh(self):
		# Get program, log and database file name
		myName = self.GetMyName()
		myWorkDir = self.GetMyWorkDir()
		self.buffer[_myName] = myName
		self.buffer[_myDir] = self.GetMyDir()
		self.buffer[_myFullName] = self.GetMyFullName()
		self.buffer[_myPath] = self.GetMyPath()
		self.buffer[_myWorkDir] = myWorkDir
		self.buffer[_myTempDir] = self.GetMyTempDir()
		self.buffer[_logFileName] = myWorkDir + myName + ".log"
		self.buffer[_localdbFileName] = myWorkDir + myName + ".db"
		self.buffer[_pidFilePath] = myWorkDir + myName + ".pid"

		# Check all directorys
		os.makedirs(self.buffer[_myWorkDir], exist_ok=True)
		os.makedirs(self.buffer[_myTempDir], exist_ok=True)
	#end define

	def Run(self):
		# Check args
		if ("-ef" in sys.argv):
			file = open(os.devnull, 'w')
			sys.stdout = file
			sys.stderr = file
		if ("-d" in sys.argv):
			self.ForkDaemon()
		if ("-s" in sys.argv):
			x = sys.argv.index("-s")
			filePath = sys.argv[x+1]
			self.GetSettings(filePath)
		if ("--add2cron" in sys.argv):
			self.AddToCrone()

		# Start only one process (exit if process exist)
		if self.db.get(_config).get(_isStartOnlyOneProcess):
			self.StartOnlyOneProcess()

		# Load local database
		self.dbLoad()

		# Remove old log file
		if (self.db.get(_config).get(_isDeleteOldLogFile) and os.path.isfile(self.buffer[_logFileName])):
			os.remove(self.buffer[_logFileName])
		
		# Start other threads
		threading.Thread(target=self.WritingLogFile, name="Logging", daemon=True).start()
		threading.Thread(target=self.SelfTesting, name="SelfTesting", daemon=True).start()
		threading.Thread(target=self.LocaldbSaving, name="LocdbSaving", daemon=True).start()
		self.buffer[_threadCountOld] = threading.active_count()

		# Logging the start of the program
		self.AddLog("Start program '{0}'".format(self.buffer[_myPath]))
	#end define

	def SetDefaultConfig(self):
		if _logLevel not in self.db[_config]:
			self.db[_config][_logLevel] = INFO # info || debug
		if _isLimitLogFile not in self.db[_config]:
			self.db[_config][_isLimitLogFile] = True
		if _isDeleteOldLogFile not in self.db[_config]:
			self.db[_config][_isDeleteOldLogFile] = False
		if _isIgnorLogWarning not in self.db[_config]:
			self.db[_config][_isIgnorLogWarning] = False
		if _isStartOnlyOneProcess not in self.db[_config]:
			self.db[_config][_isStartOnlyOneProcess] = True
		if _memoryUsinglimit not in self.db[_config]:
			self.db[_config][_memoryUsinglimit] = 50
		if _isLocaldbSaving not in self.db[_config]:
			self.db[_config][_isLocaldbSaving] = False
		if _isWritingLogFile not in self.db[_config]:
			self.db[_config][_isWritingLogFile] = True
	#end define

	def StartOnlyOneProcess(self):
		pidFilePath = self.buffer[_pidFilePath]
		if os.path.isfile(pidFilePath):
			file = open(pidFilePath, 'r')
			pid_str = file.read()
			file.close()
			try:
				pid = int(pid_str)
				process = psutil.Process(pid)
				fullProcessName = " ".join(process.cmdline())
			except:
				fullProcessName = ""
			if (fullProcessName.find(self.buffer[_myFullName]) > -1):
				print("The process is already running")
				sys.exit(1)
			#end if
		self.WritePid()
	#end define

	def WritePid(self):
		pid = os.getpid()
		pid_str = str(pid)
		pidFilePath = self.buffer[_pidFilePath]
		with open(pidFilePath, 'w') as file:
			file.write(pid_str)
	#end define

	def SelfTesting(self):
		self.AddLog("Start SelfTesting thread.", DEBUG)
		while True:
			try:
				time.sleep(1)
				self.SelfTest()
			except Exception as err:
				self.AddLog("SelfTesting: {0}".format(err), ERROR)
	#end define

	def SelfTest(self):
		process = psutil.Process(os.getpid())
		memoryUsing = b2mb(process.memory_info().rss)
		freeSpaceMemory = b2mb(psutil.virtual_memory().available)
		threadCount = threading.active_count()
		self.buffer[_freeSpaceMemory] = freeSpaceMemory
		self.buffer[_memoryUsing] = memoryUsing
		self.buffer[_threadCount] = threadCount
		if memoryUsing > self.db[_config][_memoryUsinglimit]:
			self.db[_config][_memoryUsinglimit] += 50
			self.AddLog("Memory using: {0}Mb, free: {1}Mb".format(memoryUsing, freeSpaceMemory), WARNING)
	#end define

	def PrintSelfTestingResult(self):
		threadCount_old = self.buffer[_threadCountOld]
		threadCount_new = self.buffer[_threadCount]
		memoryUsing = self.buffer[_memoryUsing]
		freeSpaceMemory = self.buffer[_freeSpaceMemory]
		self.AddLog("{0}Self testing informatinon:{1}".format(bcolors.INFO, bcolors.ENDC))
		self.AddLog("Threads: {0} -> {1}".format(threadCount_new, threadCount_old))
		self.AddLog("Memory using: {0}Mb, free: {1}Mb".format(memoryUsing, freeSpaceMemory))
	#end define

	def GetThreadName(self):
		return threading.currentThread().getName()
	#end define

	def GetMyFullName(self):
		'''return "test.py"'''
		myPath = self.GetMyPath()
		myFullName = GetFullNameFromPath(myPath)
		if len(myFullName) == 0:
			myFullName = "empty"
		return myFullName
	#end define

	def GetMyName(self):
		'''return "test"'''
		myFullName = self.GetMyFullName()
		myName = myFullName[:myFullName.rfind('.')]
		return myName
	#end define

	def GetMyPath(self):
		'''return "/some_dir/test.py"'''
		myPath = os.path.abspath(self.file)
		return myPath
	#end define

	def GetMyDir(self):
		'''return "/some_dir/"'''
		myPath = self.GetMyPath()
		# myDir = myPath[:myPath.rfind('/')+1]
		myDir = os.path.dirname(myPath)
		myDir = dir(myDir)
		return myDir
	#end define

	def GetMyWorkDir(self):
		'''return "/usr/local/bin/test/" or "/home/user/.local/share/test/"'''
		if self.CheckRootPermission():
			# https://ru.wikipedia.org/wiki/FHS
			programFilesDir = "/usr/local/bin/"
		else:
			# https://habr.com/ru/post/440620/
			userHomeDir = dir(os.getenv("HOME"))
			programFilesDir = dir(os.getenv("XDG_DATA_HOME", userHomeDir + ".local/share/"))
		myName = self.GetMyName()
		myWorkDir = dir(programFilesDir + myName)
		return myWorkDir
	#end define

	def GetMyTempDir(self):
		'''return "/tmp/test/"'''
		tempFilesDir = "/tmp/" # https://ru.wikipedia.org/wiki/FHS
		myName = self.GetMyName()
		myTempDir = dir(tempFilesDir + myName)
		return myTempDir
	#end define

	def GetLang(self):
		lang = os.getenv("LANG", "en")
		if "ru" in lang:
			lang = "ru"
		else:
			lang = "en"
		return lang
	#end define

	def CheckRootPermission(self):
		process = subprocess.run(["touch", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		if (process.returncode == 0):
			subprocess.run(["rm", "/checkpermission"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
			result = True
		else:
			result = False
		return result
	#end define

	def AddLog(self, inputText, mode=INFO):
		inputText = "{0}".format(inputText)
		timeText = DateTimeLibrary.datetime.utcnow().strftime("%d.%m.%Y, %H:%M:%S.%f")[:-3]
		timeText = "{0} (UTC)".format(timeText).ljust(32, ' ')

		# Pass if set log level
		if self.db[_config][_logLevel] != DEBUG and mode == DEBUG:
			return
		elif self.db[_config][_isIgnorLogWarning] and mode == WARNING:
			return

		# Set color mode
		if mode == INFO:
			colorStart = bcolors.INFO + bcolors.BOLD
		elif mode == WARNING:
			colorStart = bcolors.WARNING + bcolors.BOLD
		elif mode == ERROR:
			colorStart = bcolors.ERROR + bcolors.BOLD
		elif mode == DEBUG:
			colorStart = bcolors.DEBUG + bcolors.BOLD
		else:
			colorStart = bcolors.UNDERLINE + bcolors.BOLD
		modeText = "{0}{1}{2}".format(colorStart, "[{0}]".format(mode).ljust(10, ' '), bcolors.ENDC)

		# Set color thread
		if mode == ERROR:
			colorStart = bcolors.ERROR + bcolors.BOLD
		else:
			colorStart = bcolors.OKGREEN + bcolors.BOLD
		threadText = "{0}{1}{2}".format(colorStart, "<{0}>".format(self.GetThreadName()).ljust(14, ' '), bcolors.ENDC)
		logText = modeText + timeText + threadText + inputText

		# Queue for recording
		self.buffer[_logList].append(logText)

		# Print log text
		print(logText)
	#end define

	def WritingLogFile(self):
		if self.db[_config][_isWritingLogFile] == False:
			return
		self.AddLog("Start WritingLogFile thread.", DEBUG)
		while True:
			time.sleep(1)
			self.TryWriteLogFile()
	#end define

	def TryWriteLogFile(self):
		try:
			self.WriteLogFile()
		except Exception as err:
			self.AddLog("TryWriteLogFile: {0}".format(err), ERROR)
	#end define

	def WriteLogFile(self):
		logFileName = self.buffer[_logFileName]

		with open(logFileName, 'a') as file:
			while len(self.buffer[_logList]) > 0:
				logText = self.buffer[_logList].pop(0)
				file.write(logText + '\n')
			#end while
		#end with

		# Control log size
		if self.db[_config][_isLimitLogFile] == False:
			return
		allline = self.CountLines(logFileName)
		if allline > 4096 + 256:
			delline = allline - 4096
			f=open(logFileName).readlines()
			i = 0
			while i < delline:
				f.pop(0)
				i = i + 1
			with open(logFileName,'w') as F:
				F.writelines(f)
	#end define

	def CountLines(self, filename, chunk_size=1<<13):
		if not os.path.isfile(filename):
			return 0
		with open(filename) as file:
			return sum(chunk.count('\n')
				for chunk in iter(lambda: file.read(chunk_size), ''))
	#end define

	def DictToBase64WithCompress(self, item):
		string = json.dumps(item)
		original = string.encode("utf-8")
		compressed = zlib.compress(original)
		b64 = base64.b64encode(compressed)
		data = b64.decode("utf-8")
		return data
	#end define

	def Base64ToDictWithDecompress(self, item):
		data = item.encode("utf-8")
		b64 = base64.b64decode(data)
		decompress = zlib.decompress(b64)
		original = decompress.decode("utf-8")
		data = json.loads(original)
		return data
	#end define

	def Exit(self):
		if len(self.buffer[_logList]) > 0:
			time.sleep(1.1)
		if os.path.isfile(self.buffer[_pidFilePath]):
			os.remove(self.buffer[_pidFilePath])
		sys.exit(0)
	#end define

	def LocaldbSaving(self):
		if self.db[_config][_isLocaldbSaving] == False:
			return
		self.AddLog("Start LocaldbSaving thread.", DEBUG)
		while True:
			time.sleep(10) # 10 sec
			threading.Thread(target=self.dbSave).start()
	#end define

	def TryLocaldbSave(self):
		try:
			self.dbSave()
		except Exception as err:
			self.AddLog("TryLocaldbSave: {0}".format(err), ERROR)
	#end define

	def dbSave(self):
		fileName = self.buffer[_localdbFileName]
		if "oldDb" in self.buffer:
			try:
				file = open(fileName, 'r')
				buffString = file.read()
				file.close()
				
				oldDb = self.buffer.get("oldDb")
				buffData = json.loads(buffString)
				for name, value in buffData.items():
					oldValue = oldDb.get(name)
					if oldValue != value:
						self.db[name] = value
				#end for
			except:
				pass
		with open(fileName, 'w') as file:
			self.buffer["oldDb"] = copy.deepcopy(self.db)
			string = json.dumps(self.db, indent=4)
			file.write(string)
	#end define

	def dbLoad(self, fileName=False):
		result = False
		if not fileName:
			fileName = self.buffer[_localdbFileName]
		try:
			file = open(fileName, 'r')
			original = file.read()
			file.close()
			arr = json.loads(original)
			self.db.update(arr)
			self.SetDefaultConfig()
			result = True
		except Exception as err:
			self.AddLog("dbLoad: {0}".format(err), WARNING)
		return result
	#end define

	def GetSettings(self, filePath):
		try:
			file = open(filePath)
			text = file.read()
			file.close()
			self.db = json.loads(text)
			self.dbSave()
			print("get setting successful: " + filePath)
			self.Exit()
		except Exception as err:
			self.AddLog("GetSettings: {0}".format(err), WARNING)
	#end define
	
	def ForkDaemon(self):
		myPath = self.buffer[_myPath]
		cmd = " ".join(["/usr/bin/python3", myPath, "-ef", '&'])
		os.system(cmd)
		print("daemon start: " + myPath)
		self.Exit()
	#end define

	def AddToCrone(self):
		cronText="@reboot /usr/bin/python3 \"{path}\" -d\n".format(path=self.buffer[_myPath])
		os.system("crontab -l > mycron")
		with open("mycron", 'a') as file:
			file.write(cronText)
		os.system("crontab mycron && rm mycron")
		print("add to cron successful: " + cronText)
		self.Exit()
	#end define

	def TryFunction(self, func, **kwargs):
		args = kwargs.get("args")
		result = None
		try:
			if args is None:
				result = func()
			else:
				result = func(*args)
		except Exception as err:
			text = "{funcName} error: {err}".format(funcName=func.__name__, err=err)
			self.AddLog(text, "error")
		return result
	#end define

	def StartThread(self, func, **kwargs):
		name = kwargs.get("name", func.__name__)
		args = kwargs.get("args")
		if args is None:
			threading.Thread(target=func, name=name, daemon=True).start()
		else:
			threading.Thread(target=func, name=name, args=args, daemon=True).start()
		self.AddLog("Thread {name} started".format(name=name), "debug")
	#end define

	def Cycle(self, func, sec, args):
		while True:
			self.TryFunction(func, args=args)
			time.sleep(sec)
	#end define

	def StartCycle(self, func, **kwargs):
		name = kwargs.get("name", func.__name__)
		args = kwargs.get("args")
		sec = kwargs.get("sec")
		self.StartThread(self.Cycle, name=name, args=(func, sec, args))
	#end define

	def InitTranslator(self, filePath=None):
		if filePath is None:
			filePath = self.db.get("translateFilePath")
		file = open(filePath, encoding="utf-8")
		text = file.read()
		file.close()
		self.buffer["translate"] = json.loads(text)
	#end define

	def Translate(self, text):
		lang = self.GetLang()
		translate = self.buffer.get("translate")
		textList = text.split(' ')
		for item in textList:
			sitem = translate.get(item)
			if sitem is None:
				continue
			ritem = sitem.get(lang)
			if ritem is not None:
				text = text.replace(item, ritem)
		return text
	#end define
#end class

def GetHashMd5(fileName):
	BLOCKSIZE = 65536
	hasher = hashlib.md5()
	with open(fileName, 'rb') as file:
		buf = file.read(BLOCKSIZE)
		while len(buf) > 0:
			hasher.update(buf)
			buf = file.read(BLOCKSIZE)
	return(hasher.hexdigest())
#end define

def Pars(text, search, search2=None):
	if search is None or text is None:
		return None
	if search not in text:
		return None
	text = text[text.find(search) + len(search):]
	if search2 is not None and search2 in text:
		text = text[:text.find(search2)]
	return text
#end define

def Ping(hostname):
	process = subprocess.run(["ping", "-c", 1, "-w", 3, hostname], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	if process.returncode == 0:
		result = True
	else:
		result = False
	return result
#end define

def GetRequest(url):
	link = urlopen(url)
	data = link.read()
	text = data.decode("utf-8")
	return text
#end define

def dir(inputDir):
	if (inputDir[-1:] != '/'):
		inputDir += '/'
	return inputDir
#end define

def b2mb(item):
	return round(int(item)/1000/1000, 2)
#end define

def SearchFileInDir(path, fileName):
	result = None
	for entry in os.scandir(path):
		if entry.name.startswith('.'):
			continue
		if entry.is_dir():
			buff = SearchFileInDir(entry.path, fileName)
			if buff is not None:
				result = buff
				break
		elif entry.is_file():
			if entry.name == fileName:
				result = entry.path
				break
	return result
#end define

def SearchDirInDir(path, dirName):
	result = None
	for entry in os.scandir(path):
		if entry.name.startswith('.'):
			continue
		if entry.is_dir():
			if entry.name == dirName:
				result = entry.path
				break
			buff = SearchDirInDir(entry.path, dirName)
			if buff is not None:
				result = buff
				break
	return result
#end define

def GetDirFromPath(path):
	return path[:path.rfind('/')+1]
#end define

def GetFullNameFromPath(path):
	return path[path.rfind('/')+1:]
#end define

def PrintTable(arr):
	buff = dict()
	for i in range(len(arr[0])):
		buff[i] = list()
		for item in arr:
			buff[i].append(len(str(item[i])))
	for item in arr:
		for i in range(len(arr[0])):
			index = max(buff[i]) + 2
			ptext = str(item[i]).ljust(index)
			if item == arr[0]:
				ptext = bcolors.Blue(ptext)
				ptext = bcolors.Bold(ptext)
			print(ptext, end = '')
		print()
#end define

def GetTimestamp():
	return int(time.time())
#end define

def ColorText(text):
	for cname in bcolors.colors:
		item = '{' + cname + '}'
		if item in text:
			text = text.replace(item, bcolors.colors[cname])
	return text
#end define

def ColorPrint(text):
	text = ColorText(text)
	print(text)
#end define

def GetLoadAvg():
	if platform.system() in ['FreeBSD','Darwin']:
		loadavg = subprocess.check_output(["sysctl", "-n", "vm.loadavg"]).decode('utf-8')
		m = re.match(r"{ (\d+\.\d+) (\d+\.\d+) (\d+\.\d+).+", loadavg)
		if m:
			loadavg_arr = [m.group(1), m.group(2), m.group(3)];
		else:
			loadavg_arr = [0.00,0.00,0.00]
	else:
		file = open("/proc/loadavg")
		loadavg = file.read()
		file.close()
		loadavg_arr = loadavg.split(' ')

	output = loadavg_arr[:3]
	for i in range(len(output)):
		output[i] = float(output[i])
	return output
#end define

def GetInternetInterfaceName():
	cmd = "ip --json route"
	text = subprocess.getoutput(cmd)
	try:
		arr = json.loads(text)
		interfaceName = arr[0]["dev"]
	except:
		lines = text.split('\n')
		items = lines[0].split(' ')
		buff = items.index("dev")
		interfaceName = items[buff+1]
	return interfaceName
#end define

def Sleep():
	while True:
		time.sleep(10)
#end define

def Timestamp2Datetime(timestamp, format="%d.%m.%Y %H:%M:%S"):
	datetime = time.localtime(timestamp)
	result = time.strftime(format, datetime)
	return result
#end define

def timeago(timestamp=False):
	"""
	Get a datetime object or a int() Epoch timestamp and return a
	pretty string like 'an hour ago', 'Yesterday', '3 months ago',
	'just now', etc
	"""
	now = DateTimeLibrary.datetime.now()
	if type(timestamp) is int:
		diff = now - DateTimeLibrary.datetime.fromtimestamp(timestamp)
	elif isinstance(timestamp, DateTimeLibrary.datetime):
		diff = now - timestamp
	elif not timestamp:
		diff = now - now
	second_diff = diff.seconds
	day_diff = diff.days

	if day_diff < 0:
		return ''

	if day_diff == 0:
		if second_diff < 10:
			return "just now"
		if second_diff < 60:
			return str(second_diff) + " seconds ago"
		if second_diff < 120:
			return "a minute ago"
		if second_diff < 3600:
			return str(second_diff // 60) + " minutes ago"
		if second_diff < 7200:
			return "an hour ago"
		if second_diff < 86400:
			return str(second_diff // 3600) + " hours ago"
	if day_diff < 31:
		return str(day_diff) + " days ago"
	if day_diff < 365:
		return str(day_diff // 30) + " months ago"
	return str(day_diff // 365) + " years ago"
#end define

def time2human(diff):
	dt = DateTimeLibrary.timedelta(seconds=diff)
	if dt.days < 0:
		return ''

	if dt.days == 0:
		if dt.seconds < 60:
			return str(dt.seconds) + " seconds"
		if dt.seconds < 3600:
			return str(dt.seconds // 60) + " minutes"
		if dt.seconds < 86400:
			return str(dt.seconds // 3600) + " hours"
	return str(dt.days) + " days"
#end define

def dec2hex(dec):
	h = hex(dec)[2:]
	if len(h) % 2 > 0:
		h = '0' + h
	return h
#end define

def RunAsRoot(args):
	text = platform.version()
	if "Ubuntu" in text:
		args = ["sudo", "-s"] + args
	else:
		print("Enter root password")
		args = ["su", "-c"] + [" ".join(args)]
	exitCode = subprocess.call(args)
	return exitCode
#end define

def Add2Systemd(**kwargs):
	name = kwargs.get("name")
	start = kwargs.get("start")
	post = kwargs.get("post", "/bin/echo service down")
	user = kwargs.get("user", "root")
	group = kwargs.get("group", user)
	path = "/etc/systemd/system/{name}.service".format(name=name)
	
	if name is None or start is None:
		raise Exception("Bad args. Need 'name' and 'start'.")
		return
	if os.path.isfile(path):
		print(f"Unit exist: {path}")
		return
	# end if
	
	text = """
[Unit]
Description = {name} service. Created by https://github.com/igroman787/mypylib.
After = network.target

[Service]
Type = simple
Restart = always
RestartSec = 30
ExecStart = {ExecStart}
ExecStopPost = {ExecStopPost}
User = {User}
Group = {Group}
LimitNOFILE = infinity
LimitNPROC = infinity
LimitMEMLOCK = infinity

[Install]
WantedBy = multi-user.target
	""".format(name=name, ExecStart=start, ExecStopPost=post, User=user, Group=group)
	file = open(path, 'wt')
	file.write(text)
	file.close()
	
	# Изменить права
	args = ["chmod", "664", path]
	subprocess.run(args)
	
	# Разрешить запуск
	args = ["chmod", "+x", path]
	subprocess.run(args)
	
	# Перезапустить systemd
	args = ["systemctl", "daemon-reload"]
	subprocess.run(args)
	
	# Включить автозапуск
	args = ["systemctl", "enable", name]
	subprocess.run(args)
#end define

def ip2int(addr):
	return struct.unpack("!i", socket.inet_aton(addr))[0]
#end define

def GetServiceStatus(name):
	status = False
	result = os.system("systemctl is-active --quiet {name}".format(name=name))
	if result == 0:
		status = True
	return status
#end define

def GetServiceUptime(name):
	property = "ExecMainStartTimestampMonotonic"
	args = ["systemctl", "show", name, "--property=" + property]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	startTimestampMonotonic = Pars(output, f"{property}=", '\n')
	startTimestampMonotonic = int(startTimestampMonotonic) / 10**6
	bootTimestamp = psutil.boot_time()
	timeNow = time.time()
	startTimestamp = bootTimestamp + startTimestampMonotonic
	uptime = int(timeNow - startTimestamp)
	return uptime
#end define

def GetServicePid(name):
	property = "MainPID"
	args = ["systemctl", "show", name, "--property=" + property]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	pid = int(Pars(output, f"{property}=", '\n'))
	return pid
#end define

def GetGitHash(gitPath, short=False):
	args = ["git", "rev-parse", "HEAD"]
	if short is True:
		args.insert(2, '--short')
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	buff = output.split('\n')
	return buff[0]
#end define

def GetGitUrl(gitPath):
	args = ["git", "remote", "-v"]
	try:
		process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=3)
		output = process.stdout.decode("utf-8")
		err = process.stderr.decode("utf-8")
	except Exception as ex:
		err = str(ex)
	if len(err) > 0:
		return
	lines = output.split('\n')
	url = None
	for line in lines:
		if "origin" in line:
			buff = line.split()
			url = buff[1]
		#end if
	return url
#end define

def GetGitAuthorAndRepo(gitPath):
	author = None
	repo = None
	url = GetGitUrl(gitPath)
	if url is not None:
		buff = url.split('/')
		if len(buff) == 5:
			author = buff[3]
			repo = buff[4]
			repo = repo.split('.')
			repo = repo[0]
	return author, repo
#end define

def GetGitLastRemoteCommit(gitPath, branch="master"):
	author, repo = GetGitAuthorAndRepo(gitPath)
	if author is None or repo is None:
		return
	url = "https://api.github.com/repos/{author}/{repo}/branches/{branch}".format(author=author, repo=repo, branch=branch)
	sha = None
	try:
		text = GetRequest(url)
		data = json.loads(text)
		sha = data["commit"]["sha"]
	except URLError: pass
	return sha
#end define

def GetGitBranch(gitPath):
	args = ["git", "branch", "-v"]
	process = subprocess.run(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=gitPath, timeout=3)
	output = process.stdout.decode("utf-8")
	err = process.stderr.decode("utf-8")
	if len(err) > 0:
		return
	lines = output.split('\n')
	branch = None
	for line in lines:
		if "*" in line:
			buff = line.split()
			branch = buff[1]
		#end if
	return branch
#end define

def CheckGitUpdate(gitPath):
	branch = GetGitBranch(gitPath)
	newHash = GetGitLastRemoteCommit(gitPath, branch)
	oldHash = GetGitHash(gitPath)
	result = False
	if oldHash != newHash:
		result = True
	if oldHash is None or newHash is None:
		result = None
	return result
#end define
