from setuptools import setup, find_packages

setup(
    name="scroll",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "scroll=scroll.__main__:main",
        ],
    },
    python_requires=">=3.7",
)
