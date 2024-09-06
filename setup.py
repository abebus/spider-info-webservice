from setuptools import setup, find_packages

from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

DESCRIPTION = "Scrapy extension for monitoring spider."

setup(
    name="spider_info_webservice",
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author="abebus",
    author_email="anamaev263@gmail.com",
    version="0.0.3.1",
    url="https://github.com/abebus/spider-info-webservice",
    packages=find_packages(),
    install_requires=["scrapy>=2.6"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.8",
)
