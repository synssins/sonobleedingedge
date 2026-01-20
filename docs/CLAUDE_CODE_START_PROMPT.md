# COMPREHENSIVE REFACTOR INITIATION PROMPT

## CRITICAL: Read These Files FIRST (In Exact Order)

Before doing ANY work, read and internalize these documents:

1. `CLAUDE.md` - Project rules and sync architecture
2. `FOUNDATIONAL_CHANGES.md` - Target architecture and true plugin requirements
3. `CLAUDE_GIT_SAFETY.md` - Git safety rules
4. `shared/README.md` - Sync system documentation
5. `docs/REFACTOR_INSTRUCTIONS.md` - Cautious incremental refactor process

After reading ALL files, confirm understanding by answering the questions below.

---

## CONTEXT: Sync Architecture Already Implemented

Claude Code has already set up:
- `shared/` folder as source of truth
- `scripts/sync_shared.py` for syncing to both targets
- `scripts/setup_hooks.py` for pre-commit hook
- `.github/workflows/verify-sync.yml` for CI verification
- Initial plugin files in `shared/plugins/`

The workflow is:
1. Edit code in `shared/`
2. Run `python scripts/sync_shared.py`
3. Commit and push to sonobleedingedge

---

## QUESTIONS YOU MUST ANSWER BEFORE PROCEEDING

### Question 1: Sync Architecture Understanding

Explain why we can't use imports/wrappers for sharing code with the HA addon.
Where is the source of truth for shared code?
What must you run before every commit?

### Question 2: What Goes Where

For each item, state WHERE it should be edited:

- Plugin base class -> ?
- Sonos speaker plugin -> ?
- Windows tray icon -> ?
- HA MQTT entity manager -> ?
- Core audio mixing engine -> ?

### Question 3: Platform-Agnostic Requirements

What is FORBIDDEN in `shared/` code? List at least 4 things.
How should shared code access platform-specific values like data directories?

### Question 4: True Plugin Architecture

What is the "Acid Test" for true plugins?
Currently, if you delete `shared/plugins/builtin/sonos/`, will Sonos support be removed? Why or why not?
What files contain the 384 protocol references that need extraction?

### Question 5: Verification Commands

What commands verify that shared/ code is platform-agnostic?
What should these commands return after the refactor is complete?

---

## IMMEDIATE TASKS

Once you have answered ALL questions and I have confirmed:

1. **Verify workflow is fixed**: Check that `.github/workflows/verify-sync.yml` has no encoding issues

2. **Update sync mappings**: Ensure `scripts/sync_shared.py` includes all shared directories

3. **Run sync and verify**: 
   ```bash
   python scripts/sync_shared.py --verbose
   git diff  # Check what changed
   ```

4. **Create refactor tracking**:
   - Create `_archive/` directory
   - Create `_refactor_log/REFACTOR_PROGRESS.md`

5. **Analyze current state**:
   - Count protocol references in network_speakers.py and streaming.py
   - List files that need extraction
   - Present extraction plan

6. **WAIT for approval** before any code changes

---

## COMMIT WORKFLOW REMINDER

```bash
# 1. Make changes in shared/ (for shared code)
# 2. Sync to targets
python scripts/sync_shared.py

# 3. Commit
git add -A
git commit -m "descriptive message"

# 4. Push (ONLY to sonobleedingedge)
git push sonobleedingedge main
```

---

## ABSOLUTE RULES

- **NEVER** edit synced files directly (edit in `shared/` only)
- **NEVER** proceed without answering the questions first
- **NEVER** make code changes without explicit approval
- **NEVER** skip the sync step before commits
- **NEVER** push to any repo except sonobleedingedge
- **ALWAYS** commit frequently with descriptive messages
- **ALWAYS** test after each extraction
- **ALWAYS** pause at checkpoints and wait for confirmation
