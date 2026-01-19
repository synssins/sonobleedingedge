# Claude Code Prompt: Sonorium Plugin System Backbone - Stage 1

## Project Context

You are implementing a plugin system for Sonorium, a multi-zone ambient soundscape mixer. This follows the architectural principles defined in the project's foundational documentation.

---

## CRITICAL: Read These Files First (In Order)

Before writing ANY code, you MUST read and understand these documents:

### Step 1: Read the Foundational Architecture
```bash
cat "G:\Projects\sonobleedingedge\FOUNDATIONAL_CHANGES.md"
```

### Step 2: Read the Plugin Architecture Spec
```bash
cat "G:\Projects\sonobleedingedge\docs\sonorium-plugin-architecture.md"
```

### Step 3: Understand Current Codebase Structure
```bash
Get-ChildItem "G:\Projects\sonobleedingedge\app" -Recurse -Depth 2 | Select-Object FullName
```

---

## Stage 1 Objectives

Implement the **plugins.py module** as defined in FOUNDATIONAL_CHANGES.md. This is an OPTIONAL module that provides the plugin system backbone.

### Deliverables for Stage 1

1. **G:\Projects\sonobleedingedge\app\plugins.py** - The main plugin system module (Category A)
2. Plugin base classes: SonoriumPlugin, PluginContext, PluginState
3. EventBus class for plugin communication
4. PluginManager class for discovery/loading/lifecycle
5. Copy to: **G:\Projects\sonobleedingedge\sonorium_addon\sonorium\plugins.py** (must be identical)

---

## Module Interface (per FOUNDATIONAL_CHANGES.md)

```python
__feature_name__ = "Plugin System"
__required__ = False
__depends_on__ = []

async def init(app_context) -> bool: ...
async def shutdown() -> None: ...
def health_check() -> dict: ...
def is_available() -> bool: ...
```

---

## What NOT To Do in Stage 1

- Do NOT implement any specific plugins yet
- Do NOT add UI components yet
- Do NOT add API routes yet (Stage 2)
- Do NOT implement HA entity creation yet (Stage 3)

---

## Completion Checklist

- [ ] plugins.py created at G:\Projects\sonobleedingedge\app\plugins.py
- [ ] Follows FOUNDATIONAL_CHANGES.md module pattern
- [ ] SonoriumPlugin base class implemented
- [ ] PluginContext dataclass implemented
- [ ] EventBus with subscribe/emit implemented
- [ ] PluginManager with discover/load/enable implemented
- [ ] Copied to G:\Projects\sonobleedingedge\sonorium_addon\sonorium\plugins.py
