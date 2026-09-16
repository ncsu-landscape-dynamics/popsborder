# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC

from __future__ import annotations

import ast
import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from math import isinf
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
)

import numpy as np
import pandas as pd
from numpy.random import Generator
from .general_utils import get_range_key

# === LOGGING ===
logger = logging.getLogger(__name__)

# === CONFIG ===
# Name of the conda environment that contains R + required R packages.
# Can be overridden by setting the environment variable POPS_R_CONDA_ENV.
CONDA_ENV_NAME: Optional[str] = os.getenv("POPS_R_CONDA_ENV", "rbb")
REPO_NAME = "plant-inspection-station-simulation"
R_SCRIPT_REL = Path("slippage_model_utils") / "clarke_bb_model.R"


class OptimResult(TypedDict):
    """Typed dictionary representation of an R optim() result.

    Attributes:
        value: Optimized objective function value.
        par: Tuple of optimized parameters (length 2).
        counts: Tuple with number of function evaluations and a status string.
        convergence: 0 on success, non-zero on convergence issues.
        message: Additional optimizer messages (often empty).
        hessian: 2x2 Hessian matrix as nested tuples.
    """

    value: float
    par: Tuple[float, float]  # two parameters
    counts: Tuple[int, str]  # R's optim: (fn_evals, "NA")
    convergence: int  # 0 means success
    message: Mapping[str, Any]  # R often returns an empty list/dict here
    hessian: Tuple[Tuple[float, float], Tuple[float, float]]  # 2x2 matrix


#### Repo & script path utilities ####
def find_repo_root() -> Optional[Path]:
    """Find the repository root directory.

    The search starts from the current file's directory and walks up the
    parent chain. The repo root is identified as the first directory whose
    name matches ``REPO_NAME`` or that contains a ``.git`` subdirectory.

    Returns:
        Path to the repository root if found, otherwise None.
    """
    start = Path(__file__).resolve()
    for parent in [start, *start.parents]:
        if parent.name == REPO_NAME or (parent / ".git").exists():
            return parent
    return None


def get_script_path(relative: Path, *, repo_root: Optional[Path] = None) -> Path:
    """Resolve an R script path relative to the repository root.

    Args:
        relative: Path to the R script, relative to the repo root.
        repo_root: Optional explicit repo root. If None, this is discovered
            via :func:`find_repo_root`.

    Returns:
        Absolute path to the script.

    Raises:
        FileNotFoundError: If the script cannot be located.
    """
    # Try explicit root first
    if repo_root:
        candidate = (repo_root / relative).resolve()
        if candidate.exists():
            return candidate

    # Auto-detect root
    auto_root = find_repo_root()
    if auto_root:
        candidate = (auto_root / relative).resolve()
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Could not locate '{relative.name}'. "
        f"Searched from repo_root={repo_root or 'auto-detected root'}; "
        f"expected relative path: {relative}"
    )


def get_r_script_path() -> Path:
    """Resolve the path to ``clarke_bb_model.R`` using repo-root discovery.

    Returns:
        Path to the R script.

    Raises:
        FileNotFoundError: If the script cannot be found.
    """
    return get_script_path(R_SCRIPT_REL)


#### Conda / R discovery utilities ####

def _find_conda_exe() -> Optional[Path]:
    """Locate the conda executable.

    Search order:

    1. Environment variables ``POPS_CONDA_EXE`` or ``CONDA_EXE``.
    2. The system PATH (using ``shutil.which``).
    3. Common Anaconda/Miniconda install locations.

    Returns:
        Path to the conda executable or None if not found.
    """
    # Explicit overrides
    for env_var in ("POPS_CONDA_EXE", "CONDA_EXE"):
        v = os.getenv(env_var)
        if v and Path(v).exists():
            return Path(v).resolve()

    # PATH
    which = shutil.which("conda.exe" if platform.system() == "Windows" else "conda")
    if which:
        return Path(which).resolve()

    # Common install locations
    candidates: list[Path] = []

    if platform.system() == "Windows":
        local_appdata = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        candidates += [
            Path(local_appdata) / "anaconda" / "Scripts" / "conda.exe",
            Path(local_appdata) / "anaconda3" / "Scripts" / "conda.exe",
            Path(local_appdata) / "miniconda3" / "Scripts" / "conda.exe",
            Path(local_appdata) / "Programs" / "anaconda" / "Scripts" / "conda.exe",
        ]
        candidates += [
            Path.home() / "anaconda" / "Scripts" / "conda.exe",
            Path.home() / "anaconda3" / "Scripts" / "conda.exe",
            Path.home() / "miniconda3" / "Scripts" / "conda.exe",
        ]
    else:
        candidates += [
            Path.home() / "anaconda" / "bin" / "conda",
            Path.home() / "anaconda3" / "bin" / "conda",
            Path.home() / "miniconda3" / "bin" / "conda",
            Path("/opt/anaconda/bin/conda"),
            Path("/opt/anaconda3/bin/conda"),
            Path("/usr/local/anaconda/bin/conda"),
            Path("/usr/local/anaconda3/bin/conda"),
        ]

    for c in candidates:
        if c.exists():
            return c.resolve()

    return None


