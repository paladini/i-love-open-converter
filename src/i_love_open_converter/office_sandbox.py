"""Constrain the Office subprocess before handing control to LibreOffice on Linux."""

from __future__ import annotations

import ctypes
import os
import resource
import sys
from pathlib import Path

_CREATE_RULESET = 444
_ADD_RULE = 445
_RESTRICT_SELF = 446
_VERSION = 1
_PATH_BENEATH = 1
_NO_NEW_PRIVS = 38
_READ_EXECUTE = (1 << 0) | (1 << 2) | (1 << 3)


class Ruleset(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneath(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


def restrict(root: Path, *, allow_app: bool = False, allow_tmp: bool = True) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(_CREATE_RULESET, 0, 0, _VERSION)
    if abi < 1:
        raise OSError(ctypes.get_errno(), "Landlock unavailable")
    rights = (1 << 13) - 1
    if abi >= 2:
        rights |= 1 << 13
    if abi >= 3:
        rights |= 1 << 14
    ruleset = Ruleset(rights)
    fd = libc.syscall(_CREATE_RULESET, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "Landlock ruleset unavailable")
    try:
        paths = [(root, rights), (Path("/dev/null"), (1 << 1) | (1 << 2))]
        if allow_tmp:
            paths.append((Path("/tmp"), (1 << 9) | (1 << 5)))
        paths += (
            [(Path("/app"), _READ_EXECUTE), (Path(sys.prefix), _READ_EXECUTE)]
            if allow_app
            else []
        ) + [
            (Path(item), _READ_EXECUTE)
            for item in ("/usr", "/lib", "/lib64", "/etc", "/dev", "/proc/self")
        ]
        for path, permitted in paths:
            if not path.exists():
                continue
            path_fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathBeneath(permitted, path_fd)
                if libc.syscall(_ADD_RULE, fd, _PATH_BENEATH, ctypes.byref(rule), 0) < 0:
                    raise OSError(ctypes.get_errno(), "Landlock rule failed")
            finally:
                os.close(path_fd)
        if libc.prctl(_NO_NEW_PRIVS, 1, 0, 0, 0) or libc.syscall(_RESTRICT_SELF, fd, 0):
            raise OSError(ctypes.get_errno(), "Landlock restriction failed")
    finally:
        os.close(fd)


if __name__ == "__main__":
    try:
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
        restrict(Path(sys.argv[1]))
    except (OSError, ValueError):
        sys.exit(77)
    os.execv(sys.argv[2], sys.argv[2:])
