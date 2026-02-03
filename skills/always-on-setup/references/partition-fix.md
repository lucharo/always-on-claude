# Moving Data Between Partitions

When data lands on the wrong partition (e.g., root instead of /home), follow this procedure to move it safely.

## Pre-requisites

- Root access (via `su -` or working `sudo`)
- Mutagen sync paused (if running)
- Backup exists (e.g., data also on client machine)

## Procedure

### Step 1: Pause Any Active Syncs

From the client machine:
```bash
mutagen sync pause projects
mutagen sync pause claude-config
mutagen sync list  # Verify paused
```

### Step 2: Verify Source and Destination

On the server:
```bash
# Check current location and size
du -sh /Users/luischavesrodriguez
df -h /  # Check root partition usage
df -h /home  # Check home partition free space
```

### Step 3: Copy Data (Safer Than Move)

```bash
# Copy preserving all attributes
cp -a /Users/luischavesrodriguez /home/luischavesrodriguez_macpath
```

### Step 4: Verify the Copy

Compare file counts and sizes:
```bash
echo "=== SOURCE ===" && \
find /Users/luischavesrodriguez -type f | wc -l && \
du -sh /Users/luischavesrodriguez && \
echo "=== DESTINATION ===" && \
find /home/luischavesrodriguez_macpath -type f | wc -l && \
du -sh /home/luischavesrodriguez_macpath
```

If rsync is available, verify checksums:
```bash
rsync -avcn --delete /Users/luischavesrodriguez/ /home/luischavesrodriguez_macpath/
```

Read an actual file to confirm copy is real:
```bash
cat /home/luischavesrodriguez_macpath/Projects/some-project/README.md | head -10
```

### Step 5: Delete Original and Create Symlink

Only after verification:
```bash
rm -rf /Users/luischavesrodriguez
ln -s /home/luischavesrodriguez_macpath /Users/luischavesrodriguez
```

### Step 6: Verify Symlink Works

```bash
ls -la /Users/
ls /Users/luischavesrodriguez/Projects | head -5
df -h /  # Should show freed space
```

### Step 7: Resume Syncs

From the client machine:
```bash
mutagen sync resume projects
mutagen sync resume claude-config
mutagen sync list  # Verify working
```

## Troubleshooting

### Copy Failed Partway

If `cp` failed mid-copy:
1. Check destination for partial data
2. Delete partial copy: `rm -rf /home/luischavesrodriguez_macpath`
3. Check disk space: `df -h /home`
4. Retry copy

### Symlink Not Working

If Mutagen can't follow symlink:
```bash
# Check symlink is correct
ls -la /Users/luischavesrodriguez

# Should show:
# luischavesrodriguez -> /home/luischavesrodriguez_macpath
```

### Data Corruption Concerns

If worried about data integrity:
1. Keep original until sync is verified working
2. Create tarball backup first:
   ```bash
   tar -czf /home/backup.tar.gz /Users/luischavesrodriguez
   ```
