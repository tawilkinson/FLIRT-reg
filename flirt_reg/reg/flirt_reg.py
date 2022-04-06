import argparse
import csv
import errno
from re import VERBOSE
import gpuoptional.gpuoptional as gpopt
import logging
import os
import subprocess
import time
import nipype.interfaces.fsl as fsl  # fsl
from flirt_reg.reg import omat
from flirt_reg.utils import progress


def is_nii(path):
    """
    Checks if a file is a .nii
    """
    ext = os.path.splitext(path)[1]
    if "ref.nii" in path:
        return False
    if "tmp.nii" in path:
        return False
    if ext == ".nii":
        return True
    return False


def get_nii(data_dir, max_images=None):
    """
    Gets all .nii files in a given directory, can be limited using
    the max_images optional attribute
    """
    print("Searching for data in: {}".format(data_dir))
    all_files = [
        f
        for f in os.listdir(data_dir)
        if (os.path.isfile(os.path.join(data_dir, f)))
    ]
    all_nii = filter(is_nii, all_files)
    all_nii = list(all_nii)
    all_nii.sort()
    logging.debug("{} files found".format(len(all_nii)))
    if max_images and (len(all_nii) > max_images):
        all_nii = all_nii[0:max_images]
        print("List of files truncated to {}".format(len(all_nii)))
    for file in all_nii:
        logging.debug("Found file {}".format(file))

    return all_nii


def get_inputs(n_nii, input_schema):
    """
    Generates a set of filenames
    """
    all_inputs = []
    for i in range(n_nii):
        all_inputs.append(
            f"{input_schema[0]}{str(i).zfill(4)}{input_schema[1]}"
        )
    return all_inputs


def make_coords(datadir, all_inputs, all_nii, fsl_dir, i):
    in_coords = []
    with open("{0}".format(all_inputs[i]), "r") as file:
        for line in file:
            line_in = line.strip("\n").split(" ")
            in_coords.append(line_in)
    with open("{0}/tmp/coord_tmp{1}.txt".format(datadir, i), "w") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=" ")
        regwriter.writerow(
            [
                in_coords[0][3],
                in_coords[1][3],
                in_coords[2][3],
            ]
        )

    f = open("{0}/tmp/trans_tmp{1}.txt".format(datadir, i), "w")
    subprocess.run(
        [
            "{0}/bin/std2imgcoord".format(fsl_dir),
            "-std",
            "{0}/{1}".format(datadir, all_nii[datadir][0]),
            "-img",
            "{0}/{1}".format(datadir, all_nii[datadir][i]),
            "{0}/tmp/coord_tmp{1}.txt".format(datadir, i),
            "-vox",
        ],
        check=True,
        stdout=f,
    )

    new_translations = []
    with open("{0}/tmp/trans_tmp{1}.txt".format(datadir, i), "r") as file:
        for line in file:
            new_translations = line.strip("\n").split("  ")
    with open("{0}/tmp/trans_tmp{1}.txt".format(datadir, i), "w") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=" ")
        regwriter.writerow(
            [
                in_coords[0][0],
                in_coords[0][1],
                in_coords[0][2],
                new_translations[0],
            ]
        )
        regwriter.writerow(
            [
                in_coords[1][0],
                in_coords[1][1],
                in_coords[1][2],
                new_translations[1],
            ]
        )
        regwriter.writerow(
            [
                in_coords[2][0],
                in_coords[2][1],
                in_coords[2][2],
                new_translations[2],
            ]
        )
        regwriter.writerow(
            [
                0,
                0,
                0,
                1,
            ]
        )

    return True


