"""C0: do the plugin commands work without model access (logged out, offline)?

Pass condition (spec §12): add, install and list succeed in a home with no credentials. Every
call here runs with outbound networking denied, so "offline" is enforced, not assumed. The
macOS Keychain is never touched: "logged out" is whatever each CLI reports in the temp home.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import harness as h  # noqa: E402


class ClaudeWithoutCredentials(h.ContractCase):
    TEST_ID = "C0"
    NEEDS = ("claude", "git")

    def test_plugin_verbs_work_logged_out_and_offline(self):
        status = self.run_cli("claude auth status", ["claude", "auth", "status", "--json"])
        auth = status.json() or {}
        h.record(self.iso, self.TEST_ID, "claude logged in?", logged_in=auth.get("loggedIn"),
                 auth_method=auth.get("authMethod"), returncode=status.returncode)
        self.assertIs(auth.get("loggedIn"), False, "the isolated Claude home is signed in")

        self.prove_isolated("claude")
        checkout = self.iso.make_catalog()
        self.ok("claude marketplace add (directory)",
                ["claude", "plugin", "marketplace", "add", "--scope", "user", "--json", checkout])
        self.ok("claude install", ["claude", "plugin", "install", "--scope", "user", "--json",
                                   "alpha@%s" % h.MARKETPLACE])
        listed = self.ok("claude plugin list", ["claude", "plugin", "list", "--json"]).json()
        self.assertEqual([p["id"] for p in listed if not p["id"].endswith("@builtin")],
                         ["alpha@%s" % h.MARKETPLACE])
        self.assertTrue(listed[0]["enabled"])

        # And a Git source, which goes through `git clone` rather than a directory read.
        git_catalog = self.iso.make_catalog(name="example-git-skills")
        self.ok("claude marketplace add (git)",
                ["claude", "plugin", "marketplace", "add", "--json", self.git_url_for(git_catalog)])
        self.ok("claude install (git)",
                ["claude", "plugin", "install", "--json", "alpha@example-git-skills"])
        self.ok("claude marketplace update (git)",
                ["claude", "plugin", "marketplace", "update", "--json", "example-git-skills"])
        self.ok("claude plugin update (git)",
                ["claude", "plugin", "update", "--scope", "user", "--json",
                 "alpha@example-git-skills"])
        self.ok("claude plugin disable", ["claude", "plugin", "disable", "--scope", "user",
                                          "--json", "alpha@example-git-skills"])
        self.ok("claude plugin enable", ["claude", "plugin", "enable", "--scope", "user",
                                         "--json", "alpha@example-git-skills"])

        status = self.run_cli("claude auth status, after",
                              ["claude", "auth", "status", "--json"])
        self.assertIs((status.json() or {}).get("loggedIn"), False)


class CodexWithoutCredentials(h.ContractCase):
    TEST_ID = "C0"
    NEEDS = ("codex", "git")

    def test_plugin_verbs_work_logged_out_and_offline(self):
        status = self.run_cli("codex login status", ["codex", "login", "status"])
        h.record(self.iso, self.TEST_ID, "codex logged in?", returncode=status.returncode,
                 output=(status.stdout + status.stderr).strip())
        self.assertNotEqual(status.returncode, 0, "the isolated Codex home is signed in")

        self.prove_isolated("codex")
        catalog = self.iso.make_catalog()
        self.ok("codex marketplace add (git)",
                ["codex", "plugin", "marketplace", "add", "--json", "--ref", "main",
                 self.git_url_for(catalog)])
        self.ok("codex plugin add", ["codex", "plugin", "add", "--json",
                                     "alpha@%s" % h.MARKETPLACE])
        listed = self.ok("codex plugin list",
                         ["codex", "plugin", "list", "--marketplace", h.MARKETPLACE,
                          "--json"]).json()
        self.assertEqual([p["pluginId"] for p in listed["installed"]],
                         ["alpha@%s" % h.MARKETPLACE])
        self.ok("codex marketplace upgrade",
                ["codex", "plugin", "marketplace", "upgrade", "--json", h.MARKETPLACE])

        checkout = self.iso.make_catalog(name="example-local-skills")
        self.ok("codex marketplace add (local path)",
                ["codex", "plugin", "marketplace", "add", "--json", checkout])
        self.ok("codex plugin add (local path)",
                ["codex", "plugin", "add", "--json", "alpha@example-local-skills"])

        status = self.run_cli("codex login status, after", ["codex", "login", "status"])
        self.assertNotEqual(status.returncode, 0)


class AgyWithoutCredentials(h.ContractCase):
    TEST_ID = "C0"
    NEEDS = ("agy", "git")

    def test_plugin_verbs_work_signed_out_and_offline(self):
        # agy has no auth-status command; a fresh HOME holds none of its credential files.
        self.prove_isolated("agy")
        h.record(self.iso, self.TEST_ID, "agy credential files in temp home",
                 present=sorted(n for n in ("oauth_creds.json", "google_accounts.json")
                                if os.path.exists(os.path.join(self.iso.home, ".gemini", n))))
        catalog = self.iso.make_catalog()
        self.ok("agy plugin install (directory)",
                ["agy", "plugin", "install", os.path.join(catalog, "plugins", "alpha")])
        listed = self.ok("agy plugin list", ["agy", "plugin", "list", "--json"]).json()
        self.assertEqual([p["name"] for p in listed], ["alpha"])


if __name__ == "__main__":
    unittest.main()
