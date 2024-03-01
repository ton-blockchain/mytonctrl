from setuptools import setup, find_packages
from os.path import dirname, join

with open(join(dirname(__file__), "README.md"), "r") as f:
	long_description = f.read()
with open(join(dirname(__file__), "requirements.txt")) as file:
	install_requires = file.read().split('\n')


version = 'v0.1'

setup(
	author='igroman787',
	author_email='igroman787',
	name='mytonctrl',
	version=version,
	packages=find_packages('.', exclude=['tests']),
	install_requires=install_requires,
	package_data={
		'mytoninstaller.scripts': ['*.sh'],
		'mytoncore': [
			'contracts/**/*',
			'complaints/*'
		],
		'mytonctrl': [
			'resources/*', 
			'scripts/*', 
			'migrations/*.sh'
		],
		'': ['requirements.txt'],
	},
	zip_safe=True,
	python_requires='>=3.7',
	classifiers=[
		 "Development Status :: 3 - Alpha",
		 "Intended Audience :: Developers",
		 "Programming Language :: Python :: 3.7",
		 "Programming Language :: Python :: 3.8",
		 "Programming Language :: Python :: 3.9",
		 "Programming Language :: Python :: 3.10",
		 "Programming Language :: Python :: 3.11",
		 "License :: Other/Proprietary License",
		 "Topic :: Software Development :: Libraries"
	],
	url="https://github.com/ton-blockchain/mytonctrl",
	description="MyTonCtrl",
	long_description_content_type="text/markdown",
	long_description=long_description,
)
