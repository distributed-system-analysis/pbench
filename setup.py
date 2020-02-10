import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("VERSION", "r") as fh:
    version = fh.read()

setuptools.setup(
    name="pbench",
    version=version,
    description="A Benchmarking and Performance Analysis Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://distributed-system-analysis.github.io/pbench",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
)
