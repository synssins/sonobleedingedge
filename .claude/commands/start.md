# /project:start - Start a Development Session

Start here every time you begin working on Sonorium.

## What This Does

1. **Loads the project rules** from CLAUDE.md
2. **Checks what you were working on** from Summary.md  
3. **Shows pending tasks** from TODO.md
4. **Verifies git is set up correctly**
5. **Activates self-directing orchestrator**

## What You'll See

```
## 🚀 Sonorium Session Started

### Current Branch
You're on: [branch name]

### What's In Progress  
[From Summary.md - what was being worked on]

### Pending Tasks
[Top items from TODO.md]

### Git Remotes Verified
✅ origin → Your Gitea (192.168.1.222) - where work gets saved
✅ github → Public backup - off limits

### Self-Directing Mode Active
When you ask a question or request a task, I will:
1. Figure out what needs to be investigated
2. Automatically spawn parallel agents to cover all angles
3. Synthesize findings into a clear answer

Just ask naturally - I'll handle the rest.

### Ready!
What would you like to work on?
```

## How It Works Now

**You just ask your question:**
> "Why would miniaudio need to be installed when the code is supposed to be portable?"

**The orchestrator automatically:**
1. Determines this needs research + compatibility + alternatives perspectives
2. Spawns parallel tasks to investigate each angle
3. Synthesizes findings into a direct answer

**You don't need to:**
- Specify which agents to use
- Tell it how many parallel tasks
- Define what each task should do

The orchestrator figures all that out based on your question.

## Files That Get Read

| File | Why |
|------|-----|
| CLAUDE.md | Project rules and git setup |
| Summary.md | Current work state |
| TODO.md | Task list |
| Completed.md | Recent history |
