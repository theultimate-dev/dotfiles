"""Shared fixtures for the agent-sync contract tests (spec §12, C0–C6).

These tests run the real `claude`, `codex` and `agy` CLIs. Three rules keep the machine's real
agent homes out of reach:

1. Every CLI runs with an environment built from an allowlist, never inherited: HOME,
   CLAUDE_CONFIG_DIR, CODEX_HOME and every XDG_* variable point inside a fresh temp directory, and
   no session, account or API-key variable from the caller passes through.
2. Every CLI runs under `sandbox-exec` with a profile that denies file writes anywhere under the
   real home directory, so a harness that ignores HOME fails loudly instead of writing there.
   Outbound IP networking is denied too, unless a test asks for it; the fixtures are local Git
   repositories, so no test needs it.
3. stdin is /dev/null, argv is a list, no shell; each call has a timeout and is killed with its
   process group when it runs over.

Observations go to a JSON-lines file (AGENT_SYNC_CONTRACT_RESULTS, or a file in the system temp
directory) with temp paths and the real home redacted, so the results can be quoted publicly.
"""

import datetime
import hashlib
import json
import os
import pwd
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

ENABLED = os.environ.get("AGENT_SYNC_CONTRACT") == "1"

skip_unless_enabled = unittest.skipUnless(
    ENABLED, "contract tests run the real CLIs; set AGENT_SYNC_CONTRACT=1 to run them"
)

REAL_HOME = os.path.realpath(pwd.getpwuid(os.getuid()).pw_dir)

MARKETPLACE = "example-skills"
OWNER = "example-org"

_RESULTS_PATH = None


def results_path():
    global _RESULTS_PATH
    if _RESULTS_PATH is None:
        explicit = os.environ.get("AGENT_SYNC_CONTRACT_RESULTS")
        if explicit:
            _RESULTS_PATH = explicit
        else:
            stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
            _RESULTS_PATH = os.path.join(
                tempfile.gettempdir(), "agent-sync-contract-%s.jsonl" % stamp
            )
    return _RESULTS_PATH


def which(name):
    return shutil.which(name)


def version_of(argv):
    """Version string of a CLI, run in a throwaway isolated home."""
    with IsolatedHome("version") as iso:
        r = iso.run(argv, timeout=60)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else ""


class Result:
    def __init__(self, argv, returncode, stdout, stderr, seconds, timed_out):
        self.argv = argv
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.seconds = seconds
        self.timed_out = timed_out

    def json_lines(self):
        """Every stdout line that parses as JSON, in order."""
        out = []
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
        return out

    def json(self):
        """stdout as one JSON document, or the last JSON line, or None."""
        try:
            return json.loads(self.stdout)
        except ValueError:
            lines = self.json_lines()
            return lines[-1] if lines else None


