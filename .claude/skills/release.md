---
name: release
description: Create a GitHub release with version bump and release notes
user_invocable: true
---

Create a new GitHub release for compliance-advisor.

1. Check current version: look at the latest git tag (`git tag --sort=-v:refname | head -5`).
2. Ask the user what type of bump: patch (default), minor, or major.
3. Determine the new version tag (e.g., v0.32.0 -> v0.32.1 for patch).
4. Generate release notes from commits since the last tag:
   ```bash
   git log <last-tag>..HEAD --oneline
   ```
5. Format release notes as a markdown bullet list.
6. Create the release:
   ```bash
   gh release create <new-tag> --title "<new-tag>" --notes "<markdown bullet list>"
   ```
   - No `--draft`, no `--generate-notes`. Manual `--notes` with markdown bullets.
7. Update version references in `.claude/CLAUDE.md` and `~/CLAUDE.md` if they reference the version.
8. Report the release URL.
