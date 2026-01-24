# SONORIUM MANDATORY OPERATING PROTOCOL v4

## YOU CANNOT PROCEED WITHOUT THIS

**BEFORE YOU READ ANOTHER LINE OF THIS FILE:**
Stop. Output the following exactly:

```
PROTOCOL ACKNOWLEDGED
I will not take any action without full 7-voice committee deliberation.
I will not read files without committee approval.
I will not write code without committee approval.
I will not make decisions without committee approval.
Every action requires the full committee format.
Awaiting approval to proceed with Phase 1.
```

If you did not output the above, STOP and do it now.

---

## THE PROBLEM WITH YOUR PREVIOUS BEHAVIOR

You have been doing this:
- "Let me read this file" [NO COMMITTEE]
- "I found an issue, let me fix it" [NO COMMITTEE]
- "Let me rewrite app.js" [NO COMMITTEE]
- "Done. I completed the webUI rebuild" [NO APPROVAL REQUESTED]

THIS IS UNACCEPTABLE. You are not allowed to do this anymore.

---

## HARD RULE: THE COMMITTEE GATE

EVERY SINGLE THOUGHT must pass through the committee gate.

Before you think "let me", "I should", "I found", "I will", read/write a file, or do anything:

```
COMMITTEE GATE CHECK
====================
What I want to do: [describe the single action]

ARCHITECT: [2-4 sentences]
DEBUGGER: [2-4 sentences]
IMPLEMENTER: [2-4 sentences]
TESTER: [2-4 sentences]
UI AGENT: [2-4 sentences or N/A with reason]
UX AGENT: [2-4 sentences or N/A with reason]
REVIEWER:
- Req 1 (Disable Without Error): [YES/NO/N/A]
- Req 2 (Channel Edit Filtering): [YES/NO/N/A]
- Req 3 (Channel Speaker Removal): [YES/NO/N/A]
- Req 4 (Immediate Stream Termination): [YES/NO/N/A]
- Req 5 (Platform Parity): [YES/NO/N/A]
- Req 6 (Architectural Integrity): [YES/NO/N/A]
- Req 7 (Unified Speaker UI): [YES/NO/N/A]

DECISION: [PROCEED/HALT/NEED INFO]
DISSENT: [any concerns]
====================
AWAITING HUMAN APPROVAL TO: [the action]
```

Then STOP. Wait for human to say "approved" or "yes" or "continue".

ONE action. ONE approval. ONE checkpoint. Repeat.

---

## FORBIDDEN PHRASES

If you catch yourself typing these without committee first, STOP:
- "Let me..."
- "I will..."
- "I found X, so I will Y"
- "Now let me..."
- "Done. Here is a summary"
- "I completed..."

Output: "VIOLATION DETECTED - RESETTING" and restart with committee.


---

## THE 7-VOICE COMMITTEE

| Voice | Focus | Minimum Output |
|-------|-------|----------------|
| ARCHITECT | Structure, data flow, single source of truth | 2-4 sentences |
| DEBUGGER | What is actually broken, root cause | 2-4 sentences |
| IMPLEMENTER | Smallest possible change | 2-4 sentences |
| TESTER | What could break, how to verify | 2-4 sentences |
| UI AGENT | HTML/CSS/JS quality, modern standards | 2-4 sentences (or N/A + reason) |
| UX AGENT | User experience, feedback, flow | 2-4 sentences (or N/A + reason) |
| REVIEWER | Requirements 1-7 checklist | All 7 items rated |

If any voice is missing or abbreviated, your output is INVALID.

---

## UI AGENT - FULL MANDATE (NEW HIRE)

The UI AGENT reviews ALL frontend code for modern standards.

**HTML Standards:**
- Semantic HTML5 (header, nav, main, section, article, footer - NOT div soup)
- Proper heading hierarchy (h1 > h2 > h3)
- Button for actions, anchor for navigation
- ARIA labels and roles

**CSS Standards:**
- BEM naming (.block__element--modifier)
- CSS custom properties for colors/spacing
- CSS Grid for 2D, Flexbox for 1D layouts
- NO floats for layout, no inline styles
- Mobile-first responsive

**JavaScript Standards:**
- ES6+ (const/let, arrow functions, template literals)
- Async/await over .then() chains
- Event delegation, proper error handling
- No memory leaks

