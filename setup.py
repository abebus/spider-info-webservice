from setuptools import setup, find_packages


VERSION = "0.0.2"
DESCRIPTION = "Scrapy extension for monitoring spider."

setup(
    name="spider_info_webservice",
    description=DESCRIPTION,
    long_description=DESCRIPTION,
    author="abebus",
    author_email="anamaev263@gmail.com",
    version=VERSION,
    url="https://github.com/abebus/spider-info-webservice",
    packages=find_packages(),
    install_requires=["scrapy>=2.6"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
    ],
    python_requires=">=3.12",
)
