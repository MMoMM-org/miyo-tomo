# Spec 032 — Live-Validierung (T6.5)

> Was von hier aus validiert wurde, und was einen echten Lauf braucht.
> Stand: 2026-09-03.

## Bereits bestätigt — auf echten Vault-Daten, ohne Änderung am Vault

Gemessen gegen `tomo-instance/config/moc-structure-cache.yaml`, die Datei, die
`garden-audit.py:550` tatsächlich lädt:

| | |
|---|---|
| Cache-Einträge | 346 |
| davon mit `up_value` | **0** — der Cache stammt aus der Zeit vor dieser Spec |
| `up_source` | 239 ohne, 85 `inline`, 22 `frontmatter` |
| `broken_up`-Findings | 29 — davon **28 inline, 1 frontmatter** |
| die eine property-residente | `Atlas/202 Notes/Aristotle and Metaphor - Seeing the similarity between things..md` → `Philosophy MOC (kit)` |

Der echte Scan über diese Daten, durch den echten Renderer, ergibt:

```
Broken parents: 29 findings — 28 in the note body, 1 in a note property.

**29 findings withheld this run — not fixable:**

- 29 stale cache — the discovery cache predates property routing.
  Run `/explore-vault` to refresh it, then re-run the audit.
```

**Kriterium 3** (die Split-Zeile meldet mindestens ein property-residentes Finding) — ✅ erfüllt.
**Kriterium 6** (auf einem Vor-Refresh-Cache werden Property-Findings zurückgehalten *mit* Remedy,
nicht falsch geroutet) — ✅ erfüllt, alle 29, keines mit Apply-Häkchen, keine body-orientierte
Aktion angeboten.

Bemerkenswert: die Findings sind **zurückgehalten** und trotzdem **zuordenbar**. Der Cache trägt
`up_source`, nur `up_value` fehlt. ADR-4 („wo steht die Deklaration") und ADR-5 („ist das diesen
Lauf fixbar") sind bewusst getrennte Fragen, und der Report beantwortet beide.

## Was einen echten Lauf braucht

Die verbleibenden Kriterien verlangen einen Cache-Rebuild und ein Apply durch Hashi. Beides ist von
außen nicht auslösbar: der Rebuild sollte im Container laufen (Host-seitige Vollscans laufen in
Kados 429-Limit), und das Apply passiert in Obsidian.

### Reihenfolge — sie ist nicht beliebig

```
1.  scripts/update-tomo.sh          # Instanz bekommt den neuen Code
2.  /explore-vault                  # Cache wird neu gebaut UND GEWINNT up_value
3.  /garden-audit                   # erst jetzt ist irgendetwas routbar
```

Ohne Schritt 2 sind weiterhin alle Findings `stale-cache` — der Lauf wäre korrekt, würde aber nichts
über das Routing beweisen.

### Woran du erkennst, dass es funktioniert hat

**Nach Schritt 2**, im neuen Cache: `up_value` steht auf **allen** Einträgen (nicht nur den
frontmatter-deklarierten — bei inline ist der Wert `None`, aber der *Schlüssel* muss da sein). Prüfen:

```
grep -c 'up_value:' tomo-instance/config/moc-structure-cache.yaml   # erwartet: 346
```

Steht dort 0, hat Schritt 1 den Code nicht ausgeliefert.

**Nach Schritt 3**, im Report:

- Die Withheld-Zeile ist **weg** oder deutlich kleiner — die 29 sind jetzt routbar.
- Die Split-Zeile steht weiterhin da: `28 in the note body, 1 in a note property`.
- Der Block für `Aristotle and Metaphor …` trägt **zusätzlich zu den anderen** diese zwei Zeilen:

  ```
  - **Fix target:** note property `up` — editing YAML properties.
    ⚠️ Comments inside this note's property block will not survive the edit.
  ```

- Seine Fix-Zeile spricht von **`up` property**, nicht von `` `up::` `` — die anderen 28 sprechen
  weiterhin von `` `up::` ``. Das ist der sichtbarste Unterschied und der schnellste Check.

**Nach dem Apply** (Häkchen setzen, `/inbox`):

- Die Notiz `Aristotle and Metaphor …` hat im Frontmatter ein geändertes `up:`.
- **Kommentare in genau diesem Property-Block sind weg** — das ist bekannt und unvermeidbar, deshalb
  die Warnung. Wenn dort Kommentare stehen, die du behalten willst: vorher sichern.
- Die 28 inline-deklarierten Notizen verhalten sich **unverändert** wie vorher.

### Wenn etwas anders aussieht

| Beobachtung | wahrscheinliche Ursache |
|---|---|
| weiterhin 29 withheld nach `/explore-vault` | Schritt 1 fehlte — die Instanz hat den alten Code |
| Split-Zeile fehlt ganz | keine `broken_up`-Findings mehr, oder `up_source` fehlt im Cache |
| Aristotle-Block ohne ⚠️-Warnung | sein `up_source` wurde nicht als `frontmatter` erkannt |
| Apply meldet Erfolg, Notiz unverändert | genau der Defekt, den diese Spec behebt — bitte melden |

Der letzte Fall wäre das eigentliche Signal: er würde bedeuten, dass die Action doch als Body-Fix
geroutet wurde. Nach dem, was hier verifiziert ist, kann das nicht passieren — es gibt keinen Pfad
von einem frontmatter-Finding zu `remove_up_link`/`add_relationship`. Falls doch, ist das der
wichtigste Fehlerbericht dieser Spec.

## Kosten (CON-3)

Zu protokollieren in `docs/evolution/inbox-cost-log.md` nach dem Lauf. Erwartung: **keine
zusätzlichen Kado-Calls** gegenüber vorher. `broken_up` ist cache-only — `_check_broken_up` hat
keine `graph_audit_fn`/`list_dir_fn`-Parameter und kann Kado strukturell nicht aufrufen. `up_value`
kommt aus Content, der bei `moc-tree-builder.py:410` ohnehin gelesen wurde.
