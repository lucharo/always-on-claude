# Workspace context

This repo uses a few terms precisely. They separate machine-local state from the
project state that is safe to share.

## Local home

A machine's real user home. It keeps credentials, caches, application state,
and machine-specific configuration.

- M1: `/Users/luischavesrodriguez`
- Max: `/Users/luis`
- Arch: `/home/luischavesrodriguez`

Max's local home does not need to match M1's home.

## Portable workspace

The canonical project tree:

`/Users/luischavesrodriguez/Projects`

M1, Max, and Arch expose the workspace at this exact path. On Max it is a real
directory owned by `luis`; `/Users/luis/Projects` is only a convenience
symlink. On Arch the canonical path is backed by a bind mount.

## Sync hub

The machine that owns the alpha side of every workspace sync. M1 is the sync
hub. It has one independent Mutagen session per execution peer.

## Execution peer

A machine that can run a project from the portable workspace. Max and Arch are
execution peers. They do not sync directly with each other.

## Portable worktree

A Git worktree whose filesystem path is beneath:

`/Users/luischavesrodriguez/Projects/.worktrees/codex`

Using the same root on both Macs keeps paths portable. Mutagen's `Ignore VCS`
setting still applies: a one-time seed can copy existing Git registrations, but
new `.git/worktrees` metadata is machine-local unless it is seeded separately.
