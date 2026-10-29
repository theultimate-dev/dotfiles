# Colima: Docker without Docker Desktop

How Docker runs here: Colima's Linux VM, driven by Homebrew's `docker` CLI and its Compose and
Buildx plugins. Covers the flags that matter on Apple silicon, how to size the VM for several
Compose stacks running at once, and the traps that only show up once they do.

Verified against **Colima 0.10.3**, **Docker CLI 29.9.2**, **Compose 5.6.1** and
**Buildx 0.38.1** on macOS 27 with an Apple M5, running the five-container web stack described
under sizing. The commands themselves are in
[manual setup, step 8](manual-setup.md#8-run-containers-with-colima).

## What you get

`docker`, `docker compose` and `docker buildx` working against a Linux VM that runs only while you
want it to. There is no Docker Desktop app and no background service. When Colima starts, it makes
itself the current Docker context, so the CLI needs no `DOCKER_HOST` and no further setup.

## Four packages, and why four

| `Brewfile` entry | What it is |
|---|---|
| `colima` | The VM manager. It pulls in `lima`, which does the virtualisation. |
| `docker` | The CLI only, with no engine. `cask "docker"` is a different thing: Homebrew resolves it to Docker Desktop. |
| `docker-compose` | `docker compose`, a CLI plugin. |
| `docker-buildx` | `docker buildx`, the BuildKit builder plugin. Without it `docker build` falls back to the legacy builder, which Docker has deprecated. |

The two plugins are the part that needs care. Docker looks for plugins in `~/.docker/cli-plugins`
and in any directory listed under `cliPluginsExtraDirs` in `~/.docker/config.json`. Homebrew
installs them under `$(brew --prefix)/lib/docker/cli-plugins`, which is neither, so until that
directory is listed, `docker compose` fails with `unknown command`. Homebrew also links a
standalone `docker-compose` binary, which works without the plugin setup, but scripts that call
`docker compose` do not use it.

Colima's own FAQ suggests symlinking each plugin into `~/.docker/cli-plugins`. That is rejected
here, as every symlink into `$HOME` is (see
[ADR 0001](decisions/0001-deliver-configs-as-include-stubs-not-symlinks.md)). Listing the directory
is one key in a file Docker already owns, it survives plugin upgrades, and it is added by hand in
step 8 rather than by the installer. `config.json` is shared with Docker itself: Colima writes the
current context into it, and `docker login` may write credentials into it.

## The flags that matter on Apple silicon

Every Apple silicon Mac, M1 onwards, takes the same flags. What differs between machines is the
three numbers.

| Flag | What it does | Changeable later? |
|---|---|---|
| `--vm-type vz` | Runs the VM on Apple's Virtualization.framework (macOS 13+). Without the flag, Colima chooses between `qemu` and `vz` depending on what else is installed; naming it removes that guess. | No: fixed when the VM is created |
| `--mount-type virtiofs` | The shared-folder driver for `vz`, and its default. Your home directory is mounted writable, so bind mounts from any checkout under it work. | Restart |
| `--mount-inotify` | Forwards file-change events from macOS into the VM. Off by default; see the first trap below. | Restart |
| `--cpus` | The number of virtual CPUs. They are scheduled on the host's cores as needed, not reserved. (`--cpu` is the older spelling.) | Restart |
| `--memory` | Memory in GiB. Plan as if all of it is taken: Linux fills spare memory with page cache, and after one image build, 9.5 of 12 GiB were cache. | Restart |
| `--disk` | The ceiling for images, containers, volumes and build cache, in GiB. The disk file is sparse: 150 GiB nominal took 8 MiB on the Mac when new. | **Grow only**, never shrink |
| `--ssh-config=false` | Stops Colima adding its SSH host entry to `~/.ssh/config`, a file it does not own. `colima ssh` does not need that entry. | Restart |
| `--arch` | Defaults to the host's architecture, `aarch64`. Leave it. | No: fixed when the VM is created |
| `--vz-rosetta` | Runs amd64 containers through Rosetta instead of QEMU emulation. Needs Rosetta 2 installed on macOS first. | Restart |

Colima saves the flags of the last start (`--save-config`, on by default) into its own
`~/.colima/default/colima.yaml`, so a later `colima start` with no flags reuses them. To change the
resources, stop the VM and start it again with the new values. Only the disk, the VM type and the
architecture resist that.

**Rosetta is optional.** If every image you run publishes an arm64 build (`postgres`, `node`,
`caddy` and Keycloak all do), it buys nothing. An amd64-only image still runs without it, through
QEMU emulation, only more slowly. Turn it on when an amd64 image is slow enough to matter, after
installing Rosetta with Apple's `softwareupdate --install-rosetta`.

## Sizing the VM for several stacks at once

The workload this was sized for is the demanding case: one repository checked out in several git
worktrees, each running its own Compose stack. Each worktree is its own Compose project, named after
its directory, so it gets its own containers, its own volumes and its own built images. Pulled base
images are stored once and shared by every project that uses the same tag.

**Measure one stack, then multiply.** Bring a single stack up, let it settle, and read
`docker stats --no-stream`. Then:

- **Memory:** per-stack usage × the number of stacks you run at once, plus about 2 GiB for a
  concurrent build and the VM's own kernel, dockerd and BuildKit. Then cap it at whatever macOS
  needs for your editor, browsers, agent CLIs and any test browsers that run on the host. Memory
  is the setting to get roughly right and then adjust: changing it costs a restart, nothing more.
- **CPUs:** the host's core count minus two. Idle virtual CPUs cost nothing, and parallel
  dependency installs across stacks are exactly the burst that extra CPUs absorb.
- **Disk:** be generous. The ceiling can only grow, and hitting it mid-build fails with "no space
  left on device". Each stack's volumes, a few shared images and a build cache that grows
  10–20 GiB if never pruned add up faster than the image sizes suggest.

**The worked example**, on an M5 with 10 cores and 32 GiB: the stack is a web application of five
containers (PostgreSQL, Keycloak, a Node API with a file watcher, a Vite dev server and a Caddy
proxy), with three worktrees running at once plus a fourth stack for integration or end-to-end
tests. Measured on one stack:

| | Measured | Planned |
|---|---|---|
| Memory, one stack | 2.3 GiB while it boots after a build (the Vite server alone 1.3); 1.3 GiB once settled | 2.5 GiB per stack |
| Disk, one stack | 3.1 GB of volumes, almost all of it four `node_modules` volumes of about 750 MB each | 3–5 GB per stack |
| Disk, shared | 6.4 GB of images, and 2.8 GB of build cache after the first build | 10–20 GB of cache over time |

| | Arithmetic | Result |
|---|---|---|
| Memory | 4 stacks × 2.5 + 2 | **12 GiB**, which leaves macOS 20 |
| CPUs | 10 − 2 | **8** |
| Disk | 6.4 + 5 stacks × 3–5 + up to 20 of cache ≈ 50 GB | **150 GiB**, about 3× headroom |

The memory figures were taken with no traffic, and Keycloak far below the heap it is allowed
(trap 2). Load moves them up, so measure your own stack under the use you actually give it.

Running four or more dev stacks regularly is the point to move to 16 GiB. Going past 16 leaves
macOS less than half of a 32 GiB machine.

## Trap 1: file watchers in containers see nothing

`--mount-inotify` is off by default. Without it, an edit saved on the Mac changes the file inside
the VM but fires no inotify event there. Every watcher running in a container misses it: Vite's
hot reload, `node --watch`, nodemon, webpack and test watchers. The container keeps serving the
old code, and nothing errors. Restarting the container "fixes" it, which is what makes the cause
hard to see.

Turning the flag on forwards the events from macOS into the VM. In the example stack, with the
flag on, saving a change to the API's entry point restarted `node --watch` within seconds. With
the flag off, the same edit produced nothing in 30 seconds. A bare `touch`, which changes only the
timestamp, did not trigger a restart even with the flag on, so test with a real edit.

Colima marks the flag experimental. The alternative, and the only option if the flag misbehaves,
is to make each watcher poll, which costs CPU in every container that does it.

## Trap 2: a JVM in a container sizes itself from the whole VM

Keycloak's container image sets its heap relative to the memory it can see: up to 70% of it,
starting at 50%. Keycloak 25 starts with exactly those flags (`-XX:MaxRAMPercentage=70`,
`-XX:InitialRAMPercentage=50`). With no memory limit on the container, what it sees is the whole
VM, so on a 12 GiB VM each Keycloak may grow to about 8 GiB. It sat at about 0.5 GiB at rest in
the example stack, which is why the problem stays hidden until load arrives.
Three stacks mean three Keycloaks, each planning on most of the VM's memory. Keycloak's own
container documentation says to always set a memory limit.

That fix belongs to the project, not to this machine: a memory limit on the service in its
Compose file, or an explicit heap through `JAVA_OPTS_KC_HEAP`. Every other JVM service also sizes
its heap from the memory it can see (a quarter of it, by the JVM's own default), so without a
limit each one is planned against the whole VM.

## Trap 3: disk only grows, and anonymous volumes pile up

`docker compose down` removes a stack's containers and networks but not its anonymous volumes. A
service that declares a bare container path under `volumes:` (the common way to keep
`node_modules` out of a bind mount) leaves one behind on every `down`. Each holds a full
dependency tree, about 750 MB in the example stack, and the next `up` creates a fresh one rather
than reusing it.

`docker system df` shows where the space went. `docker volume prune` removes unused anonymous
volumes, and `docker builder prune` removes the build cache. Pruning frees space inside the VM,
but the ceiling set by `--disk` never comes back down, which is the other reason to choose it
generously and once.

## Trap 4: Colima takes over the Docker context

On every start, Colima makes `colima` the current Docker context and records it in
`~/.docker/config.json`. If Docker Desktop, OrbStack or a second Colima profile is also in use, the
most recently started one wins, and `docker context ls` shows which. Deleting a Colima profile
removes its context and leaves Docker on `default`, which points at `/var/run/docker.sock`, a
socket nothing on the Mac serves. Switch back with `docker context use colima`.

Tools that skip contexts and look for a socket directly need `DOCKER_HOST` pointed at Colima's
socket, `~/.colima/default/docker.sock`, as Colima's FAQ describes. Nothing here exports it,
because the Docker CLI itself does not need it.

## What is deliberately not here

- **A managed `colima.yaml`.** Colima rewrites that file itself on every start that passes flags,
  the same reason [ADR 0005](decisions/0005-install-agent-tooling-without-managing-its-config.md)
  leaves self-rewriting configs unmanaged. One documented command gives the same result without a
  new destination.
- **Starting at login.** `brew services start colima` would do it, and it is the route Colima
  recommends for Homebrew installs. It also keeps the VM's memory gone from the moment you log in.
  Here the VM is started when containers are needed and stopped when they are not.
- **Docker Desktop.** Neither the app nor its cask is installed. Colima and Docker Desktop can run
  side by side, separated by context (trap 4), if you need both.
