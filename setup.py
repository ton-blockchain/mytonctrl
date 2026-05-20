from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).resolve().parent


setup(
    name="mytonctrl",
    version="0.1.0",
    description="MyTonCtrl",
    long_description=(ROOT / "README.md").read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="TON Core",
    url="https://github.com/ton-blockchain/mytonctrl",
    packages=find_packages(
        ".",
        include=[
            "mytoninstaller*",
            "mypyconsole*",
            "mytonctrl*",
            "mypylib*",
            "modules*",
            "mytoncore*",
        ],
        exclude=["tests", "tests.*"],
    ),
    install_requires=[
        "requests==2.32.4",
        "psutil==6.1.0",
        "fastcrc==0.3.2",
        "pynacl==1.5.0",
        "importlib_resources==6.4.5; python_version < '3.9'",
    ],
    package_data={
        "mytoninstaller.scripts": ["*.sh"],
        "mytoncore": [
            "contracts/single-nominator-pool/*",
            "complaints/*",
        ],
        "mytonctrl": [
            "resources/*",
            "scripts/*",
        ],
    },
    python_requires=">=3.8",
)