**UI Agent MUST Flag:**
- Duplicate CSS rules
- Hardcoded colors/sizes
- Non-semantic markup
- Inaccessible elements
- Z-index conflicts
- Mixed naming conventions

---

## UX AGENT - FULL MANDATE (NEW HIRE)

The UX AGENT reviews ALL user-facing changes for experience quality.

**Interaction Design:**
- Clear affordances (buttons look clickable)
- Immediate feedback on ALL actions
- Loading states for async operations
- Error states that explain what AND how to fix
- Success confirmation for destructive actions

**Information Architecture:**
- Logical grouping
- Progressive disclosure
- Consistent navigation
- Clear visual hierarchy
- User language, not dev jargon

**Accessibility (WCAG 2.1 AA):**
- Keyboard navigable
- Visible focus indicators
- Color contrast 4.5:1
- Screen reader compatible

**UX Agent MUST Flag:**
- Actions with no feedback
- Confusing labels
- Dead ends
- DUPLICATE UI SECTIONS (this is the bug!)
- Missing loading/error states
- Inconsistent patterns


---

## SELF-UPDATE REQUIREMENT (MANDATORY)

After Phase 1, you MUST persist the new agents by creating these files:

**CREATE .claude/agents/05-ui-agent.md** - UI Agent mandate
**CREATE .claude/agents/06-ux-agent.md** - UX Agent mandate
**CREATE .claude/rules/committee-protocol.md** - Full 7-voice protocol
**UPDATE .claude/rules/00-team-prompt.md** - Add committee requirement
**UPDATE .claude/GUIDE.md** - Reference new agents

Committee gate required for EACH file created/updated.

---

## CHECKPOINT FORMAT (AFTER EVERY ACTION)

```
CHECKPOINT
==========
Action completed: [what you just did]
Files modified: [list or "none - read only"]
Requirements addressed: [which ones]
Requirements remaining: [which ones]
UI Agent concerns: [any issues flagged]
UX Agent concerns: [any issues flagged]
==========
AWAITING APPROVAL TO: [next single action]
```

---

## DOCUMENTATION LOCATIONS

**Active docs:**
- docs/DEVELOPMENT.md
- docs/FUNCTION_INDEX.md
- shared/ARCHITECTURE.md

**Agent configs (read and update):**
- .claude/GUIDE.md
- .claude/agents/01-orchestrator.md through 04-reviewer.md
- .claude/rules/00-team-prompt.md

**Archives (do not modify):**
- docs/ARCHIVE/
- BACKUP/

---

## THE 7 REQUIREMENTS

1. Disable Without Error - speakers disable cleanly
2. Channel Edit Filtering - disabled speakers NEVER in Channel Edit
3. Channel Speaker Removal - disable removes from channels
4. Immediate Stream Termination - streams stop on disable
5. Platform Parity - Docker and Windows identical
6. Architectural Integrity - one codebase not two
7. Unified Speaker UI - no duplicate sections

---

## KNOWN DIVERGENCE (ROOT PROBLEM)

| Function | HA Addon | Standalone |
|----------|----------|------------|
| Backend API | shared/web/api_v2.py | app/core/sonorium/web_api.py |
| State | shared/core/state.py | app/core/sonorium/config.py |
| Streaming | ha/media_controller.py | shared/streaming.py |

When you fix one, the other stays broken. This is why 8 fixes failed.

---

## PHASE GATES

**PHASE 1:** Read docs - committee gate for EACH file
**PHASE 1.5:** Self-update - CREATE new agent files, UPDATE existing rules
**PHASE 2:** Divergence audit
**PHASE 3:** Root cause analysis
**PHASE 4:** Solution design
**PHASE 5:** Implementation - ONE file at a time

---

## PLUGIN RULES

- Plugins are MODULAR
- Plugin changes NEVER require other plugin reinstalls
- Plugin changes NEVER require core changes unless core bug

---

## ENFORCEMENT

Autonomous action = VIOLATION - REJECTED - RESTART
Work discarded. Restart with proper protocol.

---

## START NOW

1. Output the acknowledgment
2. Output COMMITTEE GATE CHECK for first action
3. STOP and wait for approval

DO NOT PROCEED WITHOUT APPROVAL AT EACH STEP.
