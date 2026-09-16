# RBS PIS Slippage Model GUI Install and Use Instructions

Johns Hopkins University Applied Physics Laboratory (APL) has extended
the simulation framework, PoPS Border, co-developed by North Carolina
State University and the USDA Animal Plant Health and Inspection
Services (APHIS).  APL has implemented additional features
and functionality that applies the USDA Risk Based Sampling (RBS)
inspection process being conducted at 
USDA plant inspection stations (PIS).

Features and Functionality Added:
- Data driven options for generating and contaminating consignments
- Additional metrics added to the PoPS border framework
- Graphic user interface for building scenarios, running the model, and visualizing results
- RBS strategies captured via uploaded compliance tables

### Limitations
The additional features mentioned above have been implemented have tested by the technical team and some user engagement sessions
have been conducted to gather feedback and identify bugs in the source code.  Although default code guards have been put in place
to prevent crashes during use, there are some limitations that should be highlighted:

- Formal validation of outputs has not been fully complete on some functionality including:
  - Synthetic generation of consignments via the standalone utility script 
  `slippage_model_utils/generate_synthetic_consignments.py`
  - The wrapper functionality to be able to run `R` code within this repository (developed for the
  generating and contaminating consignments features above and contained within
  `slippage_model_utils/r_script_wrapper.py`) has undergone multiple iterations of changes to
  adjust for different platforms and environments.   Although safeguards and defaults have been put in place
  to ensure functionality of PoPS border and updated PIS simulations, additional testing would be needed
  to ensure the wrapper functionality is functioning as intended.
- An extensive set of user tests and engagements for the GUI to understand where any additional
crashes with install and use across multiple platforms occurs.

© 2026 The Johns Hopkins University Applied Physics Laboratory LLC

---
## Things to know before You Start

### Accessing the PoPS Border Graphical User Interface (GUI)

After you have completed the installation process below, you can access the GUI at any time by opening a **Miniforge Prompt** and entering the following lines of code:
```
    conda activate venv
```
```
    cd plant-inspection-station-simulation
```
```
    streamlit run frontend.py
```
In the **Miniforge Prompt** window, you can revert back to the ability to enter lines of code (for example, to restart the GUI if it is accidentally closed) by pressing **Ctrl+C**. 

---
### Required Software

**_Note_**:  _You can skip any aspects you already have
completed or have on your machine (e.g., if you have Python installed,
you can skip step 2 below)_

This software has been tested on **Windows 10/11**.

You will need the following **before** proceeding:

1. **Install Miniforge with Python 3.11+**
   - Download Miniforge from the official conda-forge page: https://conda-forge.org/download/
   - If on a government computer, you can install Miniforge from "Software Center" (managed by IT)
   - On the download page, select the Miniforge installer for your operating system; for most Windows machines this will be the 64-bit Windows installer.
   - During installation:
        - Install for all users (requires admin priveledges) 
        - Accept all other default and recommended installation options

2. **Local Access To This Git Repository**
   - You can download the repository as a archive ('zip' file)
   - You can install GitHub to access this repository
   - You can install Git GUI to access this repository
   - You can use GitLab to access/download this repository as an archive

After installing the above, **restart your computer** before continuing.

---
### Using Command Windows

You will be using the **Miniforge Prompt window** to utilize conda as you create virtual environments and access the model and UI:

- **How to Access**  
  Install Miniforge as mentioned above
  Find and run "Miniforge Prompt" from your Start menu

You will be using **Command prompt** only if you decide to update the code repository through Git rather than as an archive.

- **How to Access**  
  Type "Command Prompt" into the start menu.

---
### Accessing the Code Repository

1. Using GitLab/downloaded archive
   - Open the GitLab repository link in your web browser
   - Click the blue **Code** button
   - Under "download source code" select "zip"
   - open the downloaded archive file and copy the contents in your "User" folder 
     - e.g., `"C:\Users\<your-username>"`
   - Ensure that the top level directory folder name after `<your-username>` is `plant-inspection-station-simulation`. 
   If the folder name includes any additional text at the end (e.g., `plant-inspection-station-simulation-main`), 
   you should remove the excess text (e.g., `-main`) by renaming the folder.

2. Using GitHub
   - Open the GitLab repository link in your web browser
   - Click the blue **Code** button
   - select the option "Clone with HTTPS"
   - Open **PowerShell**, then run:
```powershell
    cd C:\Users\<your-username>
    git clone <PASTE_THE_URL_HERE>
```

If you see files such as Pipfile, frontend.py, and slippage_model_utils,
you are in the correct directory.


