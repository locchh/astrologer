---
name: todo-scan
description: Scan the codebase for TODO and FIXME comments and save a plain-text report. Use when the user asks to find TODOs, scan for FIXMEs, or get a list of pending tasks in the code.
---

Run this bash command to find all TODO/FIXME comments:

```bash
grep -rn --include="*.py" --include="*.ts" --include="*.js" --include="*.md" -E "TODO|FIXME" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules
```

Then write a plain-text report to `.claude/todo-scan.txt` with this layout:

```
TODO/FIXME Scan — <date>

Found <N> items:

<file>:<line> — <comment text>
<file>:<line> — <comment text>
...

(none found — clean codebase!)  ← use this if empty
```

Use the Write tool to save the file. Tell the user it was saved to `.claude/todo-scan.txt`.
