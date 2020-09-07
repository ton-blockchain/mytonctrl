from mytoncore import *


Init()
ton = MyTonCore()
local.StartCycle(ScanBlocks, sec=1, args=(ton,))
local.StartCycle(ReadBlocks, sec=0.3, args=(ton,))


while True:
	time.sleep(1)
	print(local.buffer["transNum"])
	# print(len(local.buffer["blocks"]))
#end while


