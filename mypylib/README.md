## Что это
Данная библиотека служит для быстрого написания фоновых приложений и системных служб.
В ней имеются логирование, сохранение локальных файлов, контроль состояния потоков и используемой памяти, способность к самообновлению (например из github) и контроль запуска одного процесса.

## Быстрый старт
```python
from mypylib.mypylib import *

local = MyPyClass(__file__)

def Config():
	# Нижеприведенная настройка является не обязательным.
	local.db["config"]["isStartOnlyOneProcess"] = False		# Отключить защиту на запуск единственного процесса. По умолчанию = True
	local.db["config"]["isLimitLogFile"] = False			# Отключить контроль размера файла логирования. По умолчанию = True
	local.db["config"]["isDeleteOldLogFile"] = True			# Включить удаление файла логирования перед запуском. По умолчанию = False
	local.db["config"]["isIgnorLogWarning"] = True			# Включить игнорирование предупреждений. По умолчанию = False
	local.db["config"]["memoryUsinglimit"] = 20				# Установить лимит контроля использования памяти в Мб. По умолчанию = 50
	local.db["config"]["isLocaldbSaving"] = True			# Сохранять локальную БД (local.db) в файл. По умолчанию = False
	local.db["config"]["isWritingLogFile"] = False			# Отключить запсиь логов в файл. По умолчанию = True
	local.db["config"]["logLevel"] = "debug"				# Уровень логирования. По умолчанию = info
#end define

def General(args):
	local.AddLog("start General function with args " + args)
	# some code...


	# example:
	print(json.dumps(local.buffer, indent=4))
	local.PrintSelfTestingResult()
#end define

###
### Start of the program
###

if __name__ == "__main__":
	Config()
	local.Run()
	local.Cycle(General, sec=3, args=("test args",))
#end if
```
