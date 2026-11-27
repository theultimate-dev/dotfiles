"""Fake `claude`, `codex`, `agy` and `git` for agent-sync's unit tests.

Each fake is a small executable on a temporary $PATH that calls main(<name>). It records its argv
(and the one environment variable agent-sync may set) to $FAKE_STATE/calls.jsonl, keeps its own
state in the temporary harness homes, and prints output shaped like the real CLI's, as recorded
by the contract tests (Claude Code 2.1.327-2.1.332, Codex 0.170.0-0.172.0, agy 1.5.9-1.5.18).

Behaviour the tests script goes in $FAKE_STATE/config.json:

    remotes   {url: {ref: {"sha": ..., "tree": dir}}}   what a Git source holds; "HEAD" is the
              default branch. Shared by the fake git, the fake Claude and the fake Codex.
    claude    {"held": {plugin_id: {"command": ..., "sha256": ...}},  a declared command
               "update": {plugin_id: new_version},                    update finds a new version
               "fail": {verb: message}}                               that verb fails
    codex     {"fail": {verb: message},
               "upgrade_skips": [plugin_id],                         upgrade leaves its cache
               "disabled": [plugin_id],                              listed with enabled: false
               "unlisted": [plugin_id]}                              add succeeds, list omits it
    agy       {"plugins": [...]}                                      `agy plugin list --json`
"""

import json
import os
import shutil
import sys


def state_dir():
    return os.environ["FAKE_STATE"]


