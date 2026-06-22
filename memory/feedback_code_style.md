---
name: feedback-code-style
description: User formats Python with Black; always write Black-compatible code
metadata:
  type: feedback
---

Format all Python code to be compatible with Black (https://black.readthedocs.io/).

**Why:** User runs Black on all Python files in this project and expects code to not need reformatting after being written.

**How to apply:** Follow Black's rules — double quotes, trailing commas in multi-line structures, 88-char line length, consistent spacing. When in doubt, imagine Black has already run on the output.
