#!/usr/bin/env python3
# -*- coding: utf_8 -*-

import os
import sys
import time
import json
sys.path.append("/usr/src/mytonctrl/")
from mypylib.mypylib import Dict

def read_session_stats(need_time_period):
	#print(f"read_session_stats: {need_time_period}")
	file_path = "/var/ton-work/log.session-stats"
	average_block_time = calculate_average_block_time(file_path)
	need_blocks = int(need_time_period/average_block_time)
	
	lines = read_last_lines(file_path, need_lines=need_blocks)
	#lines = read_all_lines(file_path)
	data = lines2data(lines)
	
	result = Dict()
	result.my_blocks = 0
	result.my_need_blocks = 0
	result.all_master_blocks = 0
	result.all_blocks = len(data)
	for buff in data:
		if buff.id.workchain == -1:
			result.all_master_blocks += 1
		first_producer = buff.rounds[0].producers[0]
		if buff.self != first_producer.id:
			continue
		result.my_need_blocks += 1
		if buff.self == buff.creator:
			result.my_blocks += 1
	#end for
	return result
#end define

def calculate_average_block_time(file_path):
	blocks = 100
	lines = read_last_lines(file_path, need_lines=blocks)
	data = lines2data(lines)
	first_block, last_block = get_first_last_block(data)
	
	diff = int(last_block.timestamp) - int(first_block.timestamp)
	average_block_time = round(diff/blocks, 2)
	#print("average_block_time:", average_block_time)
	return average_block_time
#end define

def get_first_last_block(data, last_index=-1):
	first_block = data[0]
	last_block = data[last_index]
	if first_block.id.workchain == last_block.id.workchain:
		blocks = int(last_block.id.seqno) - int(first_block.id.seqno)
	else:
		first_block, last_block = get_first_last_block(data, last_index=last_index-1)
	return first_block, last_block
#end define

def lines2data(lines):
	#start = time.time()
	data = list()
	for line in lines:
		try:
			buff = json.loads(line)
			data.append(Dict(buff))
		except json.decoder.JSONDecodeError:
			pass
	#end for
	
	#end = time.time()
	#diff = round(end - start, 2)
	#print(f"lines2data completed in {diff} seconds")
	return data
#end define

def read_all_lines(file_path):
	#start = time.time()
	with open(file_path, 'rt') as file:
		text = file.read()
	#end with
	lines = text.split('\n')
	
	#end = time.time()
	#diff = round(end - start, 2)
	#print(f"read_all_lines completed in {diff} seconds")
	return lines
#end define

def read_last_lines(file_path, need_lines):
	lines = list()
	max_lines = 30000
	if need_lines < 1:
		return lines
	elif need_lines > max_lines:
		need_lines = max_lines
	#print(f"read_last_lines: {need_lines}")
	#start = time.time()
	with open(file_path, 'rb') as file:
		find_last_lines(file, need_lines)
		for i in range(need_lines):
			line = file.readline().decode()
			lines.append(line)
	#end with
	
	
	#end = time.time()
	#diff = round(end - start, 2)
	#print(f"read_last_lines {len(lines)} completed in {diff} seconds")
	return lines
#end define

def find_last_lines(file, need_lines):
	# catch OSError in case of a one line file 
	try:
		find_lines = 0
		#file.seek(-2, os.SEEK_END)
		#while find_lines != need_lines:
		#	if file.read(1) == b'\n':
		#		find_lines += 1
		#	file.seek(-2, os.SEEK_CUR)
		
		file.seek(-100, os.SEEK_END)
		while find_lines != need_lines:
			if b'\n' in file.read(100):
				find_lines += 1
			file.seek(-200, os.SEEK_CUR)
	except OSError:
		file.seek(0)
#end define





