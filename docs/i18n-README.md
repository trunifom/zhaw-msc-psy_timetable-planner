# i18n Guide

This project uses a simple key-based localization system in `src/i18n.py`.

## Overview
- `TEXTS` stores all translations by language code (`de`, `en`, `fr`).
- `get_text(lang, key, **kwargs)` returns the localized text.
- Fallback order is:
  1. selected language
  2. German (`de`)
  3. the key itself

## Usage in `src/app.py`
- Use `t("namespace.key")` for normal UI text.
- Use `c("column_key")` for DataFrame and table column labels.

Examples:

```python
st.subheader(t("dashboard.subheader"))
df = pd.DataFrame([{c("metric"): "...", c("value"): 42}])
```

## Key Naming Rules
- Keep keys stable and lowercase.
- Use namespaces:
  - `app.*`, `sidebar.*`, `guided.*`, `dashboard.*`, `conflicts.*`, `raw.*`, `export.*`, `chart.*`
  - `col.*` for DataFrame column names
- Do not reuse one key for different meanings.
- Prefer short, explicit keys over ambiguous ones.

## Placeholders
- Use named placeholders for dynamic text:
  - `"{count}"`, `"{sheet_name}"`, `"{error}"`
- Keep the same placeholder names across all languages.

Example:

```python
"upload.success_sheet": "Loaded data from sheet '{sheet_name}'."
```

## Adding a New Language
1. Add a new language block in `TEXTS` (for example `"it"`).
2. Copy all keys from `de` and translate values.
3. Add the language option in `render_sidebar()` (`app.py`).
4. Verify app import and basic rendering.

## Consistency Checklist
- All new visible strings use `t(...)`.
- All new DataFrame column labels use `c(...)`.
- No hardcoded user-facing labels in tables/charts.
- New keys are added to all active languages (`de`, `en`, `fr`).