def _find_conda_env_dir(env_name: str) -> Optional[Path]:
    """Locate the directory of a conda environment by name.

    Args:
        env_name: Name of the conda environment.

    Returns:
        Path to the environment directory, or None if not found.
    """
    # Explicit override
    override = os.getenv("POPS_CONDA_ENV_DIR")
    if override:
        override_path = Path(override)
        if override_path.exists() and override_path.is_dir():
            return override_path.resolve()

    conda_exe = _find_conda_exe()
    if not conda_exe:
        return None

    # Method 1: 'conda env list --json'
    try:
        result = subprocess.run(
            [str(conda_exe), "env", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30.0,
            check=True,
        )
        stdout = result.stdout.strip()
        json_start = stdout.find("{")
        json_end = stdout.rfind("}")
        if json_start != -1 and json_end != -1:
            json_str = stdout[json_start : json_end + 1]
            env_data = json.loads(json_str)

            # Check 'envs' list
            envs = env_data.get("envs", [])
            for env_path in envs:
                env_path_obj = Path(env_path)
                if env_path_obj.name == env_name:
                    return env_path_obj

            # Check 'envs_details'
            envs_details = env_data.get("envs_details", {})
            for env_path_str, details in envs_details.items():
                if details.get("name") == env_name:
                    env_path_obj = Path(env_path_str)
                    if env_path_obj.exists():
                        return env_path_obj

    except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
        pass

    # Method 2: 'conda info --envs'
    try:
        result = subprocess.run(
            [str(conda_exe), "info", "--envs"],
            capture_output=True,
            text=True,
            timeout=30.0,
            check=True,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            curr_env_name = parts[0]
            env_path_str = parts[-1]
            if curr_env_name == env_name:
                env_path_obj = Path(env_path_str)
                if env_path_obj.exists():
                    return env_path_obj

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    # Method 3: common env locations
    conda_root = conda_exe.parent.parent  # Scripts/bin -> conda root
    candidates = [
        conda_root / "envs" / env_name,
        Path.home() / ".conda" / "envs" / env_name,
        Path.home() / "anaconda3" / "envs" / env_name,
        Path.home() / "miniconda3" / "envs" / env_name,
    ]

    if platform.system() == "Windows":
        local_appdata = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        candidates += [
            Path(local_appdata) / "anaconda" / "envs" / env_name,
            Path(local_appdata) / "anaconda3" / "envs" / env_name,
            Path(local_appdata) / "miniconda3" / "envs" / env_name,
        ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            if platform.system() == "Windows":
                if (candidate / "Scripts" / "activate.bat").exists() or (candidate / "python.exe").exists():
                    return candidate
            else:
                if (candidate / "bin" / "activate").exists() or (candidate / "bin" / "python").exists():
                    return candidate

    return None


def _build_windows_r_env(env_dir: Path) -> dict[str, str]:
    """Build environment variables to run Rscript from a Windows conda env.

    Args:
        env_dir: Path to the conda environment directory.

    Returns:
        Dictionary of environment variables to use when launching Rscript.
    """
    env = os.environ.copy()
    prepend = [
        str(env_dir / "Library" / "bin"),
        str(env_dir / "Scripts"),
        str(env_dir),
    ]
    env["PATH"] = os.pathsep.join(prepend + [env.get("PATH", "")])
    env["R_HOME"] = str(env_dir / "Lib" / "R")
    return env


def _pick_rscript_command() -> tuple[list[str], dict[str, str]]:
    """Determine the command and environment for running Rscript.

    On Windows, this locates ``Rscript.exe`` inside the target conda
    environment and builds an appropriate PATH. On Unix-like systems,
    it uses ``conda run -n <env> Rscript``.

    Returns:
        Tuple ``(command_list, env_dict)`` where:
            * ``command_list`` is the base command to execute.
            * ``env_dict`` is the environment to use (empty dict indicates
              that ``conda run`` will manage the environment).

    Raises:
        RuntimeError: If the conda environment or Rscript cannot be located.
    """
    if not CONDA_ENV_NAME:
        raise RuntimeError(
            "CONDA_ENV_NAME is not set. "
            "Set POPS_R_CONDA_ENV to the name of a conda environment "
            "that contains R and required packages."
        )

    conda_exe = _find_conda_exe()

    if platform.system() == "Windows":
        env_dir = _find_conda_env_dir(CONDA_ENV_NAME)
        if not env_dir:
            available_envs = "(could not retrieve environment list)"
            if conda_exe:
                try:
                    result = subprocess.run(
                        [str(conda_exe), "env", "list"],
                        capture_output=True,
                        text=True,
                        timeout=30.0,
                    )
                    available_envs = result.stdout
                except Exception:
                    pass

            raise RuntimeError(
                f"Could not find conda environment '{CONDA_ENV_NAME}'.\n\n"
                f"Conda executable found at: {conda_exe}\n\n"
                f"Available environments:\n{available_envs}\n\n"
                "Please ensure the environment exists and try:\n"
                f"  conda activate {CONDA_ENV_NAME}\n"
                f"  conda list | findstr R\n\n"
                "Or set the environment path explicitly:\n"
                f"  set POPS_CONDA_ENV_DIR=C:\\path\\to\\envs\\{CONDA_ENV_NAME}"
            )

        rscript = env_dir / "Scripts" / "Rscript.exe"
        if not rscript.exists():
            raise RuntimeError(
                f"Rscript.exe not found in environment '{CONDA_ENV_NAME}'.\n"
                f"Expected at: {rscript}\n"
                f"Environment directory: {env_dir}\n\n"
                "Please ensure R is installed in the environment:\n"
                f"  conda activate {CONDA_ENV_NAME}\n"
                "  conda install r-base"
            )

        env = _build_windows_r_env(env_dir)
        return [str(rscript)], env

    # Unix-like: use conda run
    if not conda_exe:
        raise RuntimeError(
            "Could not locate conda executable. "
            "Ensure conda is installed and CONDA_EXE or POPS_CONDA_EXE is set "
            "if using nonstandard locations."
        )

    return [str(conda_exe), "run", "-n", CONDA_ENV_NAME, "Rscript"], {}


#### R subprocess helpers ####
def _run_rscript(
    cmd: list[str],
    script_path: str,
    arg: str,
    *,
    env: Optional[dict[str, str]] = None,
    timeout_sec: float = 120.0,
) -> subprocess.CompletedProcess[str]:
    """Run an R script with a single argument and common error handling.

    Args:
        cmd: Base command list for invoking Rscript (e.g., from
            :func:`_pick_rscript_command`).
        script_path: Full path to the R script.
        arg: Single string argument passed to the R script (JSON payload or
            file path).
        env: Optional environment variables for the subprocess.
        timeout_sec: Maximum time in seconds to allow the R script to run.

    Returns:
        CompletedProcess object representing the R subprocess.

    Raises:
        TimeoutError: If the R script exceeds ``timeout_sec``.
        subprocess.CalledProcessError: If the R script exits with non-zero
            return code.
    """
    subprocess_env = env if env else None

    try:
        proc: subprocess.CompletedProcess[str] = subprocess.run(
            cmd + [script_path, arg],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
            env=subprocess_env,
        )
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(
            f"R script '{script_path}' timed out after {timeout_sec}s. "
            f"Partial stdout: {e.output!r}, stderr: {e.stderr!r}"
        ) from e

    if proc.returncode != 0:
        # Let callers wrap this if they want more context
        raise subprocess.CalledProcessError(
            returncode=proc.returncode,
            cmd=proc.args,
            output=proc.stdout,
            stderr=proc.stderr,
        )

    return proc


def _parse_json_from_r_stdout(stdout: str) -> dict[str, Any]:
    """Extract the final JSON object from noisy R stdout.

    R often prints startup messages, warnings, and other text before or
    after the JSON payload. This helper searches from the end of stdout
    to find the last well-formed JSON object.

    Args:
        stdout: Raw stdout string emitted by the R subprocess.

    Returns:
        Parsed JSON object as a Python dictionary.

    Raises:
        ValueError: If no JSON-like object can be located.
    """
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    for ln in reversed(lines):
        if ln.startswith("{") and ln.endswith("}"):
            return json.loads(ln)

    start = stdout.rfind("{")
    end = stdout.rfind("}")
    if start != -1 and end != -1 and start < end:
        return json.loads(stdout[start : end + 1])

    raise ValueError("Expected JSON from R; nothing that looks like a JSON object was found.")


def _safe_parse_json_from_r_stdout(stdout: str, context: str) -> dict[str, Any]:
    """Parse JSON from R stdout with additional context in error messages.

    Args:
        stdout: Raw stdout string from the R subprocess.
        context: Human-readable description of the calling context.

    Returns:
        Parsed JSON object as a dictionary.

    Raises:
        ValueError: If JSON parsing fails; the error message includes a
            preview of stdout and the context string.
    """
    try:
        return _parse_json_from_r_stdout(stdout)
    except ValueError as e:
        preview = stdout[:500].replace("\n", "\\n")
        raise ValueError(
            f"Expected JSON from R ({context}); got (preview): {preview}"
        ) from e

#### Clark BB wrapper ####
def run_clarke_bb_group_model(
    ty: Sequence[int],
    b: int,
    B: int,
    Nbar: int,
    freq: Sequence[int],
    theta: float,
    R: int,
    startval: Sequence[float],
    se: bool,
    *,
    timeout_sec: float = 120.0,
) -> dict[str, Any]:
    """Run the Clarke beta-binomial group model via R and return results.

    The function constructs a JSON payload with model inputs, invokes
    ``clarke_bb_model.R`` through the configured conda-based R wrapper, and
    parses the resulting JSON.

    Args:
        ty: Sequence of unique counts of groups testing positive.
        b: Number of groups per consignment.
        B: Number of consignments.
        Nbar: Average items per group.
        freq: Sequence of frequencies corresponding to ``ty``.
        theta: Clustering hyperparameter (use ``np.inf`` for no extra clustering).
        R: Number of Monte Carlo or sensitivity runs.
        startval: Initial values for optimizer (e.g., [log-alpha, log-beta]).
        se: If True, request standard errors.
        timeout_sec: Maximum time allowed for the R script to complete.

    Returns:
        Dictionary parsed from R stdout, typically containing model
        parameters and diagnostics.

    Raises:
        FileNotFoundError: If the R script cannot be found.
        subprocess.CalledProcessError: If the R subprocess exits with
            non-zero status.
        TimeoutError: If R does not complete within ``timeout_sec``.
        ValueError: If stdout does not contain valid JSON in the expected
            format.
    """
    r_script_path_bb_cli = str(get_r_script_path())
    if not Path(r_script_path_bb_cli).exists():
        raise FileNotFoundError(f"R script not found: {r_script_path_bb_cli}")

    cmd, env = _pick_rscript_command()

    theta_json = None if isinf(float(theta)) else float(theta)

    payload: Dict[str, Any] = {
        "ty": [int(x) for x in ty],
        "b": int(b),
        "B": int(B),
        "Nbar": int(Nbar),
        "freq": [int(x) for x in freq],
        "theta": theta_json,
        "R": int(R),
        "startval": [float(x) for x in startval],
        "se": bool(se),
    }

    proc = _run_rscript(
        cmd,
        r_script_path_bb_cli,
        json.dumps(payload, allow_nan=False),
        env=env,
        timeout_sec=timeout_sec,
    )

    return _safe_parse_json_from_r_stdout(proc.stdout, "run_clarke_bb_group_model")


#### DataFrame serialization helpers ####
def _write_df_temp(
    df: pd.DataFrame,
    *,
    use_parquet: bool,
    temp_dir: str,
) -> str:
    """Write a DataFrame to a temporary file and return its path.

    Depending on ``use_parquet``, writes either a Parquet or CSV file into
    the provided temporary directory.

    Args:
        df: DataFrame to serialize.
        use_parquet: If True, write a ``.parquet`` file; otherwise write CSV.
        temp_dir: Directory in which to create the temporary file.

    Returns:
        Path to the temporary file as a string.
    """
    if use_parquet:
        tmp_file = tempfile.NamedTemporaryFile(
            suffix=".parquet",
            delete=False,
            dir=temp_dir,
        )
        tmp_file.close()
        df.to_parquet(tmp_file.name, engine="pyarrow", index=False)
    else:
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".csv",
            delete=False,
            newline="",
            encoding="utf-8",
            dir=temp_dir,
        )
        df.to_csv(tmp_file.name, index=False)
        tmp_file.close()
    return tmp_file.name


def _read_df_from_path(path: str) -> pd.DataFrame:
    """Read a DataFrame from a Parquet or CSV file.

    Args:
        path: Path to the file.

    Returns:
        DataFrame loaded from the given path.
    """
    if path.endswith(".parquet"):
        return pd.read_parquet(path, engine="pyarrow")
    return pd.read_csv(path)


#### R variable creator wrapper class for engineered features ####
class RVariableCreator:
    """Wrapper for calling R-based feature engineering functions.

    This class executes functions defined in ``variable_creator.R`` using
    the conda-based R wrapper infrastructure. It supports both simple
    JSON-based calls and DataFrame payloads via temporary files.
    """

    # Name of the R script (relative to repo root)
    R_SCRIPT_REL = Path("slippage_model_utils") / "variable_creator.R"

    def __init__(self, repo_root: Optional[Union[str, Path]] = None) -> None:
        """Initialize a new RVariableCreator.

        Args:
            repo_root: Root directory of the repository. If None, the root
                is auto-detected via :func:`find_repo_root`.
        """
        self.repo_root = Path(repo_root) if repo_root is not None else None

    def _get_r_script_path(self) -> Path:
        """Resolve the path to ``variable_creator.R``.

        Returns:
            Path to the R script.

        Raises:
            FileNotFoundError: If the script cannot be found.
        """
        return get_script_path(self.R_SCRIPT_REL, repo_root=self.repo_root)

    def _call_r_function(
        self,
        function_name: str,
        args: Optional[Dict[str, Any]] = None,
        timeout_sec: float = 120.0,
    ) -> Dict[str, Any]:
        """Call an R function (no DataFrames) via JSON payload.

        Args:
            function_name: Name of the R function to invoke.
            args: Dictionary of argument values passed through JSON.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            Dictionary parsed from the R function's JSON output.

        Raises:
            subprocess.CalledProcessError: If the R process fails.
            TimeoutError: If the R function times out.
            ValueError: If the R output is not valid JSON.
        """
        r_script_path = str(self._get_r_script_path())
        cmd, env = _pick_rscript_command()

        payload: Dict[str, Any] = {
            "func_name": function_name,
            "args": args if args is not None else {},
        }

        try:
            proc = _run_rscript(
                cmd,
                r_script_path,
                json.dumps(payload, allow_nan=False),
                env=env,
                timeout_sec=timeout_sec,
            )
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"R function '{function_name}' failed with return code {e.returncode}\n"
                f"{'=' * 60}\n"
                f"STDOUT:\n{e.output}\n"
                f"{'=' * 60}\n"
                f"STDERR:\n{e.stderr}\n"
                f"{'=' * 60}\n"
                f"Command: {' '.join(map(str, e.cmd))}\n"
                f"{'=' * 60}"
            )
            logger.error(error_msg)
            raise

        return _safe_parse_json_from_r_stdout(
            proc.stdout,
            f"function '{function_name}'",
        )

    def _call_r_function_df(
            self,
            function_name: str,
            args: Optional[Dict[str, Any]] = None,
            timeout_sec: float = 120.0,
            use_parquet: bool = True,
    ) -> Dict[str, Any]:
        """Call an R function with DataFrame arguments via temp files.

        DataFrames are written to temporary files (CSV or Parquet), and the
        file paths are passed to the R script. R writes result DataFrames to
        ``df_results`` files, which are read back into Python and then
        cleaned up. All temporary files (inputs and outputs) are deleted
        even if errors occur.

        Args:
            function_name: Name of the R function to invoke.
            args: Dictionary of arguments; any pandas DataFrame values
                are written to temporary files.
            timeout_sec: Maximum time to allow the R function to run.
            use_parquet: If True, use Parquet for DataFrame transfer;
                otherwise use CSV.

        Returns:
            Dictionary of non-DataFrame results along with any DataFrames
            produced by the R function.

        Raises:
            TimeoutError: If the R function times out.
            subprocess.CalledProcessError: If the R process fails.
            ValueError: If the R output is not valid JSON.
        """
        r_script_path = str(self._get_r_script_path())
        cmd, env = _pick_rscript_command()

        temp_files: list[str] = []  # Python-created input temp files (JSON + DF inputs)
        df_result_files: list[str] = []  # R-generated output files to be cleaned up
        temp_dir = tempfile.gettempdir()

        proc = None
        result: Dict[str, Any] | Any = {}

        try:
            # ---------------------------
            # Build payload & input temp files
            # ---------------------------
            df_paths: Dict[str, str] = {}
            simple_args: Dict[str, Any] = {}

            if args:
                for key, value in args.items():
                    if isinstance(value, pd.DataFrame):
                        file_path = _write_df_temp(
                            value,
                            use_parquet=use_parquet,
                            temp_dir=temp_dir,
                        )
                        df_paths[key] = file_path
                        temp_files.append(file_path)
                    else:
                        simple_args[key] = value

            payload = {
                "func_name": function_name,
                "args": simple_args,
                "df_args": df_paths,
                "use_parquet": use_parquet,
                "temp_dir": temp_dir,
            }

            tmp_json = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
                encoding="utf-8",
                dir=temp_dir,
            )
            try:
                json.dump(payload, tmp_json, allow_nan=False)
            finally:
                # Make sure file handle is closed even if json.dump fails
                tmp_json.close()
            temp_files.append(tmp_json.name)

            # ---------------------------
            # Call R
            # ---------------------------
            try:
                proc = _run_rscript(
                    cmd,
                    r_script_path,
                    tmp_json.name,
                    env=env,
                    timeout_sec=timeout_sec,
                )
            except subprocess.TimeoutExpired as e:
                # Let the finally block handle cleanup of known temp files
                raise TimeoutError(
                    f"R function '{function_name}' timed out after {timeout_sec}s."
                ) from e

            # ---------------------------
            # Parse JSON output from R
            # ---------------------------
            result = _safe_parse_json_from_r_stdout(
                proc.stdout,
                f"function '{function_name}' (df)",
            )

            # ---------------------------
            # Handle df_result files
            # ---------------------------
            if isinstance(result, dict) and "df_results" in result:
                file_paths = result["df_results"]
                df_results: Dict[str, pd.DataFrame] = {}

                # Track these paths so we can attempt cleanup in finally on any failure
                for file_path in file_paths.values():
                    if isinstance(file_path, str):
                        df_result_files.append(file_path)

                for key, file_path in file_paths.items():
                    try:
                        logger.debug("Looking for result file: %s", file_path)
                        if os.path.exists(file_path):
                            df_results[key] = _read_df_from_path(file_path)
                            logger.debug(
                                "Successfully read %d rows for key %s",
                                len(df_results[key]),
                                key,
                            )
                            try:
                                os.unlink(file_path)
                                logger.debug("Cleaned up: %s", file_path)
                                # Also remove from df_result_files so we don't try twice in finally
                                if file_path in df_result_files:
                                    df_result_files.remove(file_path)
                            except Exception as e:
                                logger.warning("Could not delete %s: %s", file_path, e)
                        else:
                            logger.warning("File not found: %s", file_path)
                    except Exception as read_err:
                        logger.exception("Error reading file %s: %s", file_path, read_err)

                # Merge DataFrame results with other results
                result = {**result, **df_results}
                if "df_results" in result:
                    del result["df_results"]

            return result

        finally:
            # ---------------------------
            # Cleanup: input temp files (JSON & DF inputs)
            # ---------------------------
            for tmp_file in temp_files:
                try:
                    if os.path.exists(tmp_file):
                        os.unlink(tmp_file)
                except Exception as cleanup_err:
                    logger.warning(
                        "Could not delete temp file %s: %s",
                        tmp_file,
                        cleanup_err,
                    )

            # ---------------------------
            # Cleanup: df_result files (R outputs) if any remain
            # ---------------------------
            for tmp_file in df_result_files:
                try:
                    if os.path.exists(tmp_file):
                        os.unlink(tmp_file)
                        logger.debug("Cleaned up df_result file in finally: %s", tmp_file)
                except Exception as cleanup_err:
                    logger.warning(
                        "Could not delete df_result file %s: %s",
                        tmp_file,
                        cleanup_err,
                    )

    def basic_text_preproc(
        self,
        text_field: str,
        suffix_string: Optional[str] = None,
        prefix_string: Optional[str] = None,
        timeout_sec: float = 120.0,
    ) -> str:
        """Execute R ``basic_text_preproc`` to clean and normalize text.

        Args:
            text_field: Input text string to preprocess.
            suffix_string: Optional regex pattern for suffix removal.
            prefix_string: Optional regex pattern for prefix removal.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            Cleaned and normalized text string.

        Raises:
            ValueError: If the R function reports an error or returns an
                unexpected payload.
        """
        args: Dict[str, Any] = {"text_field": str(text_field)}
        if suffix_string is not None:
            args["suffix_string"] = str(suffix_string)
        if prefix_string is not None:
            args["prefix_string"] = str(prefix_string)

        result = self._call_r_function(
            "basic_text_preproc",
            args=args,
            timeout_sec=timeout_sec,
        )

        if isinstance(result, dict):
            if result.get("status") == "error":
                error_msg = result.get("error", "Unknown error from R")
                raise ValueError(f"R function error: {error_msg}")

            if "processed_text" in result:
                processed_text = result["processed_text"]
                logger.debug("basic_text_preproc result: %r", processed_text)
                return processed_text

        raise ValueError(
            f"Expected dict with 'processed_text' key from R, got: {result}"
        )

    def batch_basic_text_preproc(
            self,
            text_fields: Sequence[str],
            suffix_string: Optional[str] = None,
            prefix_string: Optional[str] = None,
            timeout_sec: float = 120.0,
    ) -> List[str]:
        """Batch version of ``basic_text_preproc`` for lists of strings.

        This method:

        * Writes a JSON payload to a temporary file.
        * Calls the R function with that file path.
        * Parses and returns a list of processed text entries.

        Args:
            text_fields: Sequence of text strings to preprocess.
            suffix_string: Optional regex pattern for suffix removal.
            prefix_string: Optional regex pattern for prefix removal.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            List of cleaned/normalized text strings.

        Raises:
            TimeoutError: If the R process times out.
            subprocess.CalledProcessError: If the R process returns a non-zero
                exit code.
            ValueError: If the R output is not valid JSON with the expected
                schema.
        """
        # Prepare argument payload
        args: Dict[str, Any] = {"text_field": list(map(str, text_fields))}
        if suffix_string is not None:
            args["suffix_string"] = str(suffix_string)
        if prefix_string is not None:
            args["prefix_string"] = str(prefix_string)

        payload: Dict[str, Any] = {
            "func_name": "basic_text_preproc",
            "args": args,
        }

        r_script_path = str(self._get_r_script_path())
        cmd, env = _pick_rscript_command()
        subprocess_env = env if env else None

        # Write payload to temp JSON file
        with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
                encoding="utf-8",
        ) as f:
            json.dump(payload, f, allow_nan=False)
            temp_json_path = f.name

        try:
            # Use raw subprocess.run here instead of _run_rscript, because we
            # want the exact same semantics as the original implementation.
            proc = subprocess.run(
                cmd + [r_script_path, temp_json_path],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_sec,
                env=subprocess_env,
            )
        except subprocess.TimeoutExpired as e:
            # Ensure cleanup of the temp file on timeout
            if os.path.exists(temp_json_path):
                try:
                    os.unlink(temp_json_path)
                except Exception as cleanup_err:
                    logger.warning(
                        "Could not delete temp JSON file %s: %s",
                        temp_json_path,
                        cleanup_err,
                    )
            raise TimeoutError(
                f"R function 'basic_text_preproc' timed out after {timeout_sec}s. "
                f"Partial stdout: {e.output!r}, stderr: {e.stderr!r}"
            ) from e
        finally:
            # Best-effort cleanup of the temp JSON file
            if os.path.exists(temp_json_path):
                try:
                    os.unlink(temp_json_path)
                except Exception as cleanup_err:
                    logger.warning(
                        "Could not delete temp JSON file %s: %s",
                        temp_json_path,
                        cleanup_err,
                    )

        if proc.returncode != 0:
            error_msg = (
                f"R function 'basic_text_preproc' failed with return code {proc.returncode}\n"
                f"{'=' * 60}\n"
                f"STDOUT:\n{proc.stdout}\n"
                f"{'=' * 60}\n"
                f"STDERR:\n{proc.stderr}\n"
                f"{'=' * 60}\n"
                f"Command: {' '.join(map(str, proc.args))}\n"
                f"{'=' * 60}"
            )
            logger.error(error_msg)
            raise subprocess.CalledProcessError(
                returncode=proc.returncode,
                cmd=proc.args,
                output=proc.stdout,
                stderr=proc.stderr,
            )

        result = _safe_parse_json_from_r_stdout(
            proc.stdout,
            "basic_text_preproc batch",
        )

        # Your R returns {processed_text: [cleaned names...]}
        if "processed_text" in result:
            return list(result["processed_text"])

        raise ValueError("R did not return processed_text")


    def entity_resolution(
        self,
        df: pd.DataFrame,
        entity_resolution_lookup_table: pd.DataFrame,
        use_parquet: bool = True,
        timeout_sec: float = 120.0,
    ) -> pd.DataFrame:
        """Run the R ``entity_resolution`` function to group producer names.

        This function calls an R routine that generates
        ``PRODUCER_GROUP_NAME`` and ``PRODUCER_GROUP_NAME1`` columns,
        based on a lookup table of names and group IDs.

        Args:
            df: Main DataFrame, which must include columns:
                ``PRODUCER_NAME``, ``PRODUCER_NAME1``, ``QUANTITY``,
                ``COUNTRY_OF_ORIGIN_NAME``, ``PROPAGATIVE_MATERIAL_TYPE``,
                ``INSPECTION_NUMBER``.
            entity_resolution_lookup_table: DataFrame with columns ``name``
                and ``group`` describing entity groups.
            use_parquet: If True, use Parquet for DataFrame transfer.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            DataFrame including new ``PRODUCER_GROUP_NAME`` and
            ``PRODUCER_GROUP_NAME1`` columns.

        Raises:
            ValueError: If required columns are missing or if the R function
                reports an error or returns an unexpected payload.
        """
        required_dt = {
            "PRODUCER_NAME",
            "PRODUCER_NAME1",
            "QUANTITY",
            "COUNTRY_OF_ORIGIN_NAME",
            "PROPAGATIVE_MATERIAL_TYPE",
            "INSPECTION_NUMBER",
        }
        missing_dt = required_dt - set(df.columns)
        if missing_dt:
            raise ValueError(
                f"df missing required columns for entity_resolution: {missing_dt}"
            )

        required_lookup = {"name", "group"}
        missing_lookup = required_lookup - set(entity_resolution_lookup_table.columns)
        if missing_lookup:
            raise ValueError(
                "entity_resolution_lookup_table missing required columns: "
                f"{missing_lookup}"
            )

        args: Dict[str, Any] = {
            "dt": df,
            "entity_resolution_lookup_table": entity_resolution_lookup_table,
        }

        result = self._call_r_function_df(
            "entity_resolution",
            args=args,
            timeout_sec=timeout_sec,
            use_parquet=use_parquet,
        )

        if isinstance(result, dict) and result.get("status") == "error":
            raise ValueError(f"R function error: {result.get('error')}")

        if "result_df" in result:
            result_df = result["result_df"]
            if isinstance(result_df, pd.DataFrame):
                return result_df
            raise ValueError(f"Expected DataFrame, got {type(result_df)}")

        raise ValueError(f"No 'result_df' in result: {result.keys()}")



    def generate_quantity_binaries(
        self,
        df: pd.DataFrame,
        quantity_threshold: float = 200.0,
        group_cols: Optional[List[str]] = None,
        use_parquet: bool = True,
        timeout_sec: float = 120.0,
    ) -> pd.DataFrame:
        """Aggregate data and create binary features based on quantity.

        This function delegates to an R routine that:

        * Groups data by the provided ``group_cols`` (default R-side grouping).
        * Computes aggregate statistics and flags indicating whether quantities
          exceed a given threshold.

        Args:
            df: Input DataFrame that must contain a ``'QUANTITY'`` column.
            quantity_threshold: Threshold for binary classification.
            group_cols: Columns to group by (default behavior is implemented
                R-side, often ``['RISK_UNIT']``).
            use_parquet: If True, use Parquet for DataFrame transfer.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            DataFrame of aggregated groups with quantity-based binary features.

        Raises:
            ValueError: If ``'QUANTITY'`` is missing or if the R function
                reports an error or returns an unexpected payload.
        """
        if "QUANTITY" not in df.columns:
            raise ValueError("DataFrame must contain 'QUANTITY' column")

        args: Dict[str, Any] = {
            "df": df,
            "quantity_threshold": float(quantity_threshold),
        }
        if group_cols is not None:
            args["group_cols"] = list(group_cols)

        result = self._call_r_function_df(
            "generate_quantity_binaries",
            args=args,
            timeout_sec=timeout_sec,
            use_parquet=use_parquet,
        )

        if isinstance(result, dict) and result.get("status") == "error":
            raise ValueError(f"R function error: {result.get('error')}")

        if "result_df" in result:
            result_df = result["result_df"]
            if isinstance(result_df, pd.DataFrame):
                logger.debug("Aggregated to %d groups", result_df.shape[0])
                return result_df
            raise ValueError(f"Expected DataFrame, got {type(result_df)}")

        raise ValueError(f"No 'result_df' in result: {result.keys()}")

    def generate_producer_top_strata_features(
        self,
        df: pd.DataFrame,
        dt_train: pd.DataFrame,
        max_strat_count: int = 50,
        min_action_rate: float = 0.02,
        min_records: int = 5,
        use_parquet: bool = True,
        timeout_sec: float = 120.0,
    ) -> pd.DataFrame:
        """Add top-producer strata features based on action rates.

        This function calls an R routine to compute stratified producer
        groups (``PRODUCER_GROUP_TOP``) using both the main DataFrame and a
        training DataFrame.

        Args:
            df: Input DataFrame containing at least ``'action'`` and
                ``'PRODUCER_GROUP_NAME1'``.
            dt_train: Training DataFrame with the same required columns.
            max_strat_count: Maximum number of strata to retain.
            min_action_rate: Minimum action rate threshold for including a
                stratum.
            min_records: Minimum number of records required per stratum.
            use_parquet: If True, use Parquet for DataFrame transfer.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            DataFrame with a new ``PRODUCER_GROUP_TOP`` feature (and any
            other R-generated columns).

        Raises:
            ValueError: If required columns are missing or if the R function
                reports an error or returns an unexpected payload.
        """
        required = {"action", "PRODUCER_GROUP_NAME1"}
        missing = required - set(df.columns)
        missing_train = required - set(dt_train.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        if missing_train:
            raise ValueError(f"Training DataFrame missing required columns: {missing_train}")

        args: Dict[str, Any] = {
            "df": df,
            "dt_train": dt_train,
            "maxStratCount": int(max_strat_count),
            "minActionRate": float(min_action_rate),
            "minRecords": int(min_records),
        }

        result = self._call_r_function_df(
            "generate_producer_top_strata_features",
            args=args,
            timeout_sec=timeout_sec,
            use_parquet=use_parquet,
        )

        if isinstance(result, dict) and result.get("status") == "error":
            raise ValueError(f"R function error: {result.get('error')}")

        if "result_df" in result:
            result_df = result["result_df"]
            if isinstance(result_df, pd.DataFrame):
                return result_df
            raise ValueError(f"Expected DataFrame, got {type(result_df)}")

        raise ValueError(f"No 'result_df' in result: {result.keys()}")


    def generate_importer_top_strata_features(
        self,
        df: pd.DataFrame,
        dt_train: pd.DataFrame,
        max_strat_count: int = 50,
        min_action_rate: float = 0.02,
        min_records: int = 5,
        use_parquet: bool = True,
        timeout_sec: float = 120.0,
    ) -> pd.DataFrame:
        """Add top-importer strata features based on action rates.

        This function calls an R routine to compute stratified importer
        groups (``IMPORTER_NAME_TOP``) using the main and training DataFrames.

        Args:
            df: Input DataFrame containing at least ``'action'`` and
                ``'IMPORTER_NAME1'``.
            dt_train: Training DataFrame with the same required columns.
            max_strat_count: Maximum number of strata to retain.
            min_action_rate: Minimum action rate threshold for including a
                stratum.
            min_records: Minimum number of records required per stratum.
            use_parquet: If True, use Parquet for DataFrame transfer.
            timeout_sec: Maximum time to allow the R function to run.

        Returns:
            DataFrame with a new ``IMPORTER_NAME_TOP`` feature (and any
            other R-generated columns).

        Raises:
            ValueError: If required columns are missing or if the R function
                reports an error or returns an unexpected payload.
        """
        required = {"action", "IMPORTER_NAME1"}
        missing = required - set(df.columns)
        missing_train = required - set(dt_train.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        if missing_train:
            raise ValueError(f"Training DataFrame missing required columns: {missing_train}")

        args: Dict[str, Any] = {
            "df": df,
            "dt_train": dt_train,
            "maxStratCount": int(max_strat_count),
            "minActionRate": float(min_action_rate),
            "minRecords": int(min_records),
        }

        result = self._call_r_function_df(
            "generate_importer_top_strata_features",
            args=args,
            timeout_sec=timeout_sec,
            use_parquet=use_parquet,
        )

        if isinstance(result, dict) and result.get("status") == "error":
            raise ValueError(f"R function error: {result.get('error')}")

        if "result_df" in result:
            result_df = result["result_df"]
            if isinstance(result_df, pd.DataFrame):
                return result_df
            raise ValueError(f"Expected DataFrame, got {type(result_df)}")

        raise ValueError(f"No 'result_df' in result: {result.keys()}")
