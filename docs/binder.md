# Binder and mybinder.org

Binder is a tool which can run Jupyter Notebooks and other notebooks
or scripts in a cloud environment without any need for setup or an
account.

Binder works as any other website, but instead of pressing
links or buttons, you can run Python code which runs somewhere in the
cloud (not on you computer). This means that you don't have to install
anything on your computer and it is really just another website.
However, this also means that you cannot upload any private or internal
data or documents.

Here is a link to the example notebook for the simulation using the
mybinder.org service:

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ncsu-landscape-dynamics/popsborder/main?urlpath=lab/tree/basic_with_command_line.ipynb)

Note also that using mybinder.org is not required. You can run the
notebook locally if you install Jupyter. The Binder (BinderHub) itself
is open source and can be installed on institutional servers and run
internally.

## Saving your work

There is no persistent cloud storage in Binder, so you need to take care
of saving the file.

It is important to rememberer that the cloud instance used for
computations is just temporary.
Simply saving a file only saves it in the temporary instance.
To preserve the file for later use, you need to download it.
There are three ways how to do it. You can use whatever is most
convenient for you. Here are the three choices:

* There is a *Download* button in the top toolbar of the notebook.

* You can use File Browser on the left. Right click on the notebook file,
  and pick *Download*. If you are contributing the notebook file into
  this repository, you need to use this option because it produces a
  nicely formatted file (however, there is no different in content or
  what you see once you display the notebook).

* Next to the *Download* button there are "cloud download" and
  "cloud upload" icons. You can use those to save the notebook into your
  browser storage (on you computer) rather as a regular file on your disk.
  This option is handy for quickly getting the file saved (and then
  restored later).

## Lifetime of the environment

Every time you use the link (the *launch binder* button) a new
environment is created for you. 

After some time of inactivity, the notebook's kernel (a program running
in the cloud making the Python code work) will shut down. If that's the
case, the notebook will show *No Kernel!* in the top right corner.
To fix that, restart the kernel from menu using:
*Kernel* > *Restart kernel*.

After even more time of inactivity the whole environment shuts down.
There is no way to restore it. To avoid any surprises, it is good to
save your work often.

Next: [Command line interface](cli.md)
