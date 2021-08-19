import os
from configparser import ConfigParser

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
CONFIGS_DIR = f'{BASE_DIR}/configs'

class MTCConfig:
	MTC_CONFIG = f'{CONFIGS_DIR}/mytoncore.ini'
	MINING_SECTION_KEY = 'mining'

	def __init__(self):
		self.config = Config(self.MTC_CONFIG)

	@property
	def mining(self):
		return self.config.section(self.MINING_SECTION_KEY)

	@property
	def mining_threads(self):
		if self.mining:
			return self.mining.getint('threads')


class Config:
	def __init__(self, path):
		self.config = ConfigParser()
		self.config.read(path)

	def section(self, name):
		if self.config and name in self.config:
			return self.config[name]
