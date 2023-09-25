from setuptools import setup, find_packages
from os.path import dirname, join

with open(join(dirname(__file__), "README.md"), "r") as f:
    long_description = f.read()


version = 'dev'

setup(
    author='igroman',
    author_email='igroman',
    name='myton',
    version=version,
    packages=find_packages('.', exclude=['tests']),
    install_requires=[
        'crc16',
        'requests',
        'psutil',
        'cryptography',
        'fastcrc',
    ],
    package_data={
        'mytoninstaller.scripts': ['*.sh'],
        'mytonctrl': ['resources/*', 'scripts/*.sh'],
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
         "License :: Other/Proprietary License",
         "Topic :: Software Development :: Libraries"
    ],
    # url="https://github.com/toncenter/pytonlib",
    description="MyTonCtrl",
    long_description_content_type="text/markdown",
    long_description=long_description,
)
