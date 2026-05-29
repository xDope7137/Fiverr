"""Preflight checks. Verifies that everything needed to run the automation
is in place: Python version, adb, uiautomator2, a valid config, a connected
device, the Fiverr app installed, and the uiautomator2 agent reachable.

Run on its own with `python preflight.py` (or `check.bat` on Windows).
Each step prints [OK] / [WARN] / [FAIL]. Exits 0 if everything required
passes, 1 otherwise.
"""
import json
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
FIVERR_PACKAGE = "com.fiverr.fiverr"


def ok(msg):
    print(f"  [OK]   {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


def header(msg):
    print()
    print(msg)


def check_python():
    header("Python")
    v = sys.version_info
    if v.major == 3 and v.minor >= 8:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} found — need 3.8+")
    return False


def check_adb():
    header("ADB (Android Debug Bridge)")
    adb_path = shutil.which("adb")
    if not adb_path:
        fail("`adb` not found in PATH.")
        fail("Install Android Platform Tools and add it to PATH:")
        fail("  https://developer.android.com/studio/releases/platform-tools")
        return False
    ok(f"adb found at {adb_path}")
    return True


def check_uiautomator2_pkg():
    header("Python dependencies")
    try:
        import uiautomator2  # noqa: F401
        ok("uiautomator2 importable")
        return True
    except ImportError:
        fail("uiautomator2 not installed.")
        fail("Run: pip install -r requirements.txt  (or just run setup.bat)")
        return False


def load_config_or_none():
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return "bad"


def check_config():
    header("Config")
    if not os.path.exists(CONFIG_PATH):
        warn(f"{os.path.basename(CONFIG_PATH)} not found — defaults will be created on first run.")
        return True
    cfg = load_config_or_none()
    if cfg == "bad":
        fail(f"{os.path.basename(CONFIG_PATH)} is not valid JSON — fix the syntax.")
        return False
    ok(f"loaded {os.path.basename(CONFIG_PATH)}")
    serial = cfg.get("serial")
    print(f"        serial:  {serial!r}{' (auto-detect)' if not serial else ''}")
    print(f"        message: {cfg.get('message')!r}")
    send = cfg.get("send", False)
    print(f"        send:    {send}  ({'LIVE — will post replies' if send else 'dry-run only'})")
    return True


def _adb(args, serial=None):
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True)


def check_device(serial):
    header("Device connection")
    if serial:
        # Pre-emptive wireless connect attempt; harmless if already connected.
        subprocess.run(["adb", "connect", serial], capture_output=True, text=True)
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    devices = []
    for line in result.stdout.splitlines()[1:]:
        if "\tdevice" in line:
            devices.append(line.split()[0])
    if not devices:
        fail("No connected device found.")
        fail("USB: plug the phone in with USB debugging enabled.")
        fail("Wireless: set `serial` in config.json (e.g. \"192.168.x.x:5555\") and re-run.")
        return False
    ok(f"connected device(s): {devices}")
    if serial and serial not in devices:
        warn(f"configured serial {serial!r} is not in the connected list — auto-detect may pick wrong device")
    return True


def check_fiverr_installed(serial):
    header("Fiverr app")
    result = _adb(["shell", "pm", "list", "packages", FIVERR_PACKAGE], serial=serial)
    if FIVERR_PACKAGE in result.stdout:
        ok(f"{FIVERR_PACKAGE} is installed")
        return True
    fail(f"{FIVERR_PACKAGE} not installed on the device.")
    fail("Install Fiverr from Google Play (or sideload), then re-run.")
    return False


def check_fiverr_foreground(serial):
    header("Fiverr foreground (warn-only)")
    result = _adb(["shell", "dumpsys", "activity", "activities"], serial=serial)
    out = result.stdout
    for line in out.splitlines():
        if ("ResumedActivity" in line or "mResumedActivity" in line) and FIVERR_PACKAGE in line:
            ok("Fiverr is the resumed (foreground) activity")
            return True
    warn(f"Couldn't confirm {FIVERR_PACKAGE} is foreground.")
    warn("Open the Fiverr app on the phone before starting watch_and_reply.")
    return True


def check_uiautomator_agent(serial):
    header("uiautomator2 agent")
    try:
        import uiautomator2 as u2
        d = u2.connect(serial)
        info = d.info
        ok(f"agent reachable (device: {info.get('productName', 'unknown')})")
        return True
    except Exception as e:
        fail(f"uiautomator2 agent connect failed: {e}")
        fail("First time on this device? Run: python -m uiautomator2 init")
        return False


def main():
    print("Fiverr Automation — preflight checks")

    cfg = load_config_or_none()
    serial = None
    if isinstance(cfg, dict):
        serial = cfg.get("serial")

    required_pass = True
    if not check_python():
        required_pass = False
    if not check_adb():
        required_pass = False
    if not check_uiautomator2_pkg():
        required_pass = False
    if not check_config():
        required_pass = False
    if required_pass:
        if not check_device(serial):
            required_pass = False
        if required_pass and not check_fiverr_installed(serial):
            required_pass = False
        if required_pass:
            check_fiverr_foreground(serial)
            if not check_uiautomator_agent(serial):
                required_pass = False

    print()
    if required_pass:
        print("All required checks passed. You're ready to go.")
        sys.exit(0)
    else:
        print("Some checks failed. Fix the issues above and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()
