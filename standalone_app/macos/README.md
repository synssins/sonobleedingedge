# Sonorium macOS App

**Status:** Placeholder - Not Yet Implemented

## Planned Structure

```
macos/
├── main.py                 # Entry point
├── wrapper/                # macOS-specific wrapper code
│   └── app_factory.py      # macOS app configuration
├── sonorium/               # Core code (synced from shared/)
├── plugins/                # User plugins
└── themes/                 # User themes
```

## Implementation Notes

- Native macOS application (.app bundle)
- May use py2app or similar for packaging
- Core Python code identical to all platforms
- Plugins directory: ~/Library/Application Support/Sonorium/plugins/
- Themes directory: ~/Library/Application Support/Sonorium/themes/
- Will share identical core with all other platforms
