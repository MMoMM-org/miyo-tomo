---
name: obsidian-canvas
description: "Use PROACTIVELY when composing, authoring, reading, or editing Obsidian Canvas files (.canvas) or JSON Canvas structures, including canvas nodes, canvas edges, canvas groups, or the canvas color system. MUST BE USED when the task explicitly names Obsidian Canvas, JSON Canvas, or .canvas files. Do NOT activate for .base files, .md notes, or generic diagram discussions unrelated to the JSON Canvas 1.0 format."
user-invocable: true
model: sonnet
effort: low
---
# Obsidian Canvas
# version: 0.1.0

Format knowledge for composing and editing Obsidian Canvas files (`.canvas`) per the JSON Canvas 1.0 spec.

## File Structure

A `.canvas` file is a JSON document with two optional root arrays:

```json
{
  "nodes": [],
  "edges": []
}
```

Both arrays are optional and may be empty. Array order determines z-index: earlier entries render beneath later ones.

## Nodes

### Shared Fields (all node types)

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `id` | Yes | string | Unique within the file; recommended: 16-char lowercase hex |
| `type` | Yes | string | `text`, `file`, `link`, or `group` |
| `x` | Yes | integer | X position (top-left corner), pixels; negative values allowed |
| `y` | Yes | integer | Y position (top-left corner), pixels; negative values allowed |
| `width` | Yes | integer | Width in pixels |
| `height` | Yes | integer | Height in pixels |
| `color` | No | canvasColor | Preset `"1"`–`"6"` or hex string `"#RRGGBB"` |

`x` increases rightward; `y` increases downward. The canvas has no fixed origin.

### Text Nodes (`type: "text"`)

Displays Markdown content.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `text` | Yes | string | Plain text with Markdown syntax; use `\n` for newlines in JSON |

```json
{
  "id": "6f0ad84f44ce9c17",
  "type": "text",
  "x": 0,
  "y": 0,
  "width": 400,
  "height": 200,
  "text": "# Main Concept\n\nSummary goes here."
}
```

Pitfall: use `\n` for line breaks, not the literal characters `\` + `n`.

### File Nodes (`type: "file"`)

References a file inside the vault (note, image, PDF, etc.).

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `file` | Yes | string | Vault-relative path to the file |
| `subpath` | No | string | Section anchor starting with `#`, e.g. `#Heading` |

```json
{
  "id": "a1b2c3d4e5f67890",
  "type": "file",
  "x": 500,
  "y": 0,
  "width": 400,
  "height": 300,
  "file": "Projects/Project Alpha.md",
  "subpath": "#Goals"
}
```

### Link Nodes (`type: "link"`)

Embeds a web URL preview.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `url` | Yes | string | Absolute URL |

```json
{
  "id": "c3d4e5f678901234",
  "type": "link",
  "x": 1000,
  "y": 0,
  "width": 400,
  "height": 200,
  "url": "https://jsoncanvas.org"
}
```

### Group Nodes (`type: "group"`)

Visual container for other nodes. Child nodes are positioned within the group bounds but are not
structurally nested in the JSON — they simply occupy the same spatial area.

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `label` | No | string | Display title for the group |
| `background` | No | string | Vault-relative path to a background image |
| `backgroundStyle` | No | string | `cover`, `ratio`, or `repeat` |

```json
{
  "id": "d4e5f6789012345a",
  "type": "group",
  "x": -50,
  "y": -50,
  "width": 1000,
  "height": 600,
  "label": "Phase 1",
  "color": "4"
}
```

Child nodes are positioned by setting their `x`/`y` coordinates to fall within the group's bounds.
Groups have no parent–child relationship in the JSON; containment is purely spatial.

## Edges

Edges connect two nodes. Both `fromNode` and `toNode` must reference IDs that exist in `nodes`.

| Field | Required | Type | Default | Notes |
|-------|----------|------|---------|-------|
| `id` | Yes | string | — | Unique within the file |
| `fromNode` | Yes | string | — | Source node ID |
| `toNode` | Yes | string | — | Target node ID |
| `fromSide` | No | string | — | `top`, `right`, `bottom`, or `left` |
| `toSide` | No | string | — | `top`, `right`, `bottom`, or `left` |
| `fromEnd` | No | string | `none` | `none` or `arrow` |
| `toEnd` | No | string | `arrow` | `none` or `arrow` |
| `color` | No | canvasColor | — | Line color |
| `label` | No | string | — | Text label on the edge |

```json
{
  "id": "0123456789abcdef",
  "fromNode": "6f0ad84f44ce9c17",
  "fromSide": "right",
  "toNode": "a1b2c3d4e5f67890",
  "toSide": "left",
  "toEnd": "arrow",
  "label": "informs"
}
```

Default endpoint behavior: the `fromEnd` defaults to `none` (no arrowhead at source); `toEnd` defaults
to `arrow` (arrowhead at target). Omitting both gives a directed edge pointing from source to target.

## Color System

The `canvasColor` type accepts two forms:

| Form | Example | Notes |
|------|---------|-------|
| Hex string | `"#FF5733"` | Must include `#`, uppercase or lowercase |
| Preset number string | `"1"` through `"6"` | Rendered per the application's theme |

Preset-to-color mapping (application-defined; Obsidian defaults):

| Preset | Obsidian default |
|--------|-----------------|
| `"1"` | Red |
| `"2"` | Orange |
| `"3"` | Yellow |
| `"4"` | Green |
| `"5"` | Cyan |
| `"6"` | Purple |

The spec does not mandate specific RGB values for presets — applications may use their own palette.

## ID Rules

- IDs must be unique strings within the file (across both nodes AND edges).
- The spec does not mandate a format; conventional practice: 16-character lowercase hexadecimal.
- Generate IDs randomly; do not derive them from content (avoids collisions on duplicate content).

Generate example: `"6f0ad84f44ce9c17"`, `"a3b2c1d0e9f87654"`.

## Layout Guidelines

- Coordinates extend infinitely in all directions; negative values are valid.
- `x`/`y` is the top-left corner of the node.
- Leave 50–100 px spacing between adjacent nodes; 20–50 px padding inside groups.
- Align to multiples of 10 or 20 for cleaner layouts.

Typical node sizes:

| Node type | Width | Height |
|-----------|-------|--------|
| Small text card | 200–300 | 80–150 |
| Medium text card | 300–450 | 150–300 |
| Large text / note | 400–600 | 300–500 |
| File embed | 300–500 | 200–400 |
| Link preview | 250–400 | 100–200 |

## Validation Checklist

Before saving a `.canvas` file, verify all 8 items:

1. All `id` values are unique across nodes and edges.
2. Every `fromNode` and `toNode` references an `id` that exists in `nodes`.
3. `text` is present on every node with `type: "text"`.
4. `file` is present on every node with `type: "file"`.
5. `url` is present on every node with `type: "link"`.
6. `type` is one of: `text`, `file`, `link`, `group`.
7. Color values are preset strings `"1"`–`"6"` or valid hex strings starting with `#`.
8. The file is valid JSON (no trailing commas, unescaped newlines, or encoding issues).

If validation fails: check for duplicate IDs, dangling edge references (`fromNode`/`toNode` pointing
to non-existent nodes), or malformed JSON strings (literal newlines in text fields must be `\n`).
