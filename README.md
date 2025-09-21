# SnyIDE

Trash Code Editor

I hated SnakeIDE thats why i made a new one.

### How themes work

The app replaces placeholders like `$EditorBG$` in `constant_theme.css` with values from the active theme JSON. You can extend styling by adding new keys to the JSON and referencing them in the CSS.

### Customize

- Edit `default.json` or `light.json` to tweak colors or the corner `Radius`.
- Add more tokens and reference them in `constant_theme.css` as `$YourToken$`.
- Extend syntax highlighting under the `colors` section (e.g., NUMBER, FUNCTION, CLASS, DECORATOR, etc.).

### Palette (default / dark)
- Backgrounds: EditorBG `#282a36`, MainBG `#2d303d`, Surface `#2b2d3a`
- Foreground: `#f8f8f2`, Muted: `#6272a4`
- Accent: `#bd93f9`, AccentAlt: `#8be9fd`, Accent2: `#50fa7b`
- Selection: BG `#44475a`, FG `#f8f8f2`
- Borders: `#3a3d4d`

### Notes
- Qt style sheets don’t support dynamic color math; hover/active colors are provided via tokens.
- Caret color for QPlainTextEdit is controlled by Qt internals (not via QSS); selection colors are themed.

### ICON CREDITS
- Thanks for jetbrains for the open source icons!