### Subfolders within the Plant-Inspection-Station-Simulation repository

- "data_input": Houses files used for completing the 'GUI Structure Testing' example problems. These examples are intended to walk through examples uses of the PoPS Border tool within the GUI. 
- "Slippage_model_utils": Contains the files which run the Slippage model within the PoPS Border GUI
- "popsborder": Contains the files from the original PoPS border used within the PoPS Border GUI

--- 

## Initial Setup and Installation of PoPs Border and New Features
High-level, this is a three step process to install and run the model with the updated features: You will need to create a python virtual environment to run the frontend, an rscript virtual environment to run the PoPs Border slippage model, and then run the PoPs Border model through the frontend.


### Setting up the Python Virtual Environment
   1. Open **Miniforge Prompt** command window.
     - This should open into your "Username" folder. If not, navigate there through the command prompt.
```
     cd C:\Users\<your-username>
```
   2. Enter the archive folder containing the files copied/cloned above.
```
    cd plant-inspection-station-simulation
```

Note: The top level of the repository should have the exact name `plant-inspection-station-simulation` to avoid any conflicts.

  3. If you already have a ```venv``` virtual environment, remove it.

```
    conda env remove -n venv
```
**_Note_**: _You can check if you have this ```venv``` by using command ```conda env list```. Skip this step if you do not see a folder/directory called ```venv``` in list that is displayed. If displayed in list, enter the removal command above._


  4. Use conda to create a python and Rscript virtual environment called 'venv'.
```
    conda create -n venv -c conda-forge python=3.11 r-base r-jsonlite r-stringr r-dplyr r-arrow rpy2 pip -y
```
**_Note_**: _You may be prompted to accept the Terms of Service (TOS) before being allowed to continue. Review these and type "y" and click enter to continue. You will also be prompted to proceed after the package list is presented; click "y" and enter again to continue._


  5. Activate the Python virtual environment.
```
    conda activate venv
```
  6. Install the "requirements.txt" file within the plant-inspection-station-simulation folder to include the required versions of required packages in your virtual environment.

```
    pip install -r requirements.txt --timeout=10000
```

---
### Verify Correct Virtual Environment Setup
In the same **Miniforge Prompt** window, run these scripts to verify that Python and Rscript are working correctly within the virtual environment.
1. (optional) Activate the venv environment; you can skip this step if already active. You can tell if the virtual environment is already active if the command line prompt states with "(venv)" instead of "(base)".
```
    conda activate venv
```
2. Verify that python  runs within the venv virtual environment.
``` 
    python --version
```
Running this line of code should respond with the version of python installed in the virtual environment.

2. Verify that the R script runs within the venv virtual environment.
```
    Rscript -e "cat('Rscript is alive\n')"
```
Running this script should respond "Rscript is alive".

3. Verify that the wrapper runs successfully
```
    python -c "from slippage_model_utils.r_script_wrapper import run_clarke_bb_group_model as run; print('Wrapper imported successfully')"
```
Running this line of code should respond "Wrapper imported successfully". 

---
### Verifying Streamlit 
In the same **Miniforge Prompt** window, run these scripts to verify that the virtual environments are working correctly.

1. (optional) Activate the Python virtual environment (venv); you can skip this step if already active. You can tell if the virtual environment is already active if the command line prompt starts with "(venv)" instead of "(base)".
```
    conda activate venv
```
2. Verify that streamlit is installed and accessible within the virtual environment. 
```
    streamlit --version
```
---
## Activating the PoPs Border GUI
1. (optional) Activate the Python virtual environment (venv); you can skip this step if already active. You can tell if the virtual environment is already active if the command line prompt starts with "(venv)" instead of "(base)".
```
    conda activate venv
```
2. Activate the GUI via streamlit.
```
    streamlit run frontend.py
```

After running the above command, a web browser should automatically open
with the initial landing page.  If not, then it should provide a link
that you can open.

In the **Miniforge Prompt** window, you can revert back to the ability to enter lines of code (to restart the GUI if it is accidentally closed) by pressing **Ctrl+C**. 

### Additional Notes for GUI Use

- All outputs (files, figures, etc.) generated by GUI
will be put into a sub-directory of the top-level directory 
called "Outputs".
- Items used/created by the "scenario builder" components
of the GUI will be placed in a sub-directory called "tmp".

**Maintainers and POCs:** Joseph Agor (joseph.agor@jhuapl.edu) and Gary Lin (Gary.Lin@jhuapl.edu)

**Last updated:** August, 18 2026

---
