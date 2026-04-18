# Instruction-Builder Test Fixtures

Vault: `/Volumes/Moon/Coding/MiYo/temp/Privat-Test/`
Updated: 2026-04-17
Purpose: Controlled inbox state for testing full Pass 1 → Pass 2 pipeline.

## Inbox Contents (12 notes)

### Board Game Notes (3 new — trigger new MOC creation)

No existing MOC covers board games/tabletop. These three notes should
cluster and trigger `create_moc` for a new "Board Games (MOC)" or similar
under `2700 - Art & Recreation`.

| File | Content | Expected Actions |
|------|---------|------------------|
| `Catan Strategien.md` | Eröffnungsstrategien, Longest Road vs Largest Army | `create_atomic_note`, `link_to_moc` → new Board Games MOC |
| `Wingspan Vogelkunde.md` | Engine Building + Ornithologie, Erweiterungen | `create_atomic_note`, `link_to_moc` → new Board Games MOC |
| `Gloomhaven Kampfsystem.md` | Kartenbasiertes Kampfsystem, Frosthaven | `create_atomic_note`, `link_to_moc` → new Board Games MOC |

Collective trigger: `create_moc` + `link_to_moc` into `2700 - Art & Recreation`.

### Hokkaido City Notes (4 — link to existing Japan MOC)

| File | Content | Expected Actions |
|------|---------|------------------|
| `Sapporo.md` | Hauptstadt, Schneefestival, Miso-Ramen | `create_atomic_note`, `link_to_moc` → Japan (MOC) |
| `Hakodate.md` | Hafenstadt, Nachtaussicht, Shinkansen | `create_atomic_note`, `link_to_moc` → Japan (MOC) |
| `Asahikawa.md` | Zweitgrößte Stadt, Shoyu-Ramen, Zoo | `create_atomic_note`, `link_to_moc` → Japan (MOC) |
| `Furano.md` | Lavendelfelder, Powder Snow | `create_atomic_note`, `link_to_moc` → Japan (MOC) |

### Existing Notes (kept from previous inbox)

| File | Content | Expected Actions |
|------|---------|------------------|
| `Japanische Gerichte.md` | Rezeptsammlung | `create_atomic_note`, `link_to_moc` → Japan (MOC) |
| `Evergreen Notes.md` | Andy Matuschak concept | `create_atomic_note`, `link_to_moc` → Type of Notes (MOC) |
| `Fleeting Notes.md` | Zettelkasten concept | `create_atomic_note`, `link_to_moc` → Type of Notes (MOC) |

### Daily Log Notes (instruction-only, no file creation)

| File | Content | Expected Actions |
|------|---------|------------------|
| `Wichtige Notiz.md` | Arzt am 30.03., Manuelle Therapie | `log_entry` → Daily 2026-03-30 |
| `Sport.md` | Sport am 26.03. | `log_entry` + `tracker` → Daily 2026-03-26 |

## Expected Action Type Coverage

| Action Type | Triggered By |
|-------------|-------------|
| `create_atomic_note` | All 10 note-creating items |
| `create_moc` | Board game cluster (3 notes, no existing MOC) |
| `link_to_moc` | All atomic notes + new MOC → parent MOC |
| `log_entry` | Wichtige Notiz, Sport |
| `tracker` (update_daily) | Sport |

## Verification Checklist

- [ ] Rendered atomic note files exist in inbox (10 files)
- [ ] Rendered MOC file exists in inbox (1 file: Board Games MOC)
- [ ] New MOC proposed in suggestions with parent 2700 - Art & Recreation
- [ ] No `undefined` string anywhere
- [ ] Templater syntax preserved in rendered files
- [ ] Instruction set uses "Move note" not "Create note"
- [ ] Daily log entries reference correct dates
- [ ] Suggestion-parser extracts edited names/tags/locations from vault
