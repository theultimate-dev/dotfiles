# agent-sync test fixtures

Read-only inputs; tests copy them into a temporary directory before changing anything.

- `catalog-flat/`: the `example-skills` catalog, one folder per plugin with `skills/<skill>/`
  inside it. `reviewing` declares its skills in `plugin.json` (and leaves `draft-notes` out).
- `catalog-shared/`: the `example-vendor-plugins` catalog, one shared root with
  `skills/<plugin>/<skill>/`, skills declared in the catalog entries.
- `loose/my-local-skill/`: a `[[skill]] path` source.
- `standalone-skills/`: a `[[skill]] git` source.

Sources with a symlink are built by the tests at run time rather than tracked.
