"""Shared helpers for agent-sync's unit tests.

Every test runs agent-sync in a Sandbox: a fresh temporary directory holding the home, the XDG
directories, CLAUDE_CONFIG_DIR, CODEX_HOME and a bin directory with the fake claude, codex, agy and
git. The environment handed to agent-sync is built from nothing, so no real harness, home or
network can be reached: PATH holds the fakes only.
"""

import contextlib
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(TESTS))
SCRIPT = os.path.join(REPO, "scripts", "agent-sync")
FIXTURES = os.path.join(TESTS, "fixtures")
FAKES = os.path.join(TESTS, "fakes")
EXAMPLE = os.path.join(REPO, "agent-sync", "manifest.example.toml")

_module = None


def load_script():
    """The script as a module; it has no .py suffix, so it is loaded by path."""
    global _module
    if _module is None:
        loader = importlib.machinery.SourceFileLoader("agent_sync", SCRIPT)
        spec = importlib.util.spec_from_loader("agent_sync", loader)
        _module = importlib.util.module_from_spec(spec)
        loader.exec_module(_module)
    return _module


def sha(n):
    """A fake commit id: n repeated to 40 hex digits."""
    return (str(n) * 40)[:40]


class Sandbox:
    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="agent-sync-test-"))
        assert self.root.startswith(os.path.realpath(tempfile.gettempdir()))
        self.home = os.path.join(self.root, "home")
        self.claude_home = os.path.join(self.home, ".claude")
        self.codex_home = os.path.join(self.home, ".codex")
        self.config_home = os.path.join(self.home, ".config")
        self.state_home = os.path.join(self.home, ".local", "state")
        self.cache_home = os.path.join(self.home, ".cache")
        self.bin = os.path.join(self.root, "bin")
        self.fake_state = os.path.join(self.root, "fake")
        for d in (self.home, self.claude_home, self.codex_home, self.bin, self.fake_state,
                  os.path.join(self.root, "tmp")):
            os.makedirs(d, exist_ok=True)
        for name in ("claude", "codex", "agy", "git"):
            self.install_fake(name)
        self.config = {"remotes": {}}
        self.save_config()
        self.state_dir = os.path.join(self.state_home, "agent-sync")
        self.agy_skills = os.path.join(self.home, ".gemini", "config", "skills")

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # -- the fakes ------------------------------------------------------------------------

    def install_fake(self, name):
        path = os.path.join(self.bin, name)
        with open(path, "w") as f:
            f.write("#!%s\nimport sys\nsys.path.insert(0, %r)\nimport fake\nfake.main(%r)\n"
                    % (sys.executable, FAKES, name))
        os.chmod(path, 0o755)

    def used(self, *homes):
        """Give each harness home a file, as a harness that has run once leaves: an empty home
        is uninitialised, and a dry run or --check does not call its harness (spec §8)."""
        for h in homes or (self.claude_home, self.codex_home):
            with open(os.path.join(h, "history.jsonl"), "w") as f:
                f.write("")

    def remove_fake(self, name):
        os.remove(os.path.join(self.bin, name))

    def save_config(self):
        with open(os.path.join(self.fake_state, "config.json"), "w") as f:
            json.dump(self.config, f, indent=2)

    def set(self, section, key, value):
        self.config.setdefault(section, {})[key] = value
        self.save_config()

    def calls(self, cmd=None):
        path = os.path.join(self.fake_state, "calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as f:
            calls = [json.loads(line) for line in f]
        return [c for c in calls if cmd is None or c["cmd"] == cmd]

    def argvs(self, cmd):
        return [c["argv"] for c in self.calls(cmd)]

    def clear_calls(self):
        path = os.path.join(self.fake_state, "calls.jsonl")
        if os.path.exists(path):
            os.remove(path)

    # -- sources --------------------------------------------------------------------------

    def copy_fixture(self, fixture, dest):
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(os.path.join(FIXTURES, fixture), dest)
        return dest

    def remote(self, url, fixture, sha_, ref="HEAD", tree=None):
        """Register a Git remote whose `ref` holds a copy of `fixture` at commit `sha_`."""
        if tree is None:
            tree = self.copy_fixture(fixture, os.path.join(self.root, "remotes", sha_))
        self.config["remotes"].setdefault(url, {})[ref] = {"sha": sha_, "tree": tree}
        if ref != "HEAD":
            self.config["remotes"][url].setdefault("HEAD", {"sha": sha_, "tree": tree})
        self.save_config()
        return tree

    def checkout(self, fixture, rel, head=None, dirty=False):
        """A local working tree under the sandbox home, with the fake git's metadata."""
        dest = self.copy_fixture(fixture, os.path.join(self.home, rel))
        self.set_checkout(dest, head or sha(3), dirty)
        return dest

    def set_checkout(self, path, head, dirty=False):
        os.makedirs(os.path.join(path, ".git"), exist_ok=True)
        with open(os.path.join(path, ".git", "fake.json"), "w") as f:
            json.dump({"url": "local", "head": head, "dirty": dirty}, f)

    # -- running agent-sync ---------------------------------------------------------------

    def env(self):
        return {
            "HOME": self.home,
            "USER": "tester",
            "LANG": "en_US.UTF-8",
            "PATH": self.bin,
            "TMPDIR": os.path.join(self.root, "tmp"),
            "XDG_CONFIG_HOME": self.config_home,
            "XDG_STATE_HOME": self.state_home,
            "XDG_CACHE_HOME": self.cache_home,
            "XDG_DATA_HOME": os.path.join(self.home, ".local", "share"),
            "CLAUDE_CONFIG_DIR": self.claude_home,
            "CODEX_HOME": self.codex_home,
            "FAKE_STATE": self.fake_state,
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def manifest(self, text):
        path = os.path.join(self.config_home, "agent-sync", "manifest.toml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def run(self, *args, input=None, timeout=60):
        env = self.env()
        assert env["HOME"].startswith(self.root) and env["PATH"] == self.bin
        return subprocess.run([sys.executable, SCRIPT] + list(args), env=env, cwd=self.root,
                              input=input, stdin=None if input is not None else subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout)

    @contextlib.contextmanager
    def active(self):
        """Point this process's environment at the sandbox, for in-process tests."""
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(self.env())
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(saved)


class SandboxCase:
    """Mixin for unittest.TestCase: a fresh sandbox per test, removed afterwards."""

    def setUp(self):
        super().setUp()
        self.sb = Sandbox()
        self.addCleanup(self.sb.close)


def rows(result):
    """The JSON report rows of a `--json` run, and its summary line."""
    lines = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    return [r for r in lines if "result" in r], next((r for r in lines if "summary" in r), None)


def cache_name(kind, url, ref=None):
    """The folder agent-sync caches a Git source in: named by the request, kind, URL and ref,
    never by a name, so no two sources share one on any volume (spec §10)."""
    return hashlib.sha256(("%s\n%s\n%s" % (kind, url, ref or "")).encode()).hexdigest()


def find(rows_, harness=None, item=None, result=None):
    return [r for r in rows_ if (harness is None or r["harness"] == harness)
            and (item is None or r["item"] == item) and (result is None or r["result"] == result)]
