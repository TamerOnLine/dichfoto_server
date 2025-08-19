# PRO_VENV_MAIN=v2
import os, sys, json, subprocess

BASE = os.path.dirname(__file__)
VENV_PY = os.path.join(BASE, r"venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(BASE, r"venv", "bin", "python")

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
    print(f"{app} does not exist.")
    sys.exit(1)

print("Interpreter:", sys.executable)
print("Running:", app)
sys.exit(subprocess.call([sys.executable, app]))
