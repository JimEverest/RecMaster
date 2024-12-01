from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="RecMaster",  # PyPI上的包名
    version="0.1.0",  # 版本号
    author="JimEverest",  # 作者名
    author_email="tianwai263@gmail.com",  # 作者邮箱
    description="A simple and efficient screen recorder with audio support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JimEverest/RecMaster",  # GitHub仓库地址
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Sound/Audio :: Capture/Recording",
        "Topic :: Multimedia :: Video :: Capture",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    python_requires=">=3.6",
    install_requires=[
        "comtypes",
        "numpy",
        "pywin32",
        "pycaw",
        "ffmpeg-python",
        "humanize",
    ],
) 