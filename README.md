# FLIRT Reg

A simple wrapper for FLIRT registration on large datasets in python

## Requirements

* Linux (if on Windows use WSL as per [the FSL docs](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation/Windows))
* [FSL](https://fsl.fmrib.ox.ac.uk)
* [Python 3](https://www.python.org/downloads/)
* [Numpy](https://numpy.org/)

## Installation

1. Clone the repo: `git clone https://github.com/tawilkinson/flirt-reg.git`
2. Change directory: `cd flirt-reg`
3. Initialise the gpuoptional submodule: `git submodule init` then `git submodule update`
4. Install with setuptools: `pip install .`

## Usage

* Running: `flirt-reg`, this will search for any .NII files in the directory you ran the script in
* Running with inputs: `flirt-reg -i <input dir>`, specifies a directory to search for .NII files
* Specifying output: `flirt-reg -o <output file>`, specifies a name for the output file instead of out.txt
