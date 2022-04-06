import math
import csv
import gpuoptional.gpuoptional as gpopt

# Converts the output matrix from FLIRT
# Based on a MATLAB script by Dr Shaihan Malik
# (https://github.com/shaihanmalik)


def read_omat(fname):
    """
    Read an FSL/FLIRT omat file
    """
    xp = gpopt.array_module("cupy")
    in_omat = []
    with open(fname, "r") as file:
        for line in file:
            line_in = line.strip("\n").split("  ")[:-1]
            try:
                line_in = [float(f) for f in line_in]
            except ValueError:
                return xp.array(0)
            in_omat.append(line_in)
    in_omat = xp.array(in_omat)
    return in_omat


def read_tmp_trans(fname):
    """
    Read an FSL/FLIRT temporary translations file
    """
    xp = gpopt.array_module("cupy")
    in_omat = []
    with open(fname, "r") as file:
        for line in file:
            line_in = line.strip("\n").split("  ")[:-1]
            try:
                line_in = [float(f) for f in line_in]
            except ValueError:
                return xp.array(0)
            in_omat.append(line_in)
    in_omat = xp.array(in_omat)
    return in_omat


def read_avs(avs_str, cost_val=0):
    """
    Read FSL/FLIRT avscale output
    """
    xp = gpopt.array_module("cupy")
    in_omat = [0, 0, 0, 0, 0, 0, 0]
    for line in avs_str.split("\n"):
        if "Rotation Angles (x,y,z) [rads]" in line:
            split_ln = line.split(" ")
            in_omat[3] = float(split_ln[5])
            in_omat[4] = float(split_ln[6])
            in_omat[5] = float(split_ln[7])
        elif "Translations (x,y,z) [mm]" in line:
            split_ln = line.split(" ")
            in_omat[0] = float(split_ln[4])
            in_omat[1] = float(split_ln[5])
            in_omat[2] = float(split_ln[6])
    if cost_val:
        in_omat[6] = float(cost_val)
    in_omat = xp.array(in_omat)
    return in_omat


def read_avs_txt(fname, cost_val=0):
    """
    Read FSL/FLIRT avscale output file
    """
    xp = gpopt.array_module("cupy")
    in_omat = [0, 0, 0, 0, 0, 0, 0]
    with open(fname, "r") as file:
        for line in file:
            if "Rotation Angles (x,y,z) [rads]" in line:
                split_ln = line.split(" ")
                in_omat[3] = float(split_ln[5])
                in_omat[4] = float(split_ln[6])
                in_omat[5] = float(split_ln[7])
            elif "Translations (x,y,z) [mm]" in line:
                split_ln = line.split(" ")
                in_omat[0] = float(split_ln[4])
                in_omat[1] = float(split_ln[5])
                in_omat[2] = float(split_ln[6])
    if cost_val:
        in_omat[6] = float(cost_val)
    in_omat = xp.array(in_omat)
    return in_omat


def convert_omat(omat, rads=False):
    """
    Converts omat into 3 translations in mm and
    3 rotations in degrees
    """
    xp = gpopt.array_module("cupy")
    # omat is a 4x4 matrix
    # the x, y, z translations are the final column
    t = omat[0:3, 3]

    # Arbitrary rot matrix is usually of the form:
    # R11, R12, R13
    # R21, R22, R23
    # R31, R32, R33

    # if R31 == +/- 1 we need to do more stuff

    # Rotations angles for x, y, z are represented by
    # psi, theta, phi respectively
    # Figuring out theta
    # theta is either -arcsin(R31) or pi + arcsin(R31)
    theta1 = -math.asin(omat[2, 0])
    # theta2 = math.pi + math.asin(omat[2, 0])
    # Figuring out psi
    psi1 = math.atan2(
        (omat[2, 1] / math.cos(theta1)), (omat[2, 2] / math.cos(theta1))
    )
    # psi2 = math.atan2(
    #    (omat[2, 1] / math.cos(theta2)), (omat[2, 2] / math.cos(theta2))
    # )
    # Figuring out phi
    phi1 = math.atan2(
        (omat[1, 0] / math.cos(theta1)), (omat[0, 0] / math.cos(theta1))
    )
    # phi2 = math.atan2(
    #    (omat[1, 0] / math.cos(theta2)), (omat[0, 0] / math.cos(theta2))
    # )
    # rotations
    if rads:
        rx = psi1
        ry = theta1
        rz = phi1
    else:
        rx = math.degrees(psi1)
        ry = math.degrees(theta1)
        rz = math.degrees(phi1)
    r = xp.array([rx, ry, rz])

    # registration parameters are the 3 translation parameters
    # and then the three rotation parameters in degrees
    reg_pars = xp.concatenate((t, r))

    return reg_pars


