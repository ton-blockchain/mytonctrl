#!/usr/bin/env python3

from os import popen
from time import sleep
from sys import stdout
from threading import Thread

class EtaBar:
	def __init__(self, **kwargs):
		self.toolbar_width = kwargs.get("toolbar_width", 10)
		self.snake_width = kwargs.get("snake_width", 4)
		self.timeout = kwargs.get("timeout", 60)
		self.sleep_time = 0.1

		self.square_symbol = '\u25A0'
		self.new_line_symbol = '\r'
		self.indent_symbol = ' '

		self.tty_height, self.tty_width = self.get_tty_size()
		stdout.reconfigure(encoding="utf-8")
	#end define

	def run(self, func=None, *args, **kwargs):
		if func is None:
			func = self.stub
		self.start_thread(func, args=args, kwargs=kwargs)
		self.snake_process()
		return self.thread_result
	#end define

	def stub(self):
		sleep(self.timeout)
	#end define

	def get_tty_size(self):
		with popen("stty size", 'r') as file:
			tty_height, tty_width = file.read().split()
			tty_height = int(tty_height)
			tty_width = int(tty_width)
		return tty_height, tty_width
	#end define

	def start_thread(self, func, **kwargs):
		self.thread_result = None
		self.thread = Thread(target=self.thread_process, name=func.__name__, args=(func,), kwargs=kwargs, daemon=True)
		self.thread.start()
	#end define

	def thread_process(self, func, **kwargs):
		args = kwargs.get("args")
		kwargs = kwargs.get("kwargs")
		self.thread_result = func(*args, **kwargs)
	#end define

	def snake_process(self):
		snake_len = 0
		indent_len = 0
		cycles = int(self.timeout / self.sleep_time)
		for cycle in range(cycles):
			if self.thread.is_alive() == False:
				break
			sleep(self.sleep_time)
			if indent_len == self.toolbar_width:
				indent_len = 0
			elif indent_len == self.toolbar_width - snake_len:
				snake_len -= 1
				indent_len += 1
			elif snake_len == self.snake_width:
				indent_len += 1
			elif snake_len < self.snake_width:
				snake_len += 1
			snake = indent_len * self.indent_symbol + snake_len * self.square_symbol
			filling_len = self.toolbar_width - indent_len - snake_len
			filling = self.indent_symbol * filling_len
			eta = int(self.timeout - cycle * self.sleep_time)
			eta_text = f"   ETA <= {eta} seconds"
			ending_len = self.tty_width - self.toolbar_width - 2 - len(eta_text)
			ending = ending_len * self.indent_symbol
			text = self.new_line_symbol + '[' + snake + filling + ']' + eta_text + ending
			stdout.write(text)
		#end for

		stdout.write(self.new_line_symbol + self.indent_symbol * self.tty_width)
		stdout.write(self.new_line_symbol)
	#end define
#end class
