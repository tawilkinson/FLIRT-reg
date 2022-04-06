import argparse
import os
import time
import nibabel as nib


def read_nii_hdr():
    # Initialise simple timer
    start_time = time.time()
    """
    A simple header reader for NII files
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        help="output filename. If provided does not print but saves to file.",
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

    if args.input:
        img = nib.load(args.input)
        hdr = img.header
        if args.output:
            filename = os.path.join(os.getcwd(), args.output)
            with open(filename, "w") as f:
                f.write(str(hdr))
            if args.verbose:
                print(f"Saving NII header to {filename}")
        else:
            print(hdr)
    else:
        print("Please select an input file")
        exit(0)

    if args.verbose:
        total_time = time.gmtime((time.time() - start_time))
        print(f"Header processed in {time.strftime('%Hh%Mm%Ss', total_time)}")
