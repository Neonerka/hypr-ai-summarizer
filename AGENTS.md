# AGENTS.md

## Project: hypr-ai-summarizer

AI assistant for Arch Linux / Hyprland / Wayland. GTK3 floating window, reading clipboard, DuckDuckGo search, Ollama streaming.

## File layout

- `~/scripts/ai-assist.py` — GTK window, 3 modes, Ollama streaming, doc loading
- `~/scripts/toggle-ai-assist.sh` — hotkey launcher, adaptive size
- `~/scripts/install.sh` — dependency installer
- `~/scripts/ollama-boot.sh` — systemd service for Ollama preload

## Key architecture

- **MODEL** in `ai-assist.py` is a personal preference; never hardcode assumptions about model capability
- Script uses `wl-paste` (CLIPBOARD first, PRIMARY fallback) for clipboard
- Three modes toggled by `Gtk.RadioButton`: Буфер (auto-fill clipboard), Поиск (free text), Доки (query + docs sources)
- Docs entry (`Gtk.TextView`) visible only in Доки mode — sources: URL, `man:`, `arch:`, `gh:`, file paths
- `/doc <source>` command in follow-up entry (`>>>`)
- Follow-up preserves context; new top-level query resets search/docs
- Ollama streaming: `requests.post` with `stream=True`, each chunk via `GLib.idle_add`
- All UI updates from background threads go through `append_text` → `GLib.idle_add`

## Window rules (Hyprland)

```conf
windowrule = float true, match:class ai-assist
windowrule = dim_around true, match:class ai-assist
windowrule = animation slide, match:class ai-assist
bind = Super+Shift, A, exec, ~/scripts/toggle-ai-assist.sh
```

## Testing restrictions

- Requires Wayland + Hyprland (cannot test fully in SSH/headless)
- Python syntax check: `python3 -c "import py_compile; py_compile.compile('ai-assist.py', doraise=True)"`
- GTK import requires `$DISPLAY`; for headless linting use `py_compile` only

## Dependencies

- Arch packages: `wl-clipboard`, `python-requests`
- pip: `duckduckgo_search`
- Ollama (local, http://localhost:11434)

## Common traps

- `Gtk.RadioButton` fires `toggled` twice (off → on). Guard with `_in_init` flag
- docs_frame explicitly hidden after `show_all()` in non-DOCS modes; mode switch calls `show_all()`/`hide()`
- `wl-paste` without args = CLIPBOARD; `wl-paste -p` = PRIMARY; both exit immediately with code 1 if empty
- Window class detected by `hyprctl clients -j | jq '.[] | select(.class == "ai-assist")'`
- CSS uses only grayscale (`#000000`, `#555555`, `#ffffff`) — no accent colors