def run_flirt(
    all_nii,
    cur_dir,
    fsl_dir,
    rads=False,
    extraction=False,
    cost_func="leastsq",
):
    xp = gpopt.array_module("cupy")
    omats = []
    original_omats = []
    # First entry is 'registered' to itself
    original_omats.append(xp.array([0, 0, 0, 0, 0, 0]))
    omats.append(xp.array([0, 0, 0, 0, 0, 0]))
    for data_directory in all_nii:
        dir_len = len(all_nii[data_directory])
        if cur_dir == data_directory:
            start_idx = 1
        else:
            start_idx = 0

        print("Running FLIRT on {}".format(data_directory))
        progress.printProgressBar(
            start_idx,
            dir_len,
            prefix="Progress:",
            suffix="Complete",
            length=50,
        )
        for i in range(start_idx, dir_len):
            if extraction:
                btr = fsl.BET()
                btr.inputs.in_file = "{0}/{1}".format(
                    data_directory, all_nii[data_directory][i]
                )
                btr.inputs.out_file = "{0}/tmp.nii".format(data_directory)
                res = btr.run()
                if res.runtime.returncode != 0:
                    print(
                        'Error in FSL bet command: \'{2}/bin/bet \
                        "{0}/{1}" "{0}/tmp.nii"\', check there \
                        are no spaces in path'.format(
                            data_directory, all_nii[data_directory][i], fsl_dir
                        )
                    )
                    exit(0)
            else:
                os.system(
                    "cp {0}/{1} {0}/tmp.nii".format(
                        data_directory, all_nii[data_directory][i]
                    )
                )

            flt = fsl.FLIRT(
                bins=256,
                dof=6,
                cost_func=cost_func,
                uses_qform=True,
                terminal_output="allatonce",
            )
            flt.inputs.in_file = "{0}/tmp.nii".format(data_directory)
            flt.inputs.reference = "{0}/ref.nii".format(cur_dir)
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.out_matrix_file = "{0}/tmp{1}.txt".format(
                data_directory, i
            )
            flt.inputs.out_file = "{0}/reg{1}.nii.gz".format(data_directory, i)
            flt.inputs.searchr_x = [-90, 90]
            flt.inputs.searchr_y = [-90, 90]
            flt.inputs.searchr_z = [-90, 90]
            flt.inputs.interp = "trilinear"
            res = flt.run()
            if res.runtime.returncode != 0:
                print("Error in FLIRT command: '{}'".format(flt.cmdline))
                exit(0)

            # This will use avscale to get real world co-ords
            # out of FLIRT
            f = open("{0}/avs.txt".format(data_directory), "w")
            avscale = fsl.AvScale(all_param=True, terminal_output="allatonce")
            avscale.inputs.mat_file = "{0}/tmp{1}.txt".format(
                data_directory, i
            )
            avscale.inputs.ref_file = "{0}/reg{1}.nii.gz".format(
                data_directory, i
            )
            res = avscale.run()
            if res.runtime.returncode != 0:
                print("Error in AVScale command")
                exit(0)
            avs_str = str(res.runtime.stdout)
            flt = fsl.FLIRT(
                cost_func=cost_func,
                terminal_output="allatonce",
            )
            flt.inputs.in_file = "{0}/reg{1}.nii.gz".format(data_directory, i)
            flt.inputs.reference = "{0}/ref.nii".format(cur_dir)
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.schedule = "{0}/etc/flirtsch/measurecost1.sch".format(
                fsl_dir
            )
            flt.inputs.in_matrix_file = "{0}/tmp{1}.txt".format(
                data_directory, i
            )
            flt.inputs.out_file = "{0}/reg{1}.nii.gz".format(data_directory, i)

            res = flt.run()
            cost_str = str(res.runtime.stdout)
            cost_val = float(cost_str.split()[0])
            if res.runtime.returncode != 0:
                print("Error in FLIRT command: '{}'".format(flt.cmdline))
                exit(0)
            try:
                original_omats.append(omat.read_avs(avs_str, cost_val))
                tmp_omat = omat.read_tmp_trans(
                    "{0}/tmp{1}.txt".format(data_directory, i)
                )
                original_omats[-1][0] = tmp_omat[0][3]
                original_omats[-1][1] = tmp_omat[1][3]
                original_omats[-1][2] = tmp_omat[2][3]
                omats.append(original_omats[-1])
            except IndexError:
                logging.debug(
                    "{0}/tmp{1}.txt does not contain omat data".format(
                        data_directory, i
                    )
                )

            progress.printProgressBar(
                i + 1,
                dir_len,
                prefix="Progress:",
                suffix="Complete",
                length=50,
            )
    return omats, original_omats


