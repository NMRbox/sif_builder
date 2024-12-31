# sifbuilder

**sifbuilder** facilitates the building of NMRbox based [Apptainer](https://apptainer.org/docs/user/main/) containers.
Software can be specified either as NMRbox Software entries or debian package names. The most current
versions will be used if no version is specified.

## Installation
Check out project, create virtual environment and run *pip install -e .* from top level directory in virtual environment.
e.g. `python3 -m venv venv`  
`./venv/bin.pip install -e .`

## Configuration
See the *example.yaml*.

## Running

**sifbuilder -h** lists runtime options. The basic syntax pattern is:
- sifbuilder myconfig.yaml generate *(produces def file specified in yaml)*
- sifbuilder myconfig.yaml sif *(generates sif file from def file)*

This allows hand editing of the def file before building the environment.

For debugging environments, `sifbuilder myconfig.yaml sandbox`  is also supported.


### Options
--force to overwrite def or sif files.
by default, the verbose output of Apptainer build commands goes to a file, ``--nolog`` will stream Apptainer output
directly to stdout / stderr.

`--loglevel [Python level]` adds some debug output

# Using container
Apptainer [exec](https://apptainer.org/docs/user/main/cli/apptainer_exec.html) can be used to run a command or script 
inside the container. See the [bind](https://apptainer.org/docs/user/main/quick_start.html#working-with-files) option
for how to make host directories available in the container.

Supporting NMRbox paths from outside the container is not straightforward. 
- consider installing the *nmrbox-paths-paas* or *nmrbox-paths-download* package, or
- use full paths names in scripts


By default the environment accessed by *Apptainer exec* is does not source PATH commands 
(it is not an "interactive" shell). Writing a script that starts with  
`#!/bin/bash -i` 
will make the shell interactive. If not embedded in the container, the script must be on a path the container binds to
by default (e.g. /tmp) or explicitly with -bind option.

## Status
This module is under development pending user feedback.
