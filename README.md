# pro_venv — Project Scaffold

![Build](https://github.com/TamerOnLine/pro_venv/actions/workflows/test-pro_venv.yml/badge.svg)
![Release](https://img.shields.io/github/v/release/TamerOnLine/pro_venv?style=flat-square)
![License](https://img.shields.io/github/license/TamerOnLine/pro_venv?style=flat-square)

A one‑shot Python project scaffold. It prepares the virtual environment, installs requirements, generates launch files, and configures VS Code — all from **the project root**.

---

## 🚀 Quick Start

> Run all commands from **the project root**.

```bash
# first-time setup
python pro_venv.py

# run your app later
python main.py
```

> You don’t need to activate `venv` manually — `main.py` re-executes inside your environment automatically.

---

## ✨ What does the script do?

- Creates or reads `setup-config.json` (project settings).
- Creates `venv/` and upgrades `pip`.
- Installs packages from `requirements.txt` (creates it if missing).
- Generates:
  - `main.py` (a safe launcher that re-executes inside venv, then runs your file).
  - `app.py` (a simple starter entry point you can replace).
  - `.vscode/settings.json`, `.vscode/launch.json`, and `project.code-workspace`.
  - `env-info.txt` (Python version + list of installed packages).
- (Optional) Generates a GitHub Actions workflow when using `--ci`.

---

## 🗂️ Files & Expected Structure

```
.
├── pro_venv.py
├── setup-config.json
├── requirements.txt
├── main.py
├── app.py
├── env-info.txt
├── venv/
└── .vscode/
    ├── settings.json
    └── launch.json
```

---

## ⚙️ Configuration: `setup-config.json`

Default values created by the script:

```json
{
  "project_name": "<folder-name>",
  "main_file": "app.py",
  "entry_point": "main.py",
  "requirements_file": "requirements.txt",
  "venv_dir": "venv",
  "python_version": "3.12"
}
```

You can edit these after generation (e.g., change the main file or the venv folder name).

---

## 🧪 GitHub Actions Integration (Optional)

To create a simple test workflow:

```bash
python pro_venv.py --ci create
```

This generates: `.github/workflows/test-pro_venv.yml`.

> Use `--ci force` to overwrite if the file already exists, and `--ci-python` to choose the Python version.

---

## ❓ FAQ

**Do I need to activate the environment manually?**  
No. `main.py` re-executes inside the environment, then runs `app.py`.

**Where should I run the script from?**  
From the **project root**. If you enable the safety check at the end of the file, it blocks running from outside the root with a clear message.

**Where are VS Code settings saved?**  
Inside `.vscode/` in the project. It’s recommended to ignore these in Git because they’re local settings.

---

## 🧰 Requirements

- Python 3.12 (or as configured in `setup-config.json`).
- Permission to create folders/files in the project root.

---

## 📝 License

MIT — see `LICENSE`.
