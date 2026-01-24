# Sonorium Linux Native App

**Status:** Placeholder - Not Yet Implemented

## Planned Structure

```
linux/
├── main.py                 # Entry point
├── wrapper/                # Linux-specific wrapper code
│   └── app_factory.py      # Linux app configuration
├── sonorium/               # Core code (synced from shared/)
├── plugins/                # User plugins
└── themes/                 # User themes
```

## Implementation Notes

- Native Linux application (systemd service or desktop app)
- Core Python code identical to all platforms
- Plugins directory: ~/.sonorium/plugins/ or configurable
- Themes directory: ~/.sonorium/themes/ or configurable
- Will share identical core with all other platforms
