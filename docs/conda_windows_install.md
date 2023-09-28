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

## Adding Conda Environments to Jupyter Notebook

Conda allows you to create isolated environments with specific versions of Python and its packages.
This prevents conflicts between
different projects' dependencies.

### Step 1: Create your conda environment
Inside of your conda based command line navigate inside your forked PopsBorder
folder. Next use the following command
```bat
conda create -n PopsBorderEnv python=3.8
```
This creates your environment with python version 3.8.
PopsBorderEnv is the name of your environment. Change as needed.

### Step 2: Activate your environment
Using your newly created environment from the previous step, run
```bat
conda activate PopsBorderEnv
```
Now you have entered into your environment.

### Step 3: Install pipenv into you environment
Now install pipenv into your environment, a packaging tool we utilize
for our project.
```bat
conda install pipenv
```

### Step 4: Install dependencies using pipenv
To download dependencies and create a virtual environment from the Pipfile.lock use:
```bat
pipenv install
```

### Step 5: Install your jupyter notebook in your Virtual Environment
Run the command below to install the necessary python kernel.
```bat
pipenv run conda install ipykernel
```
Next Run the following command replacing PopsBorderEnv with your
environment name:
```bat
pipenv run python -m ipykernel install --user --name=PopsBorderEnv
```
This installs a jupyter kernel in your environment, allowing you to
use your kernel in Jupyter Notebook.

### Step 6: Open Jupyter Notebook
Run from within your environment
```bat
pipenv run jupyter notebook
```
This will open jupyter notebook in your default browser or provide
a url in the terminal. You now have your environment linked to
jupyter notebook.

### Step 7: Select the correct kernel
Navigate into the notebook file you want to run, denoted by .ipynb.
Examples can be found in the /examples/notebooks folder.
Click on the Kernel tab, then the "Change Kernel" tab and select your
created environment, in this case ours is "PopsBorderEnv".
Now you can run the notebook files.