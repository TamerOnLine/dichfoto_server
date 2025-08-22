
import os
import sys
import subprocess
import json
import argparse
from pathlib import Path
import textwrap


def create_vscode_files(venv_dir):
    '''
    Create VS Code configuration files including settings.json, launch.json, and a workspace file.

    Args:
        venv_dir (str): Path to the virtual environment directory.

    Creates:
        - .vscode/settings.json: Contains Python and editor settings.
        - .vscode/launch.json: Configuration for launching Python files.
        - project.code-workspace: VS Code workspace configuration.

    Notes:
        - Uses correct python interpreter path on Windows/Linux/macOS.
    '''
    print("\n[8] Creating VS Code files: settings, launch, workspace")

    vscode_dir = os.path.join(os.getcwd(), ".vscode")
    settings_path = os.path.join(vscode_dir, "settings.json")
    launch_path = os.path.join(vscode_dir, "launch.json")
    workspace_path = os.path.join(os.getcwd(), "project.code-workspace")

    os.makedirs(vscode_dir, exist_ok=True)

    # Cross-platform interpreter path inside the venv
    interp = (
        os.path.join(venv_dir, "Scripts", "python.exe")
        if os.name == "nt"
        else os.path.join(venv_dir, "bin", "python")
    )

    # Create settings.json
    settings = {
        "python.defaultInterpreterPath": interp,
        "python.terminal.activateEnvironment": True,
        "editor.formatOnSave": True,
        # Old setting kept for compatibility; feel free to switch to ms-python.black-formatter later
        "python.formatting.provider": "black",
    }
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    # Create launch.json
    launch = {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Run main.py",
                "type": "python",
                "request": "launch",
                "program": "${workspaceFolder}/main.py",
                "console": "integratedTerminal",
                "justMyCode": True,
            }
        ],
    }
    with open(launch_path, "w", encoding="utf-8") as f:
        json.dump(launch, f, indent=2)

    # Create project.code-workspace
    workspace = {
        "folders": [{"path": "."}],
        "settings": {
            "python.defaultInterpreterPath": interp,
        },
    }
    with open(workspace_path, "w", encoding="utf-8") as f:
        json.dump(workspace, f, indent=2)

    print(
        "VS Code files created successfully: settings.json, launch.json, project.code-workspace"
    )


def load_or_create_config():
    '''
    Load or create the setup-config.json file.

    Returns:
        dict: The configuration loaded from or written to setup-config.json.
    '''
    print("\n[1] Setting up setup-config.json")
    config_path = os.path.join(os.getcwd(), "setup-config.json")

    if not os.path.exists(config_path):
        print("Creating config file...")
        default_config = {
            "project_name": os.path.basename(os.getcwd()),
            "main_file": "app.py",
            "entry_point": "main.py",
            "requirements_file": "requirements.txt",
            "venv_dir": "venv",
            "python_version": "3.12",
        }
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2)
        print("setup-config.json created.")
    else:
        print("Config file already exists.")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_virtualenv(venv_dir, python_version=None):
    '''
    Create a virtual environment using the current Python interpreter.

    Args:
        venv_dir (str): Directory path for the virtual environment.
        python_version (str, optional): Target Python version (unused).
    '''
    print("\n[2] Checking virtual environment")
    if not os.path.exists(venv_dir):
        print(f"Creating virtual environment at: {venv_dir}")
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        print("Virtual environment created.")
    else:
        print("Virtual environment already exists.")


def create_requirements_file(path):
    '''
    Create a default requirements.txt if it doesn't exist.

    Args:
        path (str): File path for requirements.txt.
    '''
    print("\n[3] Checking requirements.txt")
    if not os.path.exists(path):
        print("Creating empty requirements.txt...")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Add your dependencies here\n")
        print("requirements.txt created.")
    else:
        print("requirements.txt already exists.")


def _venv_python(venv_dir: str) -> str:
    return (
        os.path.join(venv_dir, "Scripts", "python.exe")
        if os.name == "nt"
        else os.path.join(venv_dir, "bin", "python")
    )


def install_requirements(venv_dir, requirements_path):
    '''
    Install packages from requirements.txt.

    Args:
        venv_dir (str): Directory path for the virtual environment.
        requirements_path (str): Path to requirements.txt file.
    '''
    print("\n[4] Installing requirements")
    py = _venv_python(venv_dir)
    subprocess.run(
        [py, "-m", "pip", "install", "-r", requirements_path, "--upgrade-strategy", "only-if-needed"],
        check=True,
    )
    print("Packages installed.")


def upgrade_pip(venv_dir):
    '''
    Upgrade pip inside the virtual environment.

    Args:
        venv_dir (str): Directory path for the virtual environment.
    '''
    print("\n[5] Upgrading pip")
    py = _venv_python(venv_dir)
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    print("pip upgraded.")


def create_env_info(venv_dir):
    '''
    Save basic information about the virtual environment.

    Args:
        venv_dir (str): Directory path for the virtual environment.
    '''
    print("\n[6] Creating env-info.txt")
    info_path = "env-info.txt"
    py = _venv_python(venv_dir)
    with open(info_path, "w", encoding="utf-8") as f:
        subprocess.run([py, "--version"], stdout=f)
        f.write("\nInstalled packages:\n")
        subprocess.run([py, "-m", "pip", "freeze"], stdout=f)
    print(f"Environment info saved to {info_path}")


