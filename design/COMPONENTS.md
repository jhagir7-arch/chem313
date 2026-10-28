# Chem313 v2 component spec

Source of truth for the shell UI. Tokens: `tokens.json` / `tokens.css`. Reference: the
approved 2026-10-24 mockups (Build & Check, Setup & Run, Results & Record).

## Rules that apply to everything

- 8-px grid. Heights come from `--h-*` tokens; nothing is sized ad hoc.
- UI text 12.5 px system font. Every number, path, hash, identifier and unit is
  `--font-mono` with tabular numerals, right-aligned in tables, unit in the column header.
- 1-px borders, square corners, no shadows, no gradients, no pills, no cards with
  descriptions. Hierarchy comes from background steps (`--bg` → `--bg-raised` →
  `--bg-panel`) and 11-px uppercase section labels, not from size.
- One accent (`--accent`) for selection, focus and the primary action. Status colours only
  for job state: queued/draft muted, running `--warn`, converged `--ok`, failed `--err`.
- Copy is labels and units. No sentences in chrome. The scientific scope line is the one
  sentence allowed, in the Results header.
- Keyboard: every toolbar action has a shortcut; focus ring `2px solid var(--accent)`
  inset; Tab order follows the visual order; `Esc` closes palette/popovers.
- Light and dark follow the OS. Never author a colour outside the tokens.
- Real controls: `<button>`, `<a>`, `<input>` + `<label>`, `<table>`. Icons are inline
  stroke SVG, 12–14 px, `aria-hidden` unless icon-only (then `aria-label`).

## Shell (fixed chrome, every mode)

```
menubar  (native; the webview shows nothing here)
toolbar  38px   actions · command field · Guided toggle
┌ navigator 232px ┬ workspace (tabs 30px + content) ┬ inspector 300px ┐
└──────────────── console 160px (Jobs | Console | Engines) ───────────┘
statusbar 24px
```

| Component | Spec |
|---|---|
| **Toolbar** | `--bg-raised`, bottom border. Buttons `.tool` 26 px, 10 px padding, 6 px gap; vertical rule between groups; primary action `.tool.primary` (`--accent-fill`), destructive `.tool.danger` (`--err-border`/`--err-text`). Right side: command field (300 px, placeholder "Command or molecule…  ⌘K") and the Guided toggle (8-px dot + label). |
| **Navigator** | `--bg-raised`, right border. Groups: Molecules, Calculations, Records, Tutorials with 11-px uppercase labels. Rows 22 px, 8 px padding, status dot (8 px) or ✓/○/● glyph, name, right-aligned mono secondary (formula, #id). Hover `--bg-hover`, selected `--bg-selected` + `--text-strong`. Resizable 180–360 px, collapsible. |
| **Workspace tabs** | 30 px, `--bg-raised`; tab 14 px padding, right border; active: `--bg`, `--text-strong`, 2-px inset top rule in `--accent`. Right end: mono context (molecule · draft · saved time). Tabs are fixed: Structure, 3D, Setup, Results. |
| **Inspector** | `--bg-raised`, left border, scrolls. Sections `.sec` (8/10 px padding, bottom border, 11-px uppercase h3). Key/value grid `.kv` 96–110 px label column. Guided block uses `--bg-guided` and `--accent-text` heading. |
| **Console** | `--bg-inset`, top border. Sub-tabs 26 px: Jobs (table), Console (mono log, timestamps `--text-faint`), Engines. Resizable 100–400 px, collapsible. |
| **Status bar** | 24 px, `--bg-panel`, 11-px mono, 18-px gaps: engine state dot + version · Tier + Add-ons link · job counts · spacer · data folder · app version. |
| **Command palette** | ⌘K / Ctrl-K. 560 px wide, top-anchored, `--bg-raised`, 1-px border, list rows 26 px with action, shortcut (mono, muted). Fuzzy over commands, molecules, calculations, records. |

## Content components

| Component | Spec |
|---|---|
| **Table** | Full width, collapsed borders. Header 11 px `--text-muted`, 4/8 px padding, `--border` bottom. Cells 3–4/8 px, `--border-faint` bottom, `white-space: nowrap`. `.num` right-aligned mono. Selected row `--bg-selected`. Wide tables scroll inside their pane, never the page. |
| **Stat strip** | Row of `.stat` blocks (10/12 px padding, right border): label 11 px uppercase, value 22 px mono medium `--text-strong`, unit 11 px mono muted. Status values use status colour. |
| **Field grid** | `.field`: 150 px label · 180 px control · hint. Controls 24 px, `--bg`, `--border`, mono for numeric. Hint 11.5 px muted, carries the unit. |
| **Engine table** | Radio · engine+version · method · kind · tier · status · est. time · action. Unavailable rows muted with an action (`Install <pack> · size`, `Locate executable…`). Only installed engines are selectable. |
| **Queue / Jobs table** | # · molecule · engine·method · state (status colour) · progress (`.bar` 6 px, `--accent` fill, `--ok` when done) · iter · E · wall · action. |
| **Element palette** | 28×26 buttons, `--bg-panel`, selected `--bg-selected` + accent border; element buttons coloured by `--el-*`. |
| **3D viewport** | `--bg-viewport`, axis gizmo bottom-left, mono hint bottom-right. Keyboard: arrows rotate, +/− zoom, Tab cycles atoms, Enter selects. |
| **Chart** | Inline SVG, `--border-faint` gridlines, mono axis labels, bars `--el-c` (initial) and `--accent` (final), values above bars. Unit switch buttons in the pane header. |
| **Geometry change table** | # · El · x₀ x₁ · y₀ y₁ · z₀ z₁ · |Δ|; initial columns muted. Footer line: largest move, heavy-atom max, bond count. |
| **Provenance block** | `.kv` mono: schema, engine+version+`real`, embedding+seed, method, tolerances, machine. Artefact table: name · sha256 (wrapped, muted). |
| **Guided block** | One question, one control, one Check/Submit button, optional one-line note. Never more than one per screen. |
| **Log** | Mono 11.5 px, line-height 1.5, timestamps `--text-faint`, `white-space: pre`. |

## Copy rules

- Labels: sentence case, no trailing punctuation. Units in headers (`E / kcal·mol⁻¹`, `x / Å`).
- Status words: `queued`, `running`, `converged`, `failed`, `draft`, `not detected`,
  `pack not installed`. Lowercase.
- Never: "real", "reproducible", "research preview", "what would you like to do", or any
  sentence that explains a feature. Exceptions: the Results scope line and Guided questions.