def config():
    try:
        with open(os.path.join(state_dir(), "config.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def log_call(name, argv):
    try:
        st, null = os.fstat(0), os.stat(os.devnull)
        devnull = (st.st_rdev, st.st_mode & 0o170000) == (null.st_rdev, null.st_mode & 0o170000)
    except OSError:
        devnull = False
    entry = {"cmd": name, "argv": argv, "cwd": os.getcwd(), "stdin_tty": sys.stdin.isatty(),
             "stdin_devnull": devnull,
             "nonessential_traffic": os.environ.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"),
             "git_env": sorted(k for k in os.environ if k.startswith("GIT_"))}
    with open(os.path.join(state_dir(), "calls.jsonl"), "a") as f:
        f.write(json.dumps(entry) + "\n")


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)


def remote_tree(url, ref=None):
    refs = config().get("remotes", {}).get(url)
    if refs is None:
        return None
    return refs.get(ref or "HEAD")


def catalog(tree):
    with open(os.path.join(tree, ".claude-plugin", "marketplace.json")) as f:
        return json.load(f)


def catalog_entry(tree, plugin):
    for entry in catalog(tree).get("plugins", []):
        if entry.get("name") == plugin:
            return entry
    return None


def plugin_dir(tree, entry):
    src = entry.get("source")
    return os.path.normpath(os.path.join(tree, src)) if isinstance(src, str) else None


def entry_version(tree, entry):
    if entry.get("version"):
        return entry["version"]
    d = plugin_dir(tree, entry)
    try:
        with open(os.path.join(d, ".claude-plugin", "plugin.json")) as f:
            return json.load(f).get("version") or "0.1.0"
    except (OSError, TypeError, ValueError):
        return "0.1.0"


def flag(argv, name):
    if name in argv:
        i = argv.index(name)
        value = argv[i + 1]
        del argv[i:i + 2]
        return value
    return None


def drop(argv, *names):
    for n in names:
        while n in argv:
            argv.remove(n)


# ── claude ────────────────────────────────────────────────────────────────────────────────────

def claude(argv):
    cfg = config().get("claude", {})
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.environ["HOME"], ".claude")
    path = os.path.join(home, "fake-state.json")
    st = load(path, {"marketplaces": [], "plugins": [], "accepted": {}})
    out = lambda doc: print(json.dumps(doc, separators=(",", ":")))  # noqa: E731

    if argv[:1] != ["plugin"]:
        print("fake claude: unsupported %r" % argv, file=sys.stderr)
        return 2
    args = argv[1:]
    verb = " ".join(args[:2]) if args[:1] == ["marketplace"] else args[0]
    if verb in cfg.get("fail", {}):
        out({"command": verb, "outcome": "failed", "message": cfg["fail"][verb]})
        return 1
    scope = flag(args, "--scope")
    accept = flag(args, "--accept-command")
    drop(args, "--json")

    if verb == "marketplace list":
        print(json.dumps(st["marketplaces"], indent=2))
        return 0
    if verb == "list":
        listed = list(st["plugins"])
        if cfg.get("builtin", True):
            listed.append({"id": "cc-plugin-example@builtin", "version": "unknown",
                           "scope": "user", "enabled": True})
        print(json.dumps(listed, indent=2))
        return 0
    if verb == "marketplace add":
        source = args[2]
        url, _, ref = source.partition("#")
        if os.path.isdir(source):
            name = catalog(source)["name"]
            entry = {"name": name, "source": "directory", "path": source,
                     "installLocation": source}
        else:
            tree = remote_tree(url, ref or None)
            if tree is None:
                out({"command": "marketplace-add", "outcome": "failed",
                     "message": "Failed to clone %s" % url})
                return 1
            name = catalog(tree["tree"])["name"]
            entry = {"name": name, "source": "git", "url": url,
                     "installLocation": os.path.join(home, "plugins", "marketplaces", name)}
            if ref:
                entry["ref"] = ref
        st["marketplaces"] = [m for m in st["marketplaces"] if m["name"] != name] + [entry]
        save(path, st)
        out({"command": "marketplace-add", "outcome": "ok", "marketplace": name,
             "message": "Successfully added marketplace: %s (declared in user settings)" % name})
        return 0
    if verb == "marketplace update":
        name = args[2]
        if not any(m["name"] == name for m in st["marketplaces"]):
            out({"command": "marketplace-update", "outcome": "failed",
                 "message": "Marketplace '%s' not found" % name})
            return 1
        out({"command": "marketplace-update", "outcome": "ok", "marketplace": name,
             "message": "Refreshing marketplace cache (timeout: 120s)…\n"
                        "Successfully updated marketplace: %s" % name})
        return 0

    pid = args[1]
    plugin, _, mname = pid.partition("@")
    mkt = next((m for m in st["marketplaces"] if m["name"] == mname), None)
    installed = next((p for p in st["plugins"] if p["id"] == pid and p["scope"] == "user"), None)
    base = {"command": verb, "plugin": pid, "pluginId": pid, "scope": scope or "user"}
    if verb in ("install", "update"):
        if mkt is None:
            out(dict(base, outcome="failed", message="Marketplace %s not found" % mname))
            return 1
        tree = mkt["path"] if mkt["source"] == "directory" else \
            remote_tree(mkt["url"], mkt.get("ref"))["tree"]
        entry = catalog_entry(tree, plugin)
        if entry is None:
            out(dict(base, outcome="failed",
                     message="Plugin %s not found in marketplace %s" % (plugin, mname)))
            return 1
        held = cfg.get("held", {}).get(pid)
        remembered = verb == "update" and st["accepted"].get(pid) == held.get("command") \
            if held else True
        if held and not remembered:
            if accept == held["sha256"]:
                st["accepted"][pid] = held["command"]
            else:
                shown = {"kind": "command_source", "pluginId": pid, "command": held["command"],
                         "mode": "copy", "catalogRevision": "git:" + "1" * 40,
                         "sha256": held["sha256"]}
                if accept:
                    shown["acceptCommandMatched"] = False
                print('"%s" is installed by running a command from marketplace "%s" on this '
                      'machine:' % (plugin, mname))
                print("  " + held["command"])
                print("Not an interactive terminal, so the command was only displayed, "
                      "not accepted.")
                out(dict(base, outcome="failed", failureCode="command_source_refused",
                         message="%s is installed by running a command on this machine (`%s`) "
                                 "that has not been reviewed yet, so it was not run."
                                 % (pid, held["command"]),
                         shownCommand=shown))
                save(path, st)
                return 1
    if verb == "install":
        version = entry_version(tree, entry)
        record = {"id": pid, "version": version, "scope": "user", "enabled": True,
                  "installPath": os.path.join(home, "plugins", "cache", mname, plugin, version)}
        if mkt["source"] == "directory":
            record["readFromFolder"] = plugin_dir(tree, entry)
        st["plugins"] = [p for p in st["plugins"] if p["id"] != pid] + [record]
        save(path, st)
        print("Installing plugin %s…" % pid)
        out(dict(base, outcome="ok",
                 message="Successfully installed plugin: %s (scope: user)" % pid))
        return 0
    if installed is None:
        out(dict(base, outcome="failed", message="Plugin %s is not installed" % pid))
        return 1
    if verb == "update":
        new = cfg.get("update", {}).get(pid)
        old = installed["version"]
        if new and new != old:
            installed["version"] = new
            save(path, st)
            out(dict(base, outcome="ok", updateOutcome="updated", oldVersion=old, newVersion=new,
                     message="Updated %s from %s to %s." % (plugin, old, new)))
        else:
            out(dict(base, outcome="ok", updateOutcome="up_to_date", oldVersion=old,
                     newVersion=old,
                     message="%s is already at the latest version (%s)." % (plugin, old)))
        return 0
    if verb in ("enable", "disable"):
        installed["enabled"] = verb == "enable"
        save(path, st)
        out(dict(base, outcome="ok", message="Successfully %sd plugin: %s" % (verb, plugin)))
        return 0
    print("fake claude: unsupported %r" % argv, file=sys.stderr)
    return 2