class IsolatedHome:
    """A fresh temp directory standing in for $HOME, and a way to run CLIs inside it."""

    def __init__(self, label):
        self.label = label
        self.root = None

    def __enter__(self):
        # realpath: /var/folders is a symlink to /private/var/folders, and the CLIs report
        # resolved paths; redaction must match either spelling.
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="agent-sync-contract-"))
        self.home = os.path.join(self.root, "home")
        self.work = os.path.join(self.root, "work")
        self.tmp = os.path.join(self.root, "tmp")
        self.claude_home = os.path.join(self.home, ".claude")
        self.codex_home = os.path.join(self.home, ".codex")
        # Codex refuses a CODEX_HOME that does not exist ("failed to resolve CODEX_HOME").
        for d in (self.home, self.work, self.tmp, self.codex_home):
            os.makedirs(d)
        self.started = datetime.datetime.now()
        self.env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "HOME": self.home,
            "USER": os.environ.get("USER", ""),
            "LOGNAME": os.environ.get("LOGNAME", os.environ.get("USER", "")),
            "SHELL": "/bin/sh",
            "TMPDIR": self.tmp + "/",
            "LANG": "en_US.UTF-8",
            "TERM": "dumb",
            "NO_COLOR": "1",
            "CLAUDE_CONFIG_DIR": self.claude_home,
            "CODEX_HOME": self.codex_home,
            "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
            "XDG_DATA_HOME": os.path.join(self.home, ".local", "share"),
            "XDG_STATE_HOME": os.path.join(self.home, ".local", "state"),
            "XDG_CACHE_HOME": os.path.join(self.home, ".cache"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "agent-sync fixture",
            "GIT_AUTHOR_EMAIL": "agent-sync-fixture",
            "GIT_COMMITTER_NAME": "agent-sync fixture",
            "GIT_COMMITTER_EMAIL": "agent-sync-fixture",
        }
        self._profiles = {}
        return self

    def __exit__(self, *exc):
        if self.root and os.environ.get("AGENT_SYNC_CONTRACT_KEEP") != "1":
            shutil.rmtree(self.root, ignore_errors=True)
        return False

    # -- running ----------------------------------------------------------------------------

    def _profile(self, network):
        if network not in self._profiles:
            rules = [
                "(version 1)",
                "(allow default)",
                '(deny file-write* (subpath "%s"))' % REAL_HOME,
            ]
            if not network:
                rules.append("(deny network-outbound (remote ip))")
            path = os.path.join(self.root, "sandbox-%s.sb" % ("net" if network else "nonet"))
            with open(path, "w") as f:
                f.write("\n".join(rules) + "\n")
            self._profiles[network] = path
        return self._profiles[network]

    def run(self, argv, timeout=120, network=False, cwd=None, extra_env=None):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        full = ["/usr/bin/sandbox-exec", "-f", self._profile(network)] + list(argv)
        start = time.monotonic()
        proc = subprocess.Popen(
            full,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=cwd or self.work,
            start_new_session=True,
        )
        timed_out = False
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            out, err = proc.communicate()
        return Result(
            list(argv),
            proc.returncode,
            out.decode("utf-8", "replace"),
            err.decode("utf-8", "replace"),
            round(time.monotonic() - start, 2),
            timed_out,
        )

    def git(self, *args, cwd=None):
        r = self.run(["git"] + list(args), cwd=cwd, timeout=60)
        if r.returncode != 0:
            raise RuntimeError("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
        return r.stdout.strip()

    # -- redaction --------------------------------------------------------------------------

    def redact(self, text):
        if not isinstance(text, str):
            return text
        for path, token in ((self.home, "$HOME"), (self.root, "$T"), (REAL_HOME, "~")):
            # /var and /tmp are symlinks into /private; a CLI may print either spelling.
            other = path[len("/private"):] if path.startswith("/private/") else "/private" + path
            text = text.replace(path, token).replace(other, token)
        return text

    # -- fixture catalogs -------------------------------------------------------------------

    def make_catalog(self, name=MARKETPLACE, plugins=None, extra_entries=None):
        """A Claude-format marketplace as a local Git repository; returns its path.

        plugins: {plugin_name: {"version": str, "skills": {skill_name: body}}}
        extra_entries: raw marketplace.json plugin entries appended as given.
        """
        if plugins is None:
            plugins = {"alpha": {"version": "0.1.0", "skills": {"alpha-skill": "First body."}}}
        repo = os.path.join(self.work, name)
        os.makedirs(os.path.join(repo, ".claude-plugin"))
        entries = []
        for pname, spec in plugins.items():
            pdir = os.path.join(repo, "plugins", pname)
            os.makedirs(os.path.join(pdir, ".claude-plugin"))
            write_json(os.path.join(pdir, ".claude-plugin", "plugin.json"), {
                "name": pname,
                "version": spec["version"],
                "description": "Fixture plugin %s." % pname,
            })
            for sname, body in spec["skills"].items():
                write_skill(pdir, sname, body)
            entries.append({
                "name": pname,
                "source": "./plugins/%s" % pname,
                "description": "Fixture plugin %s." % pname,
                "version": spec["version"],
            })
        entries.extend(extra_entries or [])
        write_json(os.path.join(repo, ".claude-plugin", "marketplace.json"), {
            "name": name,
            "owner": {"name": OWNER},
            "plugins": entries,
        })
        self.git("init", "-q", "-b", "main", cwd=repo)
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", "fixture catalog", cwd=repo)
        return repo

    def commit_all(self, repo, message):
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", message, cwd=repo)
        return self.git("rev-parse", "HEAD", cwd=repo)


def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


def write_skill(plugin_dir, skill, body):
    sdir = os.path.join(plugin_dir, "skills", skill)
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "SKILL.md"), "w") as f:
        f.write("---\nname: %s\ndescription: Fixture skill %s.\n---\n\n%s\n" % (skill, skill, body))


