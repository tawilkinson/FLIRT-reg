import argparse
import csv
import errno
from re import VERBOSE
import gpuoptional.gpuoptional as gpopt
import logging
import os
import subprocess
import time
import nibabel as nb
import nipype.interfaces.fsl as fsl  # fsl
import matplotlib.pyplot as plt
from pygifsicle import optimize
from matplotlib.animation import FuncAnimation, PillowWriter
from flirt_reg.reg import omat
from flirt_reg.utils import progress, figstring


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
    print(f"Searching for data in: {data_dir}")
    all_files = [
        f
        for f in os.listdir(data_dir)
        if (os.path.isfile(os.path.join(data_dir, f)))
    ]
    all_nii = filter(is_nii, all_files)
    all_nii = list(all_nii)
    all_nii.sort()
    logging.debug(f"{len(all_nii)} files found")
    if max_images and (len(all_nii) > max_images):
        all_nii = all_nii[0:max_images]
        print(f"List of files truncated to {len(all_nii)}")
    for file in all_nii:
        logging.debug(f"Found file {file}")

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
    with open(f"{all_inputs[i]}", "r") as file:
        for line in file:
            line_in = line.strip("\n").split(" ")
            in_coords.append(line_in)
    with open(f"{datadir}/tmp/coord_tmp{i}.txt", "w") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=" ")
        regwriter.writerow(
            [
                in_coords[0][3],
                in_coords[1][3],
                in_coords[2][3],
            ]
        )

    f = open(f"{datadir}/tmp/trans_tmp{i}.txt", "w")
    subprocess.run(
        [
            f"{fsl_dir}/bin/std2imgcoord",
            "-std",
            f"{datadir}/{all_nii[datadir][0]}",
            "-img",
            f"{datadir}/{all_nii[datadir][i]}",
            f"{datadir}/tmp/coord_tmp{i}.txt",
            "-vox",
        ],
        check=True,
        stdout=f,
    )

    new_translations = []
    with open(f"{datadir}/tmp/trans_tmp{i}.txt", "r") as file:
        for line in file:
            new_translations = line.strip("\n").split("  ")
    with open(f"{datadir}/tmp/trans_tmp{i}.txt", "w") as csvfile:
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
    out_names = []
    # First entry is 'registered' to itself
    original_omats.append(xp.array([0, 0, 0, 0, 0, 0]))
    omats.append(xp.array([0, 0, 0, 0, 0, 0]))
    for data_directory in all_nii:
        if not os.path.exists(f"{data_directory}/tmp"):
            os.mkdir(f"{data_directory}/tmp")
        dir_len = len(all_nii[data_directory])
        if cur_dir == data_directory:
            start_idx = 1
        else:
            start_idx = 0

        print(f"Running FLIRT on {data_directory}")
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
                btr.inputs.in_file = (
                    f"{data_directory}/{all_nii[data_directory][i]}"
                )
                btr.inputs.output_type = "NIFTI"
                btr.inputs.out_file = f"{data_directory}/tmp/tmp.nii"
                res = btr.run()
                if res.runtime.returncode != 0:
                    print(
                        f'Error in FSL bet command: \'{fsl_dir}/bin/bet \
                        "{data_directory}/{all_nii[data_directory][i]}" "{data_directory}/tmp/tmp.nii"\'\
                        , check there are no spaces in path'
                    )
                    exit(0)
            else:
                os.system(
                    f"cp {data_directory}/{all_nii[data_directory][i]} {data_directory}/tmp/tmp.nii"
                )

            flt = fsl.FLIRT(
                bins=256,
                dof=6,
                cost_func=cost_func,
                uses_qform=True,
                terminal_output="allatonce",
            )
            flt.inputs.in_file = f"{data_directory}/tmp/tmp.nii"
            flt.inputs.reference = f"{cur_dir}/tmp/ref.nii"
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.out_matrix_file = f"{data_directory}/tmp/tmp{i}.txt"
            flt.inputs.out_file = f"{data_directory}/tmp/reg{i}.nii.gz"
            flt.inputs.searchr_x = [-90, 90]
            flt.inputs.searchr_y = [-90, 90]
            flt.inputs.searchr_z = [-90, 90]
            flt.inputs.interp = "trilinear"
            res = flt.run()
            if res.runtime.returncode != 0:
                print(f"Error in FLIRT command: '{flt.cmdline}'")
                exit(0)

            # This will use avscale to get real world co-ords
            # out of FLIRT
            f = open(f"{data_directory}/tmp/avs.txt", "w")
            avscale = fsl.AvScale(all_param=True, terminal_output="allatonce")
            avscale.inputs.mat_file = f"{data_directory}/tmp/tmp{i}.txt"
            avscale.inputs.ref_file = f"{data_directory}/tmp/reg{i}.nii.gz"
            res = avscale.run()
            if res.runtime.returncode != 0:
                print("Error in AVScale command")
                exit(0)
            avs_str = str(res.runtime.stdout)
            flt = fsl.FLIRT(
                cost_func=cost_func,
                terminal_output="allatonce",
            )
            flt.inputs.in_file = f"{data_directory}/tmp/reg{i}.nii.gz"
            flt.inputs.reference = f"{cur_dir}/tmp/ref.nii"
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.schedule = f"{fsl_dir}/etc/flirtsch/measurecost1.sch"
            flt.inputs.in_matrix_file = f"{data_directory}/tmp/tmp{i}.txt"
            flt.inputs.out_matrix_file = (
                f"{data_directory}/tmp/reg{i}_flirt.mat"
            )
            flt.inputs.out_file = f"{data_directory}/tmp/reg{i}.nii.gz"
            out_names.append(f"{data_directory}/tmp/reg{i}.nii.gz")

            res = flt.run()
            cost_str = str(res.runtime.stdout)
            cost_val = float(cost_str.split()[0])
            if res.runtime.returncode != 0:
                print(f"Error in FLIRT command: '{flt.cmdline}'")
                exit(0)
            try:
                original_omats.append(omat.read_avs(avs_str, cost_val))
                tmp_omat = omat.read_tmp_trans(
                    f"{data_directory}/tmp/tmp{i}.txt"
                )
                original_omats[-1][0] = tmp_omat[0][3]
                original_omats[-1][1] = tmp_omat[1][3]
                original_omats[-1][2] = tmp_omat[2][3]
                omats.append(original_omats[-1])
            except IndexError:
                logging.debug(
                    f"{data_directory}/tmp/tmp{i}.txt does not contain omat data"
                )

            progress.printProgressBar(
                i + 1,
                dir_len,
                prefix="Progress:",
                suffix="Complete",
                length=50,
            )
    return omats, original_omats, out_names


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
        logging.debug(f"Verbosity: {verbose}")

    data_dirs = []
    if dname:
        for directory in dname:
            data_dirs.append(os.path.abspath(directory))
    else:
        data_dirs.append(os.getcwd())

    # Check input files and get the baseline file to register against
    if fname:
        logging.debug(f"Checking file {fname}")
        if os.path.isfile(os.path.abspath(fname)):
            logging.debug(f"Opening file {fname}")
            cur_dir = os.path.dirname(os.path.abspath(fname))
            all_nii = {}
            n_nii = 0
            for data_directory in data_dirs:
                all_nii[data_directory] = get_nii(data_directory, max_images)
                n_nii += len(all_nii[data_directory])
        else:
            logging.debug(f"!!! {fname} is not a file. !!!\nExiting...")
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), fname
            )
    else:
        cur_dir = os.getcwd()
        all_nii = {}
        all_nii[data_dirs[0]] = get_nii(data_dirs[0], max_images)
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

    logging.debug(f"FSL Base Dir: {fsl_dir}")

    if not os.path.exists(f"{cur_dir}/tmp"):
        os.mkdir(f"{cur_dir}/tmp")
    # Brain extract the reference image
    if extraction:
        btr = fsl.BET()
        btr.inputs.in_file = fname
        btr.inputs.output_type = "NIFTI"
        btr.inputs.out_file = f"{cur_dir}/tmp/ref.nii"
        res = btr.run()
        if res.runtime.returncode != 0:
            print(
                f'Error in FSL bet command: \'{fsl_dir}/bin/bet \
                "{fname}" "{cur_dir}/tmp/ref.nii"\'\
                , check there are no spaces in path'
            )
            exit(0)
    else:
        os.system(f"cp {fname} {cur_dir}/tmp/ref.nii")

    omats, original_omats, out_paths = run_flirt(
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
        logging.debug(f"Saving to {oname}")
        omat.reg_to_csv(omats, os.path.join(data_dirs[0], oname))
        omat.avs_to_csv(
            original_omats,
            os.path.join(data_dirs[0], f"original_{oname}"),
        )
    else:
        # Save to out.nii
        logging.debug("Saving to out.csv")
        if not os.path.exists(f"{data_dirs[0]}/results"):
            os.mkdir(f"{data_dirs[0]}/results")
        omat.reg_to_csv(
            omats,
            os.path.join(os.path.join(data_dirs[0], "results"), "out.csv"),
        )
        omat.avs_to_csv(
            original_omats,
            os.path.join(
                os.path.join(data_dirs[0], "results"), "original_out.csv"
            ),
        )

    make_gif(out_paths, data_dirs[0])

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
        logging.debug(f"Verbosity: {verbose}")
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
        logging.debug(f"Opening file {first_file}")
        cur_dir = os.path.dirname(os.path.abspath(first_file))
        all_nii = {}
        n_nii = 0
        for data_directory in data_dirs:
            all_nii[data_directory] = get_nii(data_directory)
            n_nii += len(all_nii[data_directory])
            all_inputs = get_inputs(n_nii, input_schema)
    else:
        logging.debug(f"!!! {first_file} is not a file. !!!\nExiting...")
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

    logging.debug(f"FSL Base Dir: {fsl_dir}")

    for data_directory in all_nii:
        dir_len = len(all_nii[data_directory])

        print(f"Applying FLIRT Transform on {data_directory}")
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

        if not os.path.exists(f"{data_directory}/tmp"):
            os.mkdir(f"{data_directory}/tmp")
        if not os.path.exists(f"{data_directory}/FLIRT_out"):
            os.mkdir(f"{data_directory}/FLIRT_out")
        for i in range(start_idx, dir_len):
            make_coords(data_directory, all_inputs, all_nii, fsl_dir, i)
            # apply the transform
            flt = fsl.FLIRT(apply_xfm=True, terminal_output="allatonce")
            flt.inputs.in_file = (
                f"{data_directory}/{all_nii[data_directory][i]}"
            )
            flt.inputs.reference = (
                f"{data_directory}/{all_nii[data_directory][0]}"
            )
            flt.inputs.output_type = "NIFTI_GZ"
            flt.inputs.schedule = f"{fsl_dir}/etc/flirtsch/measurecost1.sch"
            flt.inputs.in_matrix_file = (
                f"{data_directory}/tmp/trans_tmp{i}.txt"
            )
            flt.inputs.out_file = f"{data_directory}/FLIRT_out/out_{i}.nii.gz"
            res = flt.run()
            if res.runtime.returncode != 0:
                print(f"Error in FLIRT command: '{flt.cmdline}'")
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


def get_gif_slices(image):
    """Gets 3 orthogonal slices that show how good the registration is

    Args:
        image (nb.NiftiImage): the image to get slices from

    Returns:
        (np.array): the three slices
    """
    xp = gpopt.array_module("cupy")
    array = image.get_fdata()
    shape = xp.shape(array)
    mid_x = int(xp.floor(shape[0] / 2))
    mid_y = int(xp.floor(shape[1] / 2))
    mid_z = int(xp.floor(shape[2] / 2))
    slices = [
        xp.flipud(array[mid_x, :, :]),
        array[:, mid_y, :],
        xp.rot90(array[:, :, mid_z]),
    ]
    return slices


def make_gif(img_paths, out_path):

    slices = []
    for path in img_paths:
        img = nb.load(path)
        slices.append(get_gif_slices(img))

    start_time = time.time()
    if not os.path.exists(out_path + os.sep + "figures"):
        os.makedirs(out_path + os.sep + "figures")
    if not os.path.exists(out_path + os.sep + "tmp"):
        os.makedirs(out_path + os.sep + "tmp")
    gif_path = figstring.figstring("recon", path=out_path, ext="gif")
    fig, axes = plt.subplots(1, 3)
    # axes.axis("off")
    axes = axes.ravel()
    ims = []
    im1 = axes[0].imshow(
        slices[0][0],
        cmap="gray",
        aspect="auto",
        interpolation="none",
    )
    axes[0].axis("off")
    im2 = axes[1].imshow(
        slices[0][1],
        cmap="gray",
        aspect="auto",
        interpolation="none",
    )
    axes[1].axis("off")
    im3 = axes[2].imshow(
        slices[0][2],
        cmap="gray",
        aspect="auto",
        interpolation="none",
    )
    axes[2].axis("off")
    im = [im1, im2, im3]
    ims.append(im)

    def gif_update(slice):
        im1.set_data(slice[0])
        im2.set_data(slice[1])
        im3.set_data(slice[2])
        fig.canvas.draw_idle()
        m = [im1, im2, im3]
        return im

    ani = FuncAnimation(fig, gif_update, frames=slices, blit=True)
    ani.save(gif_path, writer=PillowWriter(fps=3))
    optimize(gif_path)
    total_time = time.gmtime((time.time() - start_time))
    print(f"Gif generated in in {time.strftime('%Hh%Mm%Ss', total_time)}")
