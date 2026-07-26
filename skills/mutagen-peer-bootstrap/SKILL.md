---
name: mutagen-peer-bootstrap
description: >
  Add an execution peer to an existing live Mutagen project-sync hub without
  changing the topology or losing active work. Use when adding a new Mac, Linux
  workstation, or server alongside existing peers, especially when the new peer
  needs a pre-seed, portable paths, Git metadata, and end-to-end propagation QA.
allowed-tools:
  - Bash
  - Read
  - Grep
  - Glob
  - AskUserQuestion
---

# Mutagen Peer Bootstrap

Add one peer by cloning the live hub's behaviour, not by redesigning the sync
topology or copying stale documentation.

## 1. Establish the invariants

Read the repository instructions and topology ADR. Identify:

- the hub, existing peer sessions, and proposed new peer;
- the canonical project path on every machine;
- live Claude/Codex working directories that must not move;
- the exact existing session whose configuration is authoritative.

Run `mutagen sync list --long <existing-session>` and record its mode, endpoints,
ignore syntax and patterns, VCS policy, symlink/permission modes, compression,
labels, and healthy status. Preserve the topology unless the user explicitly
authorises a change.

## 2. Preflight the new endpoint

Prove network reachability and SSH authentication separately. A reachable
Tailscale node is not proof that the intended username/key works.

Verify the canonical destination is absent or empty, has the intended owner and
permissions, and has enough free space. Resolve compatibility paths with a
symlink or mount only when the canonical absolute path remains real and portable.
Do not run a broad dotfiles apply merely to create the project directory.

## 3. Seed without deletion

Build the seed exclusions from the live Mutagen ignore list. Dry-run first, then
use a non-destructive archive copy such as `rsync -a`; never add `--delete`.

Include existing Git metadata when portable repository state is required, but
exclude proven volatile agent namespaces such as
`.git/refs/codex/turn-diffs` while Codex is active. `Ignore VCS` governs ongoing
Mutagen behaviour; it does not prevent a deliberate one-time seed.

For a large seed, keep healthy existing sessions running during the bulk pass
when safe. Then:

1. Record the exact resume command and pause only the affected session(s).
2. Run the final delta with the identical exclusions.
3. Repeat until the pass exits 0 with zero files transferred.

Treat rsync exit 23 as acceptable only when stderr identifies an exclusively
volatile, independently verified path. Fix or exclude that narrow cause and
still require a subsequent clean zero-transfer pass.

## 4. Create the new session paused

Create the peer session in the paused state using the live session's exact
configuration. Do not silently substitute defaults for explicit ignores,
portable symlinks/permissions, compression, labels, or VCS policy.

Inspect `mutagen sync list --long <new-session>` before activation and compare it
field-by-field with the authoritative session. Correct configuration drift while
the new session is still paused.

## 5. Activate and prove convergence

Resume and flush every session paused by this workflow. Require, for each:

- both endpoints connected;
- no conflicts or transition problems;
- matching directory, file, and symlink counts;
- `Watching for changes` (or the equivalent healthy state).

Use origin-tagged temporary sentinels to prove the intended routes:

1. hub to the new peer;
2. hub to every existing peer;
3. new peer to hub and onward to another peer when the topology requires it.

Remove every sentinel and flush again. Verify absence on all endpoints.

## 6. Audit repository portability

Compare representative repositories across machines:

- HEAD and current branch;
- dirty/untracked state;
- worktree registrations and canonical paths;
- one repository with linked worktrees if that is part of the execution model.

State the VCS limitation explicitly: when `Ignore VCS` is enabled, the seed can
preserve current Git metadata, but future refs, indexes, and worktree
registrations do not propagate through Mutagen. Commits still move through Git
remotes; seed later worktree metadata deliberately.

## 7. Report

Report the preserved topology, exact new session, seed result, final health,
sentinel routes, Git/worktree parity, and any manual UI action. Do not call the
overall setup done while a required manual action remains.