def flirt_reg(
    fname=None,
    oname=None,
    verbose=False,
    max_images=None,
    dname=None,
    rads=False,
    extraction=False,
    cost_func="leastsq",
):
    """
    FLIRT registration function
    """
    # Setup debugging
    print("Starting flirt_reg")
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Verbosity: {}".format(verbose))

    data_dirs = []
    if dname:
        for directory in dname:
            data_dirs.append(os.path.abspath(directory))
    else:
        data_dirs.append(os.getcwd())

    # Check input files and get the baseline file to register against
    if fname:
        logging.debug("Checking file {}".format(fname))
        if os.path.isfile(os.path.abspath(fname)):
            logging.debug("Opening file {}".format(fname))
            cur_dir = os.path.dirname(os.path.abspath(fname))
            all_nii = {}
            n_nii = 0
            for data_directory in data_dirs:
                all_nii[data_directory] = get_nii(data_directory, max_images)
                n_nii += len(all_nii[data_directory])
        else:
            logging.debug(
                "!!! {} is not a file. !!!\
                            \nExiting...".format(
                    fname
                )
            )
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), fname
            )
    else:
        cur_dir = os.getcwd()
        all_nii = {}
        print(f"{data_dirs}")
        all_nii[data_dirs[0]] = get_nii(data_dirs[0], max_images)
        print(f"{all_nii}")
        fname = os.path.join(data_dirs[0], all_nii[data_dirs[0]][0])
        n_nii = len(all_nii)

    if n_nii == 0:
        print("No NIFTI files found, exiting...")
        exit()

    if os.path.exists("/usr/local/fsl"):
        fsl_dir = "/usr/local/fsl"
    elif os.path.exists("/usr/share/fsl/5.0"):
        fsl_dir = "/usr/share/fsl/5.0"
    else:
        fsl_dir = "/usr/share/fsl"

    logging.debug("FSL Base Dir: {}".format(fsl_dir))

    # Brain extract the reference image
    if extraction:
        os.system("{}/bin/bet {} {}/ref.nii".format(fsl_dir, fname, cur_dir))
    else:
        os.system("cp {} {}/ref.nii".format(fname, cur_dir))

    omats, original_omats = run_flirt(
        all_nii,
        cur_dir,
        fsl_dir,
        rads=rads,
        extraction=extraction,
        cost_func=cost_func,
    )

    for registration in omats:
        logging.debug(omat.get_reg_str(registration, rads=rads))

    if oname:
        # Save to specified filename
        logging.debug("Saving to {}".format(oname))
        omat.reg_to_csv(omats, os.path.join(data_dirs[0], oname))
        omat.avs_to_csv(
            original_omats,
            os.path.join(data_dirs[0], "original_{}".format(oname)),
        )
    else:
        # Save to out.nii
        logging.debug("Saving to {}".format("out.csv"))
        omat.reg_to_csv(omats, os.path.join(data_dirs[0], "out.csv"))
        omat.avs_to_csv(
            original_omats, os.path.join(data_dirs[0], "original_out.csv")
        )

        return omats