def create_main_file(main_file_path, venv_dir):
    '''
    Create main.py with v2 safe launcher (re-exec into venv, then run app.py).

    Args:
        main_file_path (str): Path to main.py file.
        venv_dir (str): Directory path for the virtual environment.
    '''
    print("\n[7] Checking main.py")
    if not os.path.exists(main_file_path):
        print(f"Creating {main_file_path}...")

        # Safer main: re-exec inside venv, then run app.py as a subprocess
        main_code = f'''
# PRO_VENV_MAIN=v2
import os, sys, json, subprocess

BASE = os.path.dirname(__file__)
VENV_PY = os.path.join(BASE, r"{venv_dir}", "Scripts", "python.exe") if os.name == "nt" else os.path.join(BASE, r"{venv_dir}", "bin", "python")

def _load_cfg():
    cfg_path = os.path.join(BASE, "setup-config.json")
    if not os.path.exists(cfg_path):
        print("setup-config.json not found.")
        sys.exit(1)
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)

# Ensure we run inside the venv; fail fast if missing
if os.path.abspath(sys.executable) != os.path.abspath(VENV_PY):
    if not os.path.exists(VENV_PY):
        print("venv interpreter not found. Run: python pro_venv.py")
        sys.exit(1)
    os.execv(VENV_PY, [VENV_PY, __file__])

cfg = _load_cfg()
app = cfg.get("main_file", "app.py")
if not os.path.exists(app):
    print(f"{{app}} does not exist.")
    sys.exit(1)

print("Interpreter:", sys.executable)
print("Running:", app)
sys.exit(subprocess.call([sys.executable, app]))
'''.lstrip()

        with open(main_file_path, "w", encoding="utf-8") as f:
            f.write(main_code)
        print(f"{main_file_path} created.")
    else:
        print("main.py already exists.")


def create_app_file(app_file_path):
    '''
    Create a simple app.py file with a welcome message if it does not exist.
    Args:
        app_file_path (str): Path to app.py or the main application file.
    '''
    print("\n[7.1] Checking app.py")
    if not os.path.exists(app_file_path):
        print(f"Creating {app_file_path} with welcome message...")
        welcome_code = 'print("Welcome! This is your app.py file.")\nprint("You can now start writing your application code here.")\n'
        with open(app_file_path, "w", encoding="utf-8") as f:
            f.write(welcome_code)
        print(f"{app_file_path} created.")
    else:
        print(f"{app_file_path} already exists.")


def ensure_gh_actions_workflow(path=".github/workflows/test-pro_venv.yml", *, py="3.12", force=False, backup=True) -> str:
    """
    Create or overwrite a minimal GitHub Actions workflow that runs pro_venv.py.

    Args:
        path (str): Target workflow path.
        py (str): Python version for the CI runner.
        force (bool): Overwrite if file exists.
        backup (bool): Create .bak backup before overwrite.

    Returns:
        str: "created", "overwritten", or "exists".
    """
    repo_root = Path(__file__).resolve().parent
    wf_path = Path(path)
    if not wf_path.is_absolute():
        wf_path = repo_root / wf_path
    wf_path.parent.mkdir(parents=True, exist_ok=True)

    if wf_path.exists() and not force:
        return "exists"

    if wf_path.exists() and backup:
        bak = wf_path.with_suffix(wf_path.suffix + ".bak")
        bak.write_text(wf_path.read_text(encoding="utf-8"), encoding="utf-8")

    yml = textwrap.dedent(f"""    name: Test pro_venv.py

    on: [push, pull_request]

    jobs:
      run-script:
        runs-on: ubuntu-latest
        steps:
          - name: Checkout repository
            uses: actions/checkout@v4

          - name: Set up Python
            uses: actions/setup-python@v4
            with:
              python-version: "{py}"

          - name: Install minimal requirements (if any)
            run: |
              python -m pip install --upgrade pip

          - name: Run pro_venv.py
            run: |
              python pro_venv.py
    """)
    wf_path.write_text(yml, encoding="utf-8")
    return "overwritten" if force else "created"


if __name__ == "__main__":
    # Validate that this script is executed from the project root.
    # It compares CWD to the directory containing this file.
    if Path.cwd() != Path(__file__).resolve().parent:
        print("Run the script from the project root.")
        sys.exit(1)

    # CLI options for CI workflow generation
    parser = argparse.ArgumentParser(description="Project setup and CI generator")
    parser.add_argument(
        "--ci",
        choices=["skip", "create", "force"],
        default="skip",
        help="Create GitHub Actions workflow (.github/workflows/test-pro_venv.yml)."
    )
    parser.add_argument(
        "--ci-python",
        default="3.12",
        help="Python version used in the CI (default: 3.12)."
    )
    args = parser.parse_args()

    print("\nStarting project setup...\n" + "-" * 40)
    config = load_or_create_config()
    if args.ci in ("create", "force"):
        status = ensure_gh_actions_workflow(py=args.ci_python, force=(args.ci == "force"))
        print(f"[ci] {status}: .github/workflows/test-pro_venv.yml")

    venv_dir = config["venv_dir"]
    requirements_path = config["requirements_file"]
    main_file = config["main_file"]
    python_version = config["python_version"]

    create_virtualenv(venv_dir, python_version)
    create_requirements_file(requirements_path)
    upgrade_pip(venv_dir)
    install_requirements(venv_dir, requirements_path)
    create_env_info(venv_dir)

    entry_point = config.get("entry_point", "main.py")
    create_main_file(entry_point, venv_dir)
    create_app_file(main_file)
    create_vscode_files(venv_dir)

    print("\nProject setup complete.")
