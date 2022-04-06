import argparse
import time
from flirt_reg.reg import flirt_reg


def main():
    # Initialise simple timer
    start_time = time.time()
    """
    A simple runner for the program with arguments
    """
    # execute only if run as a script
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--filename",
        help="input image filename. Default: searches \
                    current directory for .nii.",
    )
    parser.add_argument(
        "-d",
        "--dirname",
        nargs="+",
        help="input directory name(s). Default: searches \
                    same directory for as filename for .nii.",
    )
    parser.add_argument(
        "-n",
        "--num",
        help="number of images. Default: All images in \
                    directory.",
        type=int,
    )
    parser.add_argument(
        "-o", "--output", help="output filename. Default: out.nii."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="prints debugging information. Default: false.",
    )
    parser.add_argument(
        "-r",
        "--radians",
        action="store_true",
        help="output in radians not degrees. Default: false.",
    )
    parser.add_argument(
        "-b",
        "--no-brain-extract",
        action="store_false",
        help="Turn off brain extraction. Default: false.",
    )
    parser.add_argument(
        "-c",
        "--cost",
        help="Select a cost function from the following list:\
            [mutualinfo,corratio,normcorr,normmi,leastsq,labeldiff,bbr]",
    )
    args = parser.parse_args()

    if args.cost:
        # Check for a resonable cost function
        cost_func_list = [
            "mutualinfo",
            "corratio",
            "normcorr",
            "normmi",
            "leastsq",
            "labeldiff",
            "bbr",
        ]
        if args.cost in cost_func_list:
            cost_func = args.cost
        else:
            print(
                "Not a valid cost function, please use one of:\
                 [mutualinfo,corratio,normcorr,normmi,leastsq,labeldiff,bbr]"
            )
            exit(0)
    else:
        cost_func = "leastsq"

    # call the flirt_reg function with cmd line args
    omats = flirt_reg.flirt_reg(
        fname=args.filename,
        oname=args.output,
        verbose=args.verbose,
        max_images=args.num,
        dname=args.dirname,
        rads=args.radians,
        extraction=args.no_brain_extract,
        cost_func=cost_func,
    )

    if args.verbose:
        total_time = time.gmtime((time.time() - start_time))
        print(f"Pipeline complete in {time.strftime('%Hh%Mm%Ss', total_time)}")


if __name__ == "__main__":
    main()
