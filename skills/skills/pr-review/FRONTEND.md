# Frontend Review Checks

Apply these checks in addition to the standard review lens whenever the PR touches React/MUI frontend code (`.tsx`, `.ts` component files, `sx` props, `styled()` calls, inline `style` props).

---

## Hardcoded Magic Values in Embedded CSS

### What to look for

Scan every `sx={{...}}`, `style={{...}}`, and `styled()` call in the diff for:

1. **Raw hex color strings** — `'#RRGGBB'`, `'#RRGGBBAA'`, `rgba(...)`, `rgb(...)`, or named CSS colors (`'black'`, `'gray'`, `'grey'`, `'lightgray'`, `'white'`).
2. **Hardcoded pixel/rem/em values** for spacing, sizing, or font sizes — e.g. `height: 20`, `width: 20`, `fontSize: 14`, `padding: '4px 8px'`, `marginLeft: '1em'`, `borderRadius: '12px'`.
3. **String-pixel layout nudges** — `mt: '-2px'`, `top: -57`, `top: -145`. These are particularly brittle because they depend on sibling element heights with no declared dependency.
4. **Hardcoded font weights** — `fontWeight: 700` instead of `theme.typography.fontWeightBold`.
5. **`style={{}}` used instead of `sx`** — a plain `style` prop bypasses MUI's theme/sx system entirely. Flag any new `style={{...}}` that should use `sx`.
6. **Duplicated `sx` objects** — identical or near-identical style blocks copy-pasted within the same file without a shared constant.

### Cross-check against the theme

Before flagging a value, check `packages/common/src/theme/palette.ts` and `packages/common/src/theme/index.ts` for an existing token. Key tokens for this codebase:

| Raw value | Theme token |
|---|---|
| `rgba(243, 208, 83, ...)` | `alpha(palette.warning.main, <opacity>)` |
| `#74550F` | `palette.pill_pending.primary` |
| `#F3D05332` | `palette.pill_pending.background` |
| `#0078d4` | `palette.primary.main` |
| `#FF5263` | `palette.error.main` |
| `#DFE3E8` | `palette.divider` |
| `rgba(0,0,0,0.87)` | `palette.text.primary` / `'text.primary'` |
| `rgba(0,0,0,0.54)` | `palette.text.secondary` / `'text.secondary'` |
| `'black'`, `'white'` | `palette.common.black` / `palette.common.white` |
| `'gray'`, `'grey'` | `'text.secondary'` or `'text.disabled'` depending on context |
| `'lightgray'` | `palette.divider` or `palette.grey[300]` |
| `fontWeight: 700` | `theme.typography.fontWeightBold` |
| `height/width: 20` | `theme.spacing(2.5)` |
| `fontSize: 14` | `fontSize: 'small'` (MUI built-in) or `theme.typography.caption.fontSize` |
| `borderRadius: '12px'` | `theme.spacing(1.5)` or `theme.shape.borderRadius` |

If a value appears in the diff but has **no palette token**, flag it with a suggestion to either introduce a token or derive it (e.g. `darken(palette.pill_pending.primary, 0.1)` for a dark variant).

### Severity and category

Use `**[maintainability]**` for all findings in this section. Sub-severities:

- **Bug risk**: A hardcoded hex that does not match any palette token for the same semantic intent (e.g. using `#D84336` for error state when `palette.error.main` is `#FF5263`) — flag as a notable finding, not just a nit.
- **Duplication**: The same raw color/spacing object copy-pasted in multiple places within one file — flag with a suggested shared constant.
- **Everything else**: Nit. Label with `**Nit:**` as the heading per the standard comment format.

### Pre-existing vs. introduced

Only flag values **introduced or modified in this PR's diff**. If pre-existing files have the same issues, note them once in a file-level or PR comment as technical debt to track separately — do not leave inline comments on lines not in the diff.

---

## Table Column Widths

When the diff touches react-table column configuration files (e.g. `DatasetColumns.tsx`, `DatasetMgmtColumns.tsx`), check whether bare integer `width` / `minWidth` values have named constants. If multiple columns in the same file share similar width values, suggest a `COLUMN_WIDTHS` or `COL_WIDTH` constant object at the top of the file.

---

## Absolute Layout Offsets

Flag `top`, `bottom`, `left`, `right` values that are hardcoded negative pixel offsets (e.g. `top: -145`, `top={-57}`) used to position elements relative to siblings. These are fragile because they break silently when sibling heights change. Use `**[structure]**` for these findings. Suggest extracting to a named constant with a comment explaining the dependency:

```tsx
// Height of the DataTable header row — keep in sync with DataTableHeader
const TABLE_HEADER_HEIGHT = 145;
...
top: -TABLE_HEADER_HEIGHT
```

---

## When to Apply

Apply the full checklist above when:
- The diff adds new React components or substantial `sx` blocks.
- The diff modifies existing `sx`/`styled` calls.

Skip or abbreviate when:
- The PR only touches non-UI files (API serializers, types, Redux slices, utility functions).
- The diff's only frontend change is a rename or import path fix.
