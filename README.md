# FLIRT Reg

A simple wrapper for FLIRT registration on large datasets in python

## Requirements

* Linux (if on Windows use WSL as per [the FSL docs](https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation/Windows))
* [FSL](https://fsl.fmrib.ox.ac.uk)
* [Python 3](https://www.python.org/downloads/)
* [Numpy](https://numpy.org/)
* [Nipype](https://nipype.readthedocs.io/en/latest/)

## Installation

1. Clone the repo: `git clone https://github.com/tawilkinson/flirt-reg.git`
2. Change directory: `cd flirt-reg`
3. Initialise the gpuoptional submodule: `git submodule init` then `git submodule update`
4. Install with setuptools: `pip install .`

## Usage

```
usage: flirt-reg [-h] [-f FILENAME] [-d DIRNAME [DIRNAME ...]] [-n NUM] [-o OUTPUT] [-v] [-r] [-b] [-c COST]

optional arguments:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        input image filename. Default: searches current directory for .nii.
  -d DIRNAME [DIRNAME ...], --dirname DIRNAME [DIRNAME ...]
                        input directory name(s). Default: searches same directory for as filename for .nii.
  -n NUM, --num NUM     number of images to process. Default: All images in directory.
  -o OUTPUT, --output OUTPUT
                        output filename. Default: out.csv.
  -v, --verbose         prints debugging information. Default: false.
  -r, --radians         output in radians not degrees. Default: false.
  -b, --brain-extract   Turn off brain extraction. Default: false.
  -c COST, --cost COST  Select a cost function from the following list: [mutualinfo,corratio,normcorr,normmi,leastsq,labeldiff,bbr]

```

* Running: `flirt-reg`, this will search for any .NII files in the directory you ran the script in and use the first image as a reference
* Running with inputs:
    * `flirt-reg -d <input dir>`, specifies a directory to search for .NII files
    * `flirt-reg -f <input file>`, specifies a reference file
    * `flirt-reg -f <input_file> -d <input dir> -b`, registers all images in `input_dir` to the reference, `input_file`, using brain extraction
* Specifying output: `flirt-reg -o <output file>`, specifies a name for the output file instead of out.csv