def apply_transform(
    oname="out_####.nii", dname=None, iname=None, verbose=False
):
    """
    Applies transforms in FLIRT style mat files
    """
    print("Starting apply_transform")
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.debug("Verbosity: {}".format(verbose))
    data_dirs = []
    if dname:
        for directory in dname:
            data_dirs.append(os.path.abspath(directory))
    else:
        data_dirs.append(os.getcwd())

    if iname:
        filen, file_ext = os.path.splitext(iname)
        # Allow numbers to be replaced with #
        input_schema = [filen.replace("#", ""), file_ext]
    else:
        input_schema = [os.path.join(data_dirs[0], "MAT_"), ".txt"]
    # Check input file exists
    first_file = f"{input_schema[0]}0000{input_schema[1]}"
    logging.debug(f"Checking file {first_file}")
    if os.path.isfile(os.path.abspath(first_file)):
        logging.debug("Opening file {}".format(first_file))
        cur_dir = os.path.dirname(os.path.abspath(first_file))
        all_nii = {}
        n_nii = 0
        for data_directory in data_dirs:
            all_nii[data_directory] = get_nii(data_directory)
            n_nii += len(all_nii[data_directory])
            all_inputs = get_inputs(n_nii, input_schema)
    else:
        logging.debug(
            "!!! {} is not a file. !!!\
                    \nExiting...".format(
                first_file
            )
        )
        raise FileNotFoundError(
            errno.ENOENT, os.strerror(errno.ENOENT), first_file
        )

    if n_nii == 0:
        print("No NIFTI files found, exiting...")
        exit()

    # Should make this a global somewhere
    if os.path.exists("/usr/local/fsl"):
        fsl_dir = "/usr/local/fsl"
    elif os.path.exists("/usr/share/fsl/6.0"):
        fsl_dir = "/usr/share/fsl/6.0"
    elif os.path.exists("/usr/share/fsl/5.0"):
        fsl_dir = "/usr/share/fsl/5.0"
    else:
        fsl_dir = "/usr/share/fsl"

    logging.debug("FSL Base Dir: {}".format(fsl_dir))

    for data_directory in all_nii:
        dir_len = len(all_nii[data_directory])

        print("Applying FLIRT Transform on {}".format(data_directory))
        if cur_dir == data_directory:
            start_idx = 1
        else:
            start_idx = 0

        progress.printProgressBar(
            start_idx,
            dir_len,
            prefix="Progress:",
            suffix="Complete",
            length=50,
        )

        if not os.path.exists("{0}/tmp".format(data_directory)):
            os.mkdir("{0}/tmp".format(data_directory))
        if not os.path.exists("{0}/FLIRT_out".format(data_directory)):
            os.mkdir("{0}/FLIRT_out".format(data_directory))
        for i in range(start_idx, dir_len):
            make_coords(data_directory, all_inputs, all_nii, fsl_dir, i)
            # apply the transform
            flt = fsl.FLIRT(apply_xfm=True, terminal_output="allatonce")
            flt.inputs.in_file = "{0}/{1}".format(
                data_directory, all_nii[data_directory][i]
            )
            flt.inputs.reference = "{0}/{1}".format(
                data_directory, all_nii[data_directory][0]
            )
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.schedule = "{0}/etc/flirtsch/measurecost1.sch".format(
                fsl_dir
            )
            flt.inputs.in_matrix_file = "{0}/tmp/trans_tmp{1}.txt".format(
                data_directory, i
            )
            flt.inputs.out_file = "{0}/FLIRT_out/out_{1}.nii.gz".format(
                data_directory, i
            )
            res = flt.run()
            if res.runtime.returncode != 0:
                print("Error in FLIRT command: '{}'".format(flt.cmdline))
                exit(0)
            progress.printProgressBar(
                i + 1,
                dir_len,
                prefix="Progress:",
                suffix="Complete",
                length=50,
            )

    return True


def apply_transform_cmd():
    # Initialise simple timer
    start_time = time.time()
    """
    A simple runner for the program with arguments
    """
    # execute only if run as a script
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dirname",
        nargs="+",
        help="input directory name(s). Default: searches \
                same directory for as filename for .nii.",
    )
    parser.add_argument(
        "-o", "--output", help="output filenames. Default: out_####.nii."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="prints debugging information. Default: false.",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="input mat files. Default: tries to find MAT_####.txt \
                in local dir.",
    )
    args = parser.parse_args()

    # call the apply_transform function with cmd line args
    apply_transform(
        oname=args.output,
        dname=args.dirname,
        iname=args.input,
        verbose=args.verbose,
    )

    if args.verbose:
        total_time = time.gmtime((time.time() - start_time))
        print(f"Pipeline complete in {time.strftime('%Hh%Mm%Ss', total_time)}")