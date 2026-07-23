# ADR 0001: M1 sync hub and portable workspaces

- Status: accepted
- Date: 2026-07-23

## Context

M1 already synchronized its project tree with an Arch workstation through a
healthy Mutagen session named `projects`. Max needed the same project state
without turning the three machines into a peer-to-peer mesh.

The machines have different local homes:

- M1 uses `/Users/luischavesrodriguez`
- Max uses `/Users/luis`
- Arch uses `/home/luischavesrodriguez`

Project and worktree paths still need to resolve identically when execution
moves between machines.

## Decision

M1 is the only sync hub. It owns two independent, two-way-safe sessions:

```text
M1 /Users/luischavesrodriguez/Projects
├── projects     ↔ arch-lenovo:/Users/luischavesrodriguez/Projects
└── projects-max ↔ luis@max:/Users/luischavesrodriguez/Projects
```

There is no Max-to-Arch session.

Max keeps `/Users/luis` as its local home. Its portable workspace is the real
directory `/Users/luischavesrodriguez/Projects`, owned by `luis:staff`.
`/Users/luis/Projects` is a compatibility symlink to that directory.

Codex's worktree root on both Macs is:

`/Users/luischavesrodriguez/Projects/.worktrees/codex`

No GHQ migration is part of this decision. Existing repositories and worktrees
stay where they are.

## Live `projects-max` record

This is the configuration reported by `mutagen sync list --long` immediately
after creation, first scan, resume, and flush:

```text
Name: projects-max
Identifier: sync_QUkbGypl1BoOvnhvQhS1wJ2PRqtNK9RsE1lvWZDbjgp
Configuration:
    Synchronization mode: Two Way Safe
    Hashing algorithm: Default (SHA-1)
    Maximum allowed entry count: Default (2⁶⁴−1)
    Maximum staging file size: Default (18 EB)
    Symbolic link mode: Portable
    Ignore syntax: Default (Mutagen)
    Ignores:
        node_modules
        .venv
        venv
        __pycache__
        *.pyc
        .pixi
        __pypackages__
        .cache
        .pytest_cache
        .mypy_cache
        .ruff_cache
        .tox
        .coverage
        htmlcov
        *.egg-info
        .eggs
        target
        dist
        build
        .next
        .nuxt
        .turbo
        .parcel-cache
        .wrangler
        .sass-cache
        .DS_Store
        *.log
        *.swp
        *.swo
        .env
        .env.local
        courses/AWS-SAA-SAAC003-cantrill
        homelab/pihole/etc-pihole
        homelab/pihole/etc-dnsmasq.d
        homelab/jellyfin/config
        homelab/jellyfin/cache
        *.mp3
        *.mp4
        homelab/yamtrack/redis/dump.rdb
        *.db-wal
        *.db-shm
        *.db-journal
        hobby/thenewcomputer
        homelab/ccusage/db
        homelab/yamtrack/db
        *.tsbuildinfo
        history.git
    Ignore VCS mode: Ignore
    Permissions mode: Portable
Alpha:
    URL: /Users/luischavesrodriguez/Projects
    Configuration:
        Watch mode: Default (Portable)
        Watch polling interval: Default (10 seconds)
        Probe mode: Default (Probe)
        Scan mode: Default (Accelerated)
        Stage mode: Default (Mutagen Data Directory)
        File mode: Default (0600)
        Directory mode: Default (0700)
        Default file/directory owner: Default
        Default file/directory group: Default
    Connected: Yes
    Synchronizable contents:
        13379 directories
        91126 files (5.3 GB)
        28 symbolic links
Beta:
    URL: luis@max:/Users/luischavesrodriguez/Projects
    Configuration:
        Watch mode: Default (Portable)
        Watch polling interval: Default (10 seconds)
        Probe mode: Default (Probe)
        Scan mode: Default (Accelerated)
        Stage mode: Default (Mutagen Data Directory)
        File mode: Default (0600)
        Directory mode: Default (0700)
        Default file/directory owner: Default
        Default file/directory group: Default
        Compression: Default (DEFLATE)
    Connected: Yes
    Synchronizable contents:
        13379 directories
        91126 files (5.3 GB)
        28 symbolic links
Status: Watching for changes
```

No labels are set on either live session.

## Seed and activation procedure

The live rollout used this sequence:

1. Verify Max's canonical directory, ownership, SSH access, and free space.
2. Pause `projects` so the first copy starts from a stable project snapshot.
3. Run a non-destructive `rsync -a` from M1 to Max with the live Mutagen ignore
   list. Do not use `--delete`.
4. Include existing Git metadata in the seed. Exclude the volatile
   `.git/refs/codex/turn-diffs` namespace if Codex is active.
5. Run the same rsync again and require exit 0 with zero files transferred.
6. Create `projects-max` pre-paused with the configuration above.
7. Resume and flush `projects` and `projects-max`.
8. Require both sessions to report `Watching for changes`.
9. Test M1-to-Max, M1-to-Arch, and Max-to-M1-to-Arch propagation with temporary
   sentinels, then remove them everywhere.

## Consequences

- A Max problem cannot directly mutate Arch; changes always pass through M1.
- Machine-local homes and credentials stay local.
- Canonical repository and existing worktree paths resolve on every execution
  peer.
- The two sessions can be paused, flushed, repaired, or terminated
  independently.
- `Ignore VCS` protects live Git internals from bidirectional file sync.
- Because VCS directories are ignored after the seed, later branch refs,
  indexes, and worktree registrations do not propagate automatically. Use Git
  remotes for commits and seed new portable worktree metadata deliberately.
- Two-way sync still carries deletion and conflict risk. Pause the affected
  session before path surgery or bulk churn, then inspect, resume, and flush.