def get_reg_str(reg, rads=False):
    """
    Generates a display string for a single reg entry
    """
    reg_str = f"X: {reg[0]} mm, Y: {reg[1]} mm, Z: {reg[2]} mm\n"
    if rads:
        reg_str += f"RX: {reg[3]} rad, RY: {reg[4]} rad, RZ: {reg[5]} rad"
    else:
        reg_str += f"RX: {reg[3]}°, RY: {reg[4]}°, RZ: {reg[5]}°"
    return reg_str


def orig_to_csv(original_omats, fname="out.csv"):
    """
    Outputs a list of registrations to csv file
    """
    with open(fname, "w", newline="\n") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=",")
        for reg in original_omats:
            regwriter.writerow(
                [
                    reg[0, 0],
                    reg[0, 1],
                    reg[0, 2],
                    reg[0, 3],
                    reg[1, 0],
                    reg[1, 1],
                    reg[1, 2],
                    reg[1, 3],
                    reg[2, 0],
                    reg[2, 1],
                    reg[2, 2],
                    reg[2, 3],
                    reg[3, 0],
                    reg[3, 1],
                    reg[3, 2],
                    reg[3, 3],
                ]
            )


def avs_to_csv(original_omats, fname="avs.csv"):
    """
    Outputs a list of avscale registrations to csv file
    """
    with open(fname, "w", newline="\n") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=",")
        for reg in original_omats:
            if len(reg) > 6:
                regwriter.writerow(
                    [
                        reg[0],
                        reg[1],
                        reg[2],
                        reg[3],
                        reg[4],
                        reg[5],
                        reg[6],
                    ]
                )
            else:
                regwriter.writerow(
                    [reg[0], reg[1], reg[2], reg[3], reg[4], reg[5], 0]
                )


def reg_to_csv(omats, fname="out.csv", verbose=False):
    """
    Outputs a list of registrations to csv file
    """
    with open(fname, "w", newline="\n") as csvfile:
        regwriter = csv.writer(csvfile, delimiter=",")
        for reg in omats:
            if verbose:
                regwriter.writerow(
                    [
                        "x",
                        reg[0],
                        "y",
                        reg[1],
                        "z",
                        reg[2],
                        "Rx",
                        reg[3],
                        "Ry",
                        reg[4],
                        "Rz",
                        reg[5],
                    ]
                )
            else:
                regwriter.writerow(
                    [
                        reg[0],
                        reg[1],
                        reg[2],
                        reg[3],
                        reg[4],
                        reg[5],
                    ]
                )


def csv_to_reg(fname="out.csv"):
    """
    Reads a list of registrations from a csv file
    """
    xp = gpopt.array_module("cupy")
    omats = []
    with open(fname, "r", newline="\n") as csvfile:
        regreader = csv.reader(csvfile, delimiter=",")
        for row in regreader:
            if row[0] == "x":
                try:
                    row_vals = xp.array(
                        [
                            float(row[1]),
                            float(row[3]),
                            float(row[5]),
                            float(row[7]),
                            float(row[9]),
                            float(row[11]),
                        ]
                    )
                    omats.append(row_vals)
                except IndexError:
                    print("Not a valid omat row, is this a valid file?")
            else:
                try:
                    row_vals = xp.array(
                        [
                            float(row[0]),
                            float(row[1]),
                            float(row[2]),
                            float(row[3]),
                            float(row[4]),
                            float(row[5]),
                        ]
                    )
                    omats.append(row_vals)
                except IndexError:
                    print("Not a valid omat row, is this a valid file?")
    if len(omats) == 0:
        print(f"!!! No omat rows found in {fname}. !!!\nExiting...")
        exit(0)

    return omats
