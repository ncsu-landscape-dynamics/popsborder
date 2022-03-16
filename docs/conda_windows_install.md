# Installing popsborder with conda on Windows

As an alternative to pipenv, you can manage the Python packages needed to run popsborder using a conda environment.

Unless you plan to use additional features of the Anaconda suite (e.g. Anaconda Navigator, Jupyter Notebook, and other tools), we recommend installing Miniconda, which contains only the conda package manager and Python.

Follow the instruction to download and install Miniconda: <https://docs.conda.io/en/latest/miniconda.html>

Once installed, open Command Prompt and run the following lines, one at a time:

```bat
conda create --name popsborder_env python=3.10 matplotlib seaborn git pip
conda activate popsborder_env
conda install -c conda-forge jupyterlab
pip install git+https://github.com/ncsu-landscape-dynamics/popsborder
conda deactivate
```

To use your environment, run the command "conda activate popsborder_env" or select the popsborder_env environment from your IDE (e.g. VS Code, Atom, PyCharm).
