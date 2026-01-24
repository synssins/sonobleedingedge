# /project:review - Review Before Saving

Run this before committing code to make sure everything is correct.

## What Gets Checked

### 1. Destination Check
Where will the code be saved?
- ✅ Your Gitea server (192.168.1.222) = Correct
- ❌ GitHub = Wrong, needs to be fixed

### 2. AI Attribution Check  
Is there any mention of Claude or AI in the code?
- ✅ None found = Good
- ❌ Found = Must be removed

### 3. Platform Check
Will the core code work everywhere?
- ✅ Works on Windows, Mac, Linux, Docker = Good
- ❌ Windows-only code found = Must be fixed

### 4. HA Addon Check
Was the stable addon accidentally modified?
- ✅ Untouched = Good
- ⚠️ Modified = Was this intentional?

## What You'll See

```
## 📋 Review Results

### Destination
✅ Code will be saved to: Your Gitea (192.168.1.222)

### Checks
✅ No AI attribution found
✅ Code works on all platforms  
✅ HA addon not modified

### Verdict: APPROVED ✅

Save your changes with:

  git add -A
  git commit -m "feat: [describe what you changed]"
  git push origin dev

This sends your code to YOUR Gitea server (the correct place).
```

## If There Are Problems

I'll list exactly what needs to be fixed before the code can be saved.
