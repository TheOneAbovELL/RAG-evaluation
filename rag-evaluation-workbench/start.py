"""Start RAG Evaluation Workbench — one command does everything:

    python start.py

1. Prepares the environment: `uv sync` if uv is installed, otherwise a local `.venv` created with
   `python -m venv` and `pip install -e .` (needs Python 3.12+). Nothing is installed outside this folder.
2. On the first launch (empty run store), runs the five offline example evaluations over the bundled
   honeybee document so the app opens with real results. No network or API key is needed.
3. Starts the Streamlit app on this machine only (http://localhost:<port>) and opens it in the browser.
4. Ctrl+C stops the app.

Options: --port N (default: first free port from 8501), --host H (default localhost; any other address requires
RAGWB_APP_PASSWORD or user accounts), --ssl-cert/--ssl-key (serve over HTTPS), --no-browser, --no-examples,
--setup-only.
This file uses only the Python standard library, so it runs before any dependency is installed.
"""

import argparse
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MIN_PYTHON = (3, 12)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def say(message):
    print(f"[start] {message}", flush=True)


def run(cmd, **kwargs):
    say("$ " + " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=ROOT, check=False, **kwargs)


def prepare_environment():
    uv = shutil.which("uv")
    if uv:
        env = dict(os.environ, UV_HTTP_TIMEOUT=os.environ.get("UV_HTTP_TIMEOUT", "180"))
        if run([uv, "sync", "--frozen", "--inexact"], env=env).returncode != 0:
            sys.exit("[start] `uv sync` failed; see the messages above (a slow network may need a retry).")
        return
    if sys.version_info < MIN_PYTHON:
        major, minor = sys.version_info[:2]
        sys.exit(f"[start] uv is not installed and this Python is {major}.{minor}; install uv "
                 "(https://docs.astral.sh/uv/) or run this file with Python 3.12 or newer.")
    if not VENV_PYTHON.exists():
        say("uv not found: creating .venv with the standard venv module")
        if run([sys.executable, "-m", "venv", VENV]).returncode != 0:
            sys.exit("[start] could not create .venv")
    if run([VENV_PYTHON, "-m", "pip", "install", "--quiet", "-e", ".", "pytest", "pytest-cov"]).returncode != 0:
        sys.exit("[start] `pip install` failed; see the messages above.")


def store_is_empty():
    probe = ("from rag_workbench.services import open_context; "
             "print(len(open_context(console_logging=False).store.list_runs()))")
    result = run([VENV_PYTHON, "-c", probe], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("[start] the application could not open its run store:\n" + result.stderr[-2000:])
    return result.stdout.strip() == "0"


def create_examples():
    say("first launch: running the offline example evaluations (a few seconds)")
    code = ("from rag_workbench.demo import seed_demo_runs; from rag_workbench.services import open_context; "
            "runs = seed_demo_runs(open_context(console_logging=False)); "
            "print('\\n'.join(f'  {r.name}: {r.status}' for r in runs.values()))")
    if run([VENV_PYTHON, "-c", code]).returncode != 0:
        say("example runs could not be created; the app will start without them")


def password_configured(env=None, env_file=None):
    """True if RAGWB_APP_PASSWORD is set (in the environment or in .env) to a non-blank value."""
    env = os.environ if env is None else env
    if env.get("RAGWB_APP_PASSWORD", "").strip():
        return True
    if env.get("RAGWB_NO_DOTENV") == "1":  # the same switch the application honours
        return False
    env_file = ROOT / ".env" if env_file is None else env_file
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "RAGWB_APP_PASSWORD" and value.strip().strip("\"'"):
                return True
    return False


def accounts_configured(env=None):
    """True if named user accounts exist (``<data dir>/users.json`` lists at least one user, or cannot be parsed)."""
    env = os.environ if env is None else env
    data_dir = Path(env.get("RAGWB_DATA_DIR", "").strip() or "data")
    users_file = (data_dir if data_dir.is_absolute() else ROOT / data_dir) / "users.json"
    if not users_file.is_file():
        return False
    try:
        users = json.loads(users_file.read_text(encoding="utf-8")).get("users")
    except (OSError, ValueError, AttributeError):
        return True  # a damaged file must count as "accounts exist": the app locks rather than opens
    return bool(users)


def host_problem(host, password_set):
    """Why this host must not be used, or None. Exposing the app needs a login: the shared password or accounts."""
    if host in LOCAL_HOSTS or password_set:
        return None
    return (f"refusing to listen on {host!r} without a login. Set RAGWB_APP_PASSWORD (environment or .env), or "
            "create accounts with `ragwb user add NAME`, first; or use the default localhost.")


def tls_problem(cert, key):
    """Why the TLS options are unusable, or None."""
    if not cert and not key:
        return None
    if not (cert and key):
        return "--ssl-cert and --ssl-key must be given together"
    for label, path in (("--ssl-cert", cert), ("--ssl-key", key)):
        if not Path(path).is_file():
            return f"{label} file not found: {path}"
    return None


def free_port(preferred):
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit(f"[start] no free port found near {preferred}")


def wait_until_ready(port, process, timeout=90, host="localhost", https=False):
    url = f"{'https' if https else 'http'}://{host}:{port}/_stcore/health"
    # A health probe of our own local server: a self-signed certificate must not make it look unhealthy.
    context = ssl._create_unverified_context() if https else None
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2, context=context) as response:
                if response.read().strip() == b"ok":
                    return True
        except OSError:
            time.sleep(0.5)
    return False


def launch(port, open_browser, host="localhost", ssl_cert=None, ssl_key=None):
    env = dict(os.environ, DEEPEVAL_TELEMETRY_OPT_OUT="1")
    cmd = [VENV_PYTHON, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", port,
           "--server.address", host, "--server.headless", "true", "--browser.gatherUsageStats", "false"]
    https = bool(ssl_cert and ssl_key)
    if https:
        cmd += ["--server.sslCertFile", ssl_cert, "--server.sslKeyFile", ssl_key]
    elif host not in LOCAL_HOSTS:
        say("warning: serving over plain HTTP; sign-in credentials cross the network unencrypted "
            "(use --ssl-cert and --ssl-key, or a TLS proxy)")
    probe_host = "localhost" if host in {"0.0.0.0", "::"} else host
    say("$ " + " ".join(str(c) for c in cmd))
    process = subprocess.Popen([str(c) for c in cmd], cwd=ROOT, env=env)
    try:
        if wait_until_ready(port, process, host=probe_host, https=https):
            url = f"{'https' if https else 'http'}://{probe_host}:{port}"
            say(f"RAG Evaluation Workbench is running at {url}  (Ctrl+C to stop)")
            if open_browser:
                webbrowser.open(url)
        elif process.poll() is not None:
            sys.exit(f"[start] the app exited during start-up (code {process.returncode}); see the messages above.")
        else:
            say(f"the app is taking long to start; it may still come up at "
                f"{'https' if https else 'http'}://{probe_host}:{port}")
        process.wait()
    except KeyboardInterrupt:
        say("stopping…")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    return process.returncode or 0


def main():
    parser = argparse.ArgumentParser(description="Set up and start RAG Evaluation Workbench.")
    parser.add_argument("--port", type=int, default=8501, help="preferred port (default 8501)")
    parser.add_argument("--host", default="localhost",
                        help="address to listen on (default localhost; anything else requires RAGWB_APP_PASSWORD "
                             "or user accounts)")
    parser.add_argument("--ssl-cert", help="TLS certificate file (PEM); serves the app over HTTPS")
    parser.add_argument("--ssl-key", help="TLS private key file (PEM), used with --ssl-cert")
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    parser.add_argument("--no-examples", action="store_true", help="skip the first-launch example runs")
    parser.add_argument("--setup-only", action="store_true", help="prepare the environment and examples, then exit")
    args = parser.parse_args()
    os.chdir(ROOT)
    problem = host_problem(args.host, password_configured() or accounts_configured()) or tls_problem(
        args.ssl_cert, args.ssl_key)
    if problem:
        sys.exit(f"[start] {problem}")
    prepare_environment()
    if not args.no_examples and store_is_empty():
        create_examples()
    if args.setup_only:
        say("setup complete")
        return 0
    return launch(free_port(args.port), not args.no_browser, args.host, args.ssl_cert, args.ssl_key)


if __name__ == "__main__":
    sys.exit(main())
