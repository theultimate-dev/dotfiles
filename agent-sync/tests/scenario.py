"""A standard machine for the adapter and end-to-end tests: the two fixture catalogs as Git
remotes, a checkout of the first, and a manifest shaped like the example (spec §3)."""

import json
import os
import shutil

import support

URL = "https://example.invalid/example-org/example-skills.git"
VURL = "https://example.invalid/example-vendor/agent-plugins.git"
SKILLS_MAIN = support.sha(1)
VENDOR_TAG = support.sha(2)
CHECKOUT_HEAD = support.sha(3)

MANIFEST = """\
version = 1
harnesses = {harnesses}

[[marketplace]]
name      = "example-skills"
git       = "{url}"
ref       = "main"
checkout  = "~/src/example-skills"
claude    = "checkout"
codex     = "git"
agy       = "checkout"
harnesses = ["claude", "codex", "agy"]
plugins   = "all"
exclude   = ["experiments"]

[[marketplace]]
name      = "example-vendor-plugins"
git       = "{vurl}"
ref       = "v2.3.0"
claude    = "git"
codex     = "git"
agy       = "{vendor_agy}"
harnesses = {vendor_harnesses}

[[plugin]]
id         = "reviewing@example-skills"
agy_skills = ["reviewing-code-changes"]

[[plugin]]
id        = "deploying@example-skills"
harnesses = ["claude", "codex"]

[[plugin]]
id = "editor-integration@example-vendor-plugins"
{extra}
[external]
skills = ["find-skills"]
"""


def setup(sb, harnesses='["claude", "codex", "agy"]', extra="", vendor_agy="none",
          vendor_harnesses='["claude", "codex"]'):
    """Remotes, checkout and manifest. Returns the checkout path."""
    sb.remote(URL, "catalog-flat", SKILLS_MAIN, ref="main")
    sb.remote(VURL, "catalog-shared", VENDOR_TAG, ref="v2.3.0")
    checkout = sb.checkout("catalog-flat", "src/example-skills", head=CHECKOUT_HEAD)
    sb.manifest(MANIFEST.format(harnesses=harnesses, url=URL, vurl=VURL, extra=extra,
                                vendor_agy=vendor_agy, vendor_harnesses=vendor_harnesses))
    return checkout


def move_remote(sb, url, ref, fixture_tree, new_sha):
    """Point a remote ref at a new commit whose tree is a copy of `fixture_tree`."""
    tree = os.path.join(sb.root, "remotes", new_sha)
    if os.path.exists(tree):
        shutil.rmtree(tree)
    shutil.copytree(fixture_tree, tree)
    sb.config["remotes"][url][ref] = {"sha": new_sha, "tree": tree}
    sb.save_config()
    return tree


def add_plugin(catalog, name, skills, version="0.1.0"):
    """Add a plugin with the given skills to a flat-layout catalog tree."""
    path = os.path.join(catalog, ".claude-plugin", "marketplace.json")
    with open(path) as f:
        doc = json.load(f)
    doc["plugins"].append({"name": name, "source": "./plugins/" + name})
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)
    pdir = os.path.join(catalog, "plugins", name)
    os.makedirs(os.path.join(pdir, ".claude-plugin"))
    with open(os.path.join(pdir, ".claude-plugin", "plugin.json"), "w") as f:
        json.dump({"name": name, "version": version}, f)
    for s in skills:
        write_skill(os.path.join(pdir, "skills", s), s)


def write_skill(path, name, body="Fixture skill.", front_name=None):
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "SKILL.md"), "w") as f:
        f.write("---\nname: %s\ndescription: test\n---\n\n%s\n" % (front_name or name, body))


def contents(root):
    """Every path under root with its bytes' digest, a link's target, or 'dir'."""
    import hashlib
    out = {}
    for d, dirs, names in os.walk(root):
        for n in dirs + names:
            p = os.path.join(d, n)
            if os.path.islink(p):
                out[os.path.relpath(p, root)] = "link:" + os.readlink(p)
            elif os.path.isdir(p):
                out[os.path.relpath(p, root)] = "dir"
            else:
                with open(p, "rb") as f:
                    out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()
    return out


def mtimes(root):
    out = {}
    for d, dirs, names in os.walk(root):
        for n in dirs + names:
            p = os.path.join(d, n)
            out[os.path.relpath(p, root)] = os.lstat(p).st_mtime_ns
    return out