# -- snapshots ------------------------------------------------------------------------------

def snapshot(root):
    """{relative path: (kind, size, sha256 | link target)} for everything under root."""
    snap = {}
    if not os.path.lexists(root):
        return snap
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            p = os.path.join(dirpath, d)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                snap[rel] = ("link", 0, os.readlink(p))
                dirnames.remove(d)
            else:
                snap[rel] = ("dir", 0, "")
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            if os.path.islink(p):
                snap[rel] = ("link", 0, os.readlink(p))
                continue
            try:
                with open(p, "rb") as f:
                    data = f.read()
                snap[rel] = ("file", len(data), hashlib.sha256(data).hexdigest())
            except OSError as e:
                snap[rel] = ("unreadable", 0, str(e))
    return snap


def diff_snapshots(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def tree_digest(root):
    """SHA-256 over sorted relative paths and bytes, skipping dot-names (spec §6, step 1)."""
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fn in sorted(f for f in filenames if not f.startswith(".")):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            h.update(rel.encode() + b"\0")
            with open(p, "rb") as f:
                h.update(f.read())
            h.update(b"\0")
    return h.hexdigest()


def find_files(root, name):
    hits = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if name in filenames:
            hits.append(os.path.join(dirpath, name))
    return sorted(hits)


# -- sandbox denials -----------------------------------------------------------------------

def sandbox_denials(since, kind, until=None):
    """Kernel sandbox denials of `kind` ("file-write" or "network-outbound") in a time window.

    The profile denies writes under the real home and outbound IP, so a denial means a CLI
    tried one of them. The kernel logs every denial with the process name and PID.
    """
    argv = ["/usr/bin/log", "show", "--style", "compact",
            "--start", since.strftime("%Y-%m-%d %H:%M:%S")]
    if until is not None:
        argv += ["--end", (until + datetime.timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")]
    predicate = 'eventMessage CONTAINS "Sandbox:" AND eventMessage CONTAINS "%s"' % kind
    if kind == "file-write":
        predicate += ' AND eventMessage CONTAINS "%s/"' % REAL_HOME
    argv += ["--predicate", predicate]
    r = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=120)
    lines = r.stdout.decode("utf-8", "replace").splitlines()
    return [ln.replace(REAL_HOME, "~") for ln in lines if "Sandbox:" in ln and "deny(" in ln]


def real_home_write_denials(since):
    return sandbox_denials(since, "file-write")


# -- the base class -------------------------------------------------------------------------

CLIS = {
    "claude": ["claude", "--version"],
    "codex": ["codex", "--version"],
    "agy": ["agy", "--version"],
}

_VERSIONS = {}


def versions():
    """Version of each installed CLI, measured once per process."""
    if not _VERSIONS:
        for name, argv in CLIS.items():
            _VERSIONS[name] = version_of(argv) if which(name) else "not installed"
    return dict(_VERSIONS)


@skip_unless_enabled
class ContractCase(unittest.TestCase):
    """One isolated home per test; any write attempted under the real home fails the test."""

    TEST_ID = "C?"
    NEEDS = ()

    def setUp(self):
        for name in self.NEEDS:
            if not which(name):
                self.skipTest("%s is not installed" % name)
        self.iso = IsolatedHome(self.TEST_ID)
        self.iso.__enter__()
        self.addCleanup(self.iso.__exit__, None, None, None)
        record(self.iso, self.TEST_ID, "versions", versions=versions(), test=self.id())

    def tearDown(self):
        denials = real_home_write_denials(self.iso.started)
        record(self.iso, self.TEST_ID, "real-home write denials", denials=denials)
        self.assertEqual(denials, [], "a CLI tried to write under the real home; see results")

    # -- helpers --------------------------------------------------------------------------

    def run_cli(self, step, argv, **kw):
        r = self.iso.run(argv, **kw)
        record(self.iso, self.TEST_ID, step, r)
        if r.timed_out:
            self.fail("%s timed out after %ss and was killed (interactive prompt or model "
                      "session?); see results" % (" ".join(argv), r.seconds))
        return r

    def ok(self, step, argv, **kw):
        r = self.run_cli(step, argv, **kw)
        self.assertEqual(r.returncode, 0, "%s failed: %s %s" % (
            " ".join(argv), self.iso.redact(r.stdout[-800:]), self.iso.redact(r.stderr[-800:])))
        return r

    def prove_isolated(self, harness):
        """A read-only list in the isolated home shows an empty state (before any mutation)."""
        if harness == "claude":
            for argv in (["claude", "plugin", "marketplace", "list", "--json"],
                         ["claude", "plugin", "list", "--json"]):
                r = self.ok("isolation proof", argv, timeout=120)
                # From 2.1.332 the plugin list also carries plugins bundled with Claude Code
                # itself (`<name>@builtin`, version "unknown"), even in an empty home.
                entries = [e for e in json.loads(r.stdout)
                           if not str(e.get("id", "")).endswith("@builtin")]
                self.assertEqual(entries, [], "isolated Claude home is not empty")
        elif harness == "codex":
            r = self.ok("isolation proof",
                        ["codex", "plugin", "marketplace", "list", "--json"], timeout=120)
            self.assertEqual(json.loads(r.stdout).get("marketplaces"), [],
                             "isolated Codex home is not empty")
        elif harness == "agy":
            # The real agy list is empty too, so emptiness alone proves nothing: also require
            # that agy created its state inside the temp HOME and tried no write in the real one.
            r = self.ok("isolation proof", ["agy", "plugin", "list", "--json"], timeout=120)
            self.assertEqual(json.loads(r.stdout), [], "isolated agy home is not empty")
            created = os.path.isdir(os.path.join(self.iso.home, ".gemini"))
            denials = real_home_write_denials(self.iso.started)
            record(self.iso, self.TEST_ID, "agy isolation evidence",
                   gemini_dir_created_in_temp_home=created, denials=denials)
            if not created or denials:
                self.skipTest("agy cannot be shown to honour HOME; its mutating test is not run")
        else:
            raise ValueError(harness)

    def git_url_for(self, repo):
        """A Git URL that resolves to a local repository, through the isolated git config.

        Claude refuses file:// sources ("owner/repo, https://..., or ./path"), so the tests give
        both CLIs an https URL on a reserved domain and map it onto the fixture with
        url.<base>.insteadOf in the temp HOME's ~/.gitconfig. Nothing reaches the network.
        """
        url = "https://example.invalid/%s/%s.git" % (OWNER, os.path.basename(repo))
        self.iso.git("config", "--global", "url.file://%s.insteadOf" % repo, url)
        return url


# -- recording ------------------------------------------------------------------------------

def record(iso, test_id, step, result=None, **fields):
    """Append one observation to the results file, redacted."""
    entry = {"test": test_id, "step": step}
    if result is not None:
        entry.update({
            "argv": [iso.redact(a) for a in result.argv],
            "returncode": result.returncode,
            "timed_out": result.timed_out,
            "seconds": result.seconds,
            "stdout": iso.redact(result.stdout[-6000:]),
            "stderr": iso.redact(result.stderr[-4000:]),
        })
    for k, v in fields.items():
        entry[k] = _redact_obj(iso, v)
    with open(results_path(), "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def _redact_obj(iso, v):
    if isinstance(v, str):
        return iso.redact(v)
    if isinstance(v, dict):
        return {k: _redact_obj(iso, x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_redact_obj(iso, x) for x in v]
    return v