# ── codex ─────────────────────────────────────────────────────────────────────────────────────

def codex_config_toml(home, st):
    lines = []
    for m in st["marketplaces"]:
        lines += ["[marketplaces.%s]" % m["name"], 'source_type = "%s"' % m["sourceType"],
                  'source = "%s"' % m["source"]]
        if m.get("ref"):
            lines.append('ref = "%s"' % m["ref"])
        lines.append("")
    for p in st["plugins"]:
        lines += ['[plugins."%s"]' % p["pluginId"], "enabled = true", ""]
    with open(os.path.join(home, "config.toml"), "w") as f:
        f.write("\n".join(lines))


def codex(argv):
    cfg = config().get("codex", {})
    home = os.environ.get("CODEX_HOME") or os.path.join(os.environ["HOME"], ".codex")
    if not os.path.isdir(home):
        print("Error: failed to resolve CODEX_HOME\n\nCaused by:\n    CODEX_HOME points to %r, "
              "but that path does not exist" % home, file=sys.stderr)
        return 1
    if argv[:1] != ["plugin"]:
        print("Error: stdin is not a terminal", file=sys.stderr)
        return 1
    path = os.path.join(home, "fake-state.json")
    st = load(path, {"marketplaces": [], "plugins": []})
    args = argv[1:]
    verb = " ".join(args[:2]) if args[:1] == ["marketplace"] else args[0]
    if verb in cfg.get("fail", {}):
        print("Error: " + cfg["fail"][verb], file=sys.stderr)
        return 1
    ref = flag(args, "--ref")
    only = flag(args, "--marketplace")
    drop(args, "--json")
    out = lambda doc: print(json.dumps(doc, indent=2))  # noqa: E731

    def snapshot(m):
        if m["sourceType"] != "git":
            return
        tree = remote_tree(m["source"], m.get("ref"))
        if os.path.isdir(m["root"]):
            shutil.rmtree(m["root"])
        shutil.copytree(tree["tree"], m["root"])
        m["sha"] = tree["sha"]

    def install(m, plugin):
        entry = catalog_entry(m["root"], plugin)
        if entry is None:
            return None
        version = entry_version(m["root"], entry)
        dest = os.path.join(home, "plugins", "cache", m["name"], plugin, version)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        shutil.copytree(plugin_dir(m["root"], entry), dest)
        return version, dest

    if verb == "marketplace list":
        out({"marketplaces": [{"name": m["name"], "root": m["root"],
                               "marketplaceSource": {"sourceType": m["sourceType"],
                                                     "source": m["source"]}}
                              for m in st["marketplaces"]]})
        return 0
    if verb == "marketplace add":
        source = args[2]
        if os.path.isdir(source):
            m = {"name": catalog(source)["name"], "root": source, "sourceType": "local",
                 "source": source}
        else:
            tree = remote_tree(source, ref)
            if tree is None:
                print("Error: failed to clone %s" % source, file=sys.stderr)
                return 1
            name = catalog(tree["tree"])["name"]
            m = {"name": name, "root": os.path.join(home, ".tmp", "marketplaces", name),
                 "sourceType": "git", "source": source, "ref": ref}
            snapshot(m)
        st["marketplaces"] = [x for x in st["marketplaces"] if x["name"] != m["name"]] + [m]
        save(path, st)
        codex_config_toml(home, st)
        out({"marketplaceName": m["name"], "installedRoot": m["root"], "alreadyAdded": False})
        return 0
    if verb == "marketplace upgrade":
        m = next((x for x in st["marketplaces"] if x["name"] == args[2]), None)
        roots = []
        if m and m["sourceType"] == "git":
            tree = remote_tree(m["source"], m.get("ref"))
            # C3: upgradedRoots 1, 0, 0 -- the first upgrade refreshes, an unmoved ref then skips
            if tree["sha"] != m.get("sha") or not m.get("upgraded"):
                snapshot(m)
                for p in st["plugins"]:
                    if p["marketplaceName"] == m["name"] and \
                            p["pluginId"] not in cfg.get("upgrade_skips", []):
                        got = install(m, p["name"])
                        if got:
                            p["version"] = got[0]
                roots.append(m["root"])
            m["upgraded"] = True
        save(path, st)
        out({"selectedMarketplaces": [args[2]], "upgradedRoots": roots, "errors": []})
        return 0
    if verb == "add":
        pid = args[1]
        plugin, _, mname = pid.partition("@")
        m = next((x for x in st["marketplaces"] if x["name"] == mname), None)
        got = install(m, plugin) if m else None
        if got is None:
            print("Error: plugin `%s` was not found in marketplace `%s`" % (plugin, mname),
                  file=sys.stderr)
            return 1
        version, dest = got
        st["plugins"] = [p for p in st["plugins"] if p["pluginId"] != pid] + (
            [] if pid in cfg.get("unlisted", []) else
            [{"pluginId": pid, "name": plugin, "marketplaceName": mname, "version": version}])
        save(path, st)
        codex_config_toml(home, st)
        out({"pluginId": pid, "name": plugin, "marketplaceName": mname, "version": version,
             "installedPath": dest, "authPolicy": "ON_INSTALL"})
        return 0
    if verb == "list":
        installed = []
        for p in st["plugins"]:
            if only and p["marketplaceName"] != only:
                continue
            installed.append(dict(p, installed=True,
                                  enabled=p["pluginId"] not in cfg.get("disabled", []),
                                  source={"source": "local", "path": os.path.join(
                                      home, ".tmp", "marketplaces", p["marketplaceName"],
                                      "plugins", p["name"])},
                                  installPolicy="AVAILABLE", authPolicy="ON_INSTALL"))
        out({"installed": installed, "available": []})
        return 0
    print("Error: stdin is not a terminal", file=sys.stderr)
    return 1


