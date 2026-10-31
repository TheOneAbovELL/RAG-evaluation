"""Tests for the one-command launcher. ``start.py`` is a standalone, standard-library-only script, so it is loaded by
file path. The functions that need uv, a network or a real server are covered by the end-to-end check in
``scripts/verify.py`` and by the manual procedure in the project book; here we test its decision logic."""

import importlib.util
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from rag_workbench.config import PROJECT_ROOT


@pytest.fixture(scope="module")
def start():
    spec = importlib.util.spec_from_file_location("start_script", PROJECT_ROOT / "start.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_local_hosts_never_need_a_password(start, host):
    assert start.host_problem(host, password_set=False) is None


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "myhost.example"])
def test_exposed_hosts_are_refused_without_a_password_and_allowed_with_one(start, host):
    problem = start.host_problem(host, password_set=False)
    assert problem and "RAGWB_APP_PASSWORD" in problem and host in problem
    assert start.host_problem(host, password_set=True) is None


def test_password_is_detected_in_the_environment_and_in_dotenv(start, tmp_path):
    env_file = tmp_path / ".env"
    assert not start.password_configured(env={}, env_file=env_file)
    assert start.password_configured(env={"RAGWB_APP_PASSWORD": "x"}, env_file=env_file)
    assert not start.password_configured(env={"RAGWB_APP_PASSWORD": "   "}, env_file=env_file)
    env_file.write_text("OPENAI_API_KEY=\nRAGWB_APP_PASSWORD=\n", encoding="utf-8")
    assert not start.password_configured(env={}, env_file=env_file)  # present but blank
    env_file.write_text('# comment\nRAGWB_APP_PASSWORD="s3cret-value"\n', encoding="utf-8")
    assert start.password_configured(env={}, env_file=env_file)
    env_file.write_text('RAGWB_APP_PASSWORD=""\n', encoding="utf-8")
    assert not start.password_configured(env={}, env_file=env_file)


def test_accounts_are_detected_from_the_users_file(start, tmp_path):
    env = {"RAGWB_DATA_DIR": str(tmp_path)}
    assert not start.accounts_configured(env=env)
    (tmp_path / "users.json").write_text("{}", encoding="utf-8")  # an empty object holds no accounts
    assert not start.accounts_configured(env=env)
    (tmp_path / "users.json").write_text('{"version": 1, "users": {"a": {}}}', encoding="utf-8")
    assert start.accounts_configured(env=env)
    (tmp_path / "users.json").write_text('{"version": 1, "users": {}}', encoding="utf-8")  # last user removed
    assert not start.accounts_configured(env=env)
    (tmp_path / "users.json").write_text("{broken", encoding="utf-8")  # damaged: fail closed
    assert start.accounts_configured(env=env)


def test_tls_options_must_come_as_a_valid_pair(start, tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    assert start.tls_problem(None, None) is None
    assert "together" in start.tls_problem(str(cert), None)
    assert "not found" in start.tls_problem(str(cert), str(key))
    cert.write_text("x", encoding="utf-8")
    key.write_text("x", encoding="utf-8")
    assert start.tls_problem(str(cert), str(key)) is None


def test_exposed_host_message_mentions_accounts(start):
    assert "ragwb user add" in start.host_problem("0.0.0.0", password_set=False)


def test_free_port_skips_a_port_that_is_in_use(start):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        assert start.free_port(taken) != taken


class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def test_wait_until_ready_sees_a_healthy_server_and_stops_when_the_process_died(start):
    server = HTTPServer(("127.0.0.1", 0), Health)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        class Alive:
            @staticmethod
            def poll():
                return None

        assert start.wait_until_ready(server.server_address[1], Alive(), timeout=5, host="127.0.0.1")
    finally:
        server.shutdown()

    class Dead:
        @staticmethod
        def poll():
            return 1

    assert start.wait_until_ready(1, Dead(), timeout=5) is False


def test_the_launcher_refuses_an_exposed_host_without_a_password_before_touching_anything(tmp_path):
    env = {"SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""), "PATH": __import__("os").environ["PATH"],
           "RAGWB_DATA_DIR": str(tmp_path / "data")}
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "start.py"), "--host", "0.0.0.0", "--setup-only"],
                            capture_output=True, text=True, timeout=60, env=env, cwd=tmp_path, check=False)
    assert result.returncode != 0 and "refusing to listen" in result.stderr
    assert not (tmp_path / "data").exists()  # exited before preparing the environment or creating data


def test_help_lists_every_option(start):
    result = subprocess.run([sys.executable, str(PROJECT_ROOT / "start.py"), "--help"], capture_output=True,
                            text=True, timeout=60, check=False)
    assert result.returncode == 0
    for flag in ("--port", "--host", "--no-browser", "--no-examples", "--setup-only"):
        assert flag in result.stdout
