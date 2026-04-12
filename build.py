"""Repository-local wrapper for ``python -m build``.

The published package does not depend on this module. It exists only so development and
validation workflows can run the standard ``python -m build`` command from the repository
root even when an embedded Windows Python distribution reports a broken executable path for
subprocess-based backend hooks.
"""

from __future__ import annotations

import sys
from importlib.machinery import PathFinder
from importlib.util import module_from_spec
from pathlib import Path
from types import ModuleType


def _repair_embedded_windows_executable() -> bool:
    """Repair broken executable attributes reported by some embedded Windows launchers."""

    if sys.platform != "win32":
        return False

    executable = getattr(sys, "executable", "")
    executable_path = Path(executable)
    if executable_path.is_file() or not executable_path.is_dir():
        return False

    for candidate in (
        executable_path.parent / "python.exe",
        executable_path / "bin" / "python.exe",
    ):
        if candidate.is_file():
            fixed_path = str(candidate)
            sys.executable = fixed_path
            if hasattr(sys, "_base_executable"):
                sys._base_executable = fixed_path
            return True
    return False


def _load_real_build_package() -> ModuleType:
    """Load the installed ``build`` package without recursing into this wrapper module."""

    repo_root = Path(__file__).resolve().parent
    search_path = [entry for entry in sys.path if entry and Path(entry).resolve() != repo_root]
    spec = PathFinder.find_spec("build", search_path)
    if spec is None or spec.loader is None or spec.submodule_search_locations is None:
        raise ModuleNotFoundError(
            "The 'build' package is not installed. Install the development dependencies first."
        )

    module = module_from_spec(spec)
    sys.modules["build"] = module
    spec.loader.exec_module(module)
    return module


def _load_real_build_main(package: ModuleType) -> ModuleType:
    """Load the installed ``build.__main__`` module for delegation."""

    assert package.__spec__ is not None
    package_paths = list(package.__spec__.submodule_search_locations or [])
    spec = PathFinder.find_spec("build.__main__", package_paths)
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError("The installed 'build' package is missing its __main__ module.")

    module = module_from_spec(spec)
    sys.modules["build.__main__"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    """Delegate to the installed ``build`` package after compatibility fixes."""

    repaired_embedded_launcher = _repair_embedded_windows_executable()
    package = _load_real_build_package()
    main_module = _load_real_build_main(package)
    cli_args = list(sys.argv[1:])
    if repaired_embedded_launcher and "--no-isolation" not in cli_args and "-n" not in cli_args:
        cli_args.insert(0, "--no-isolation")
    result = main_module.main(cli_args)
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