# ── agy ───────────────────────────────────────────────────────────────────────────────────────

def agy(argv):
    if argv[:2] == ["plugin", "list"]:
        print(json.dumps(config().get("agy", {}).get("plugins", [])))
        return 0
    print("fake agy: unsupported %r" % argv, file=sys.stderr)
    return 2


# ── git ───────────────────────────────────────────────────────────────────────────────────────

def git(argv):
    args = list(argv)
    cwd, links = None, True
    while args[:1] in (["-C"], ["--git-dir"], ["--work-tree"], ["-c"]):
        key, value = args[:2]
        args = args[2:]
        if key in ("-C", "--work-tree"):
            cwd = value
        if key == "-c" and value == "core.symlinks=false":
            links = False
    drop(args, "--no-optional-locks", "--")
    meta_path = os.path.join(cwd or ".", ".git", "fake.json")
    meta = load(meta_path, None)
    if args[:2] == ["clone", "--no-checkout"]:
        url, dest = args[2], args[3]
        if config().get("remotes", {}).get(url) is None:
            print("fatal: repository '%s' not found" % url, file=sys.stderr)
            return 128
        os.makedirs(os.path.join(dest, ".git"))
        save(os.path.join(dest, ".git", "fake.json"), {"url": url})
        return 0
    if meta is None:
        print("fatal: not a git repository", file=sys.stderr)
        return 128
    if args[:2] == ["fetch", "--tags"]:
        tree = remote_tree(meta["url"], args[3])
        if tree is None:
            print("fatal: couldn't find remote ref %s" % args[3], file=sys.stderr)
            return 128
        meta["fetched"] = tree
        save(meta_path, meta)
        return 0
    if args[:3] == ["checkout", "--detach", "FETCH_HEAD"]:
        for name in os.listdir(cwd):
            if name != ".git":
                p = os.path.join(cwd, name)
                shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        tree = meta["fetched"]
        shutil.copytree(tree["tree"], cwd, dirs_exist_ok=True, symlinks=True)
        for d, dirs, names in os.walk(cwd):
            for n in dirs + names:      # core.symlinks=false: a link is a file holding its target
                p = os.path.join(d, n)
                if os.path.islink(p) and not links:
                    target = os.readlink(p)
                    os.remove(p)
                    with open(p, "w") as f:
                        f.write(target)
        meta["head"] = tree["sha"]
        save(meta_path, meta)
        return 0
    if args[:2] == ["rev-parse", "HEAD"]:
        if not meta.get("head"):
            print("fatal: ambiguous argument 'HEAD'", file=sys.stderr)
            return 128
        print(meta["head"])
        return 0
    if args[:3] == ["remote", "get-url", "origin"]:
        print(meta["url"])
        return 0
    if args[:2] == ["status", "--porcelain"]:
        if meta.get("dirty"):
            print(" M SKILL.md")
        return 0
    print("fake git: unsupported %r" % argv, file=sys.stderr)
    return 2


def main(name):
    argv = sys.argv[1:]
    log_call(name, argv)
    sys.exit({"claude": claude, "codex": codex, "agy": agy, "git": git}[name](argv))
