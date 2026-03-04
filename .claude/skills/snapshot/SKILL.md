---
name: snapshot
description: Generate a plain-text project snapshot and save it to .claude/snapshot.txt. Use when the user asks for a project summary, snapshot, or quick overview of the current state.
---

Collect the following using Bash (no extra dependencies needed):
- Current date: `date`
- Current branch: `git branch --show-current`
- Last 5 commits: `git log --oneline -5`
- Uncommitted changes: `git status --short` (write "none" if empty)

Then write a plain-text file to `.claude/snapshot.txt` in the project root with this layout:

```
Snapshot: <date>
Branch:   <branch>

Recent commits:
  - <commit>
  - <commit>
  ...

Uncommitted changes:
  <files or "none">
```

Use the Write tool to save the file.
