#!/usr/bin/env python3
"""
Freeze the conda environment.yml

Using conda-lock

Usage:

python freeze.py [3.8]
"""

import os
import pathlib
import shutil
import sys
from argparse import ArgumentParser
from datetime import datetime
from subprocess import check_call

from ruamel.yaml import YAML

HERE = pathlib.Path(os.path.dirname(os.path.abspath(__file__)))

ENV_FILE = HERE / "environment.yml"
FROZEN_FILE_T = os.path.splitext(ENV_FILE)[0] + "-{platform}.lock"

ENV_FILE_T = HERE / "environment.py-{py}.yml"

yaml = YAML(typ="rt")


def freeze(env_file, frozen_file, platform="linux-64"):
    """Freeze a conda environment

    By running:

        conda-lock --mamba --platform=linux-64 -f environment.yml

    Result will be stored in frozen_file
    """
    frozen_dest = HERE / frozen_file

    if frozen_dest.exists():
        with frozen_dest.open("r") as f:
            line = f.readline()
            if "GENERATED" not in line:
                print(
                    f"{frozen_file.relative_to(HERE)} not autogenerated, not refreezing"
                )
                return
    print(f"Freezing {env_file} -> {frozen_file}")

    # FIXME: conda-lock 0.8 requires {platform} in template
    # https://github.com/conda-incubator/conda-lock/pull/78
    frozen_template = str(frozen_dest) + ".{platform}"
    frozen_tempfile = pathlib.Path(frozen_template.format(platform=platform))

    check_call(
        [
            "conda-lock",
            # FIXME: adopt micromamba after ordering is fixed
            # https://github.com/conda-incubator/conda-lock/issues/79
            "--mamba",
            "--kind=explicit",
            f"--platform={platform}",
            f"--filename-template={frozen_template}",
            f"--file={env_file}",
        ]
    )

    with frozen_dest.open("w") as f:
        f.write(
            f"# AUTO GENERATED FROM {env_file.relative_to(HERE)}, DO NOT MANUALLY MODIFY\n"
        )
        f.write(f"# Frozen on {datetime.utcnow():%Y-%m-%d %H:%M:%S UTC}\n")
        with frozen_tempfile.open() as temp:
            f.write(temp.read())

    os.remove(frozen_tempfile)


def set_python(py_env_file, py):
    """Set the Python version in an env file"""
    if os.path.exists(py_env_file):
        # only clobber auto-generated files
        with open(py_env_file) as f:
            text = f.readline()
            if "GENERATED" not in text:
                return

    print(f"Regenerating {py_env_file} from {ENV_FILE}")
    with open(ENV_FILE) as f:
        env = yaml.load(f)
    for idx, dep in enumerate(env["dependencies"]):
        if dep.split("=")[0] == "python":
            env["dependencies"][idx] = f"python={py}.*"
            break
    else:
        raise ValueError(f"python dependency not found in {env['dependencies']}")
    # update python dependency
    with open(py_env_file, "w") as f:
        f.write(
            f"# AUTO GENERATED FROM {ENV_FILE.relative_to(HERE)}, DO NOT MANUALLY MODIFY\n"
        )
        f.write(f"# Generated on {datetime.utcnow():%Y-%m-%d %H:%M:%S UTC}\n")
        yaml.dump(env, f)


if __name__ == "__main__":
    parser = ArgumentParser(
        description=(
            "Refreeze conda environments. See "
            "https://repo2docker.readthedocs.io/en/latest/contributing/tasks.html#update-and-freeze-buildpack-dependencies"
        )
    )
    parser.add_argument(
        "py",
        nargs="*",
        help="Python version(s) to update and freeze",
        default=("3.7", "3.8", "3.9", "3.10"),
    )
    parser.add_argument(
        "platform",
        nargs="*",
        help="Platform(s) to update and freeze",
        default=("linux-64", "linux-aarch64"),
    )
    args = parser.parse_args()
    default_py = "3.7"
    for py in args.py:
        for platform in args.platform:
            env_file = pathlib.Path(str(ENV_FILE_T).format(py=py))
            set_python(env_file, py)
            frozen_file = pathlib.Path(os.path.splitext(env_file)[0] + f"-{platform}.lock")
            freeze(env_file, frozen_file, platform)
            if py == default_py:
                shutil.copy(frozen_file, FROZEN_FILE_T.format(platform=platform))
