# Sonorium Android App

**Status:** Placeholder - Not Yet Implemented

## Planned Structure

```
android/
├── main.py                 # Entry point (if using Python/Kivy)
├── wrapper/                # Android-specific wrapper code
│   └── app_factory.py      # Android app configuration
├── sonorium/               # Core code (synced from shared/)
├── plugins/                # User plugins
└── themes/                 # User themes
```

## Implementation Notes

- May use Kivy, BeeWare, or native Kotlin wrapper
- Core Python code runs via embedded interpreter
- Plugins and themes accessible via app storage
- Will share identical core with all other platforms
