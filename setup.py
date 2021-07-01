import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PoPS Border",
    version="0.9.0",
    author="Vaclav Petras, Kellyn P. Montgomery",
    author_email="vpetras@ncsu.edu",
    description="Simulation of contaminated consignment and their inspections",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ncsu-landscape-dynamics/popsborder",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: OS Independent",
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Scientific/Engineering",
    ],
    python_requires=">=3.5",
    install_requires=["numpy", "scipy", "pandas", "PyYAML"],
)
