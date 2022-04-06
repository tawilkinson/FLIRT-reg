import os
from datetime import datetime


def figstring(name, path=None, ext=None):
    if path:
        base_path = os.path.join(path, "figures")
    else:
        base_path = os.path.join(os.getcwd(), "figures")

    date_path = os.path.join(base_path, datetime.today().strftime("%Y-%m-%d"))
    timestamp = f"{datetime.today().strftime('%H-%M-%S')}"

    if not os.path.isdir(base_path):
        os.mkdir(base_path)
    if not os.path.isdir(date_path):
        os.mkdir(date_path)

    if ext:
        if ext[0] == ".":
            ext = ext[1:]
        fig_str = f"{date_path}{os.sep}{timestamp}-{name}.{ext}"
    else:
        fig_str = f"{date_path}{os.sep}{timestamp}-{name}"
    return fig_str
