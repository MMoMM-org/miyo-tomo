# Spec 032 — Live-Validierung (T6.5)

> Was auf echten Vault-Daten bestätigt ist, was noch fehlt, und der eine Konfig-Eingriff,
> den der letzte Schritt braucht.
> Stand: 2026-09-03, nach `update-tomo` + `/explore-vault` + `/garden-audit`.

## Lauf vom 2026-09-03

Instanz-Code synchronisiert 09:40, Cache neu gebaut 10:05, Audit gelaufen 10:07.

### Schritt 2 — der Cache hat `up_value` bekommen ✅

| | vorher (2026-07-24) | nachher (2026-09-03) |
|---|---|---|
| Cache-Einträge | 346 | **359** |
| davon mit `up_value`-Schlüssel | 0 | **359** — alle |
| davon mit `up_source` | 107 | **359** — alle |
| `up_state: broken` | 29 | **42** |
| davon frontmatter-deklariert | 1 | **14** |

Der Schlüssel steht auf **allen** Einträgen, auch den inline-deklarierten (Wert dort `None`). Genau
diese Anwesenheit-statt-Wert-Unterscheidung ist ADR-3 — der `_MISSING`-Sentinel im Parser
unterscheidet „Cache kennt das Feld nicht" von „Property ist leer".

Prüfbefehl:

```
grep -c 'up_value:' tomo-instance/config/moc-structure-cache.yaml   # erwartet: 359
```

### Schritt 3 — der Report enthielt null `broken_up`-Findings ⚠️

9 Findings insgesamt: 4 Orphans, 5 stale MOCs. **Kein einziger kaputter Parent**, obwohl 42 im
Cache stehen.

**Ursache — kein Fehler.** In `tomo-instance/config/garden-audit-exclusions.yaml`:

```yaml
- target: {type: path, value: Atlas/}
  checks: all
  mode: temporary
  reason: working through 605 findings — revisit in 90 days
  created: '2026-07-21'
  until: '2026-10-19'
```

Der Cache-Scope ist vollständig `Atlas/200 Maps/` + `Atlas/202 Notes/` — **329 der 359 Einträge
liegen unter `Atlas/`**, und alle 42 broken ebenfalls. Die 9 verbleibenden Findings stammen aus den
30 Einträgen außerhalb. Gemessen:

| | Findings |
|---|---|
| `_check_broken_up` ohne Exclusions | 42 |
| mit den echten Exclusions | **0** |
| geblockt | 42 von 42 |

Die Exclusion-Maschinerie arbeitet korrekt. Der Nullwert ist die richtige Antwort auf die
Konfiguration, nicht ein Ausfall des Routings.

## Was ohne Vault-Änderung bestätigt ist

Gegen die 14 echten frontmatter-deklarierten Einträge, durch die echte Transform
(`render_actions._construct_edit_frontmatter_fields`):

| Wahl | Operation | Fälle |
|---|---|---|
| `remove` | `remove` | **14 von 14** |
| `repoint` | `set` | **14 von 14** |

Alle 14 `up_value` sind `list[1]` — deshalb ist `remove` (ganze Property löschen) hier immer
korrekt. Der `set`-auf-remove-Fall (Property hält mehrere Parents, einer kaputt) kommt in diesem
Vault **nicht vor**; er ist im Code abgedeckt und getestet, aber nicht live beobachtet.

Ein echtes Paar, verbatim:

```
remove   → {"operation": "remove", "expected": ["[[Philosophy MOC (kit)]]"]}
repoint  → {"operation": "set", "value": ["[[Philosophy MOC]]"],
            "expected": ["[[Philosophy MOC (kit)]]"]}
```

Beide validieren gegen `tomo/schemas/hashi-instructions.schema.json` — geprüft, nicht angenommen.
`expected` ist in beiden dasselbe Objekt, unverändert; `remove` trägt kein `value`.

**Kriterium 3** (Split-Zeile meldet mindestens ein property-residentes Finding) — auf dem
Vor-Refresh-Cache erfüllt, siehe Historie unten.
**Kriterium 6** (Property-Findings werden bei fehlendem `up_value` zurückgehalten *mit* Remedy,
nicht falsch geroutet) — erfüllt.

> **Messvorbehalt.** Die obigen Zahlen stammen aus direkten Aufrufen der Scan- und
> Transform-Funktionen über die echten Cache-Einträge. Sie beschreiben **nicht** einen gerenderten
> Report — den blockiert die `Atlas/`-Exclusion. Frühere Fassungen dieses Dokuments haben die
> Unterscheidung nicht gemacht: das damalige Prüfskript rief `run_scan()` ohne das
> `exclusions`-Argument auf, die Pipeline übergibt es. Deshalb standen dort 29 Findings, wo
> `/garden-audit` null liefert.

## ✅ Das Verhaltenskriterium — durchgeführt und bestätigt (2026-09-03)

**Ein property-residenter Fix ändert nach Freigabe tatsächlich die Notiz.** Beobachtet, nicht
abgeleitet.

Vorher (Cache, 10:05): `up_value: ['[[Nordböhmische Bergwelten]]']`, `up_source: frontmatter`.
Nach dem Apply, über Kado gelesen:

```yaml
---
related:
  - "[[⛰ Elbsandstein & Tschechien 2026]]"
created: 2025-11-23
Updated: 2026-09-03 15:05
---
```

Der `up:`-Schlüssel ist **vollständig weg** — das ist `operation: "remove"`, korrekt, weil die
Property genau diesen einen Eintrag hielt. Geschwister-Schlüssel unversehrt, Notizkörper
unangetastet, keine `Nordböhmische`-Referenz mehr in der Datei.

Die von `/inbox` erzeugte Action war **byte-gleich** mit der Vorhersage, die vor dem Lauf aus der
Wire berechnet wurde:

```json
{"id": "I01", "action": "edit_frontmatter",
 "path": "Atlas/202 Notes/Adersbacher Felsenstädte.md",
 "property": "up", "operation": "remove",
 "expected": ["[[Nordböhmische Bergwelten]]"], "applied": false}
```

Geroutet als `edit_frontmatter` — **nicht** als `remove_up_link`, das keine `up::`-Zeile gefunden,
stillschweigend Erfolg gemeldet und nichts geändert hätte. Genau dieser Defekt ist damit
verhaltensmäßig ausgeschlossen, nicht nur strukturell.

Nebenbefunde dieses Laufs, beide gesondert festgehalten statt hier eingearbeitet: die Detailzeile
sagte für property-residente Findings noch `up::` (behoben, `dd2712a`), und `broken_up` wirft drei
verschiedene Ursachen zusammen (Issue **#157**).

## Wie der Lauf zustande kam

Die `Atlas/`-Exclusion musste dafür temporär geöffnet werden — sie ist inzwischen wieder auf
`checks: all` zurückgesetzt (verifiziert: 329/329 geblockt). Der Ablauf zur Wiederholung:

### Der Eingriff

`Atlas/`-Regel von `checks: all` auf die Liste ohne `broken_up` umstellen:

```yaml
- target: {type: path, value: Atlas/}
  checks:
  - dead_link
  - duplicate_stem
  - orphan
  - stale_moc
  - unparented
  mode: temporary
  ...
```

Wirkung, gemessen: `broken_up` für alle 329 Atlas-Einträge **offen**, die anderen fünf Checks
weiterhin für alle 329 **still**. Ergebnis: 42 Findings, davon 14 property-resident — statt der 605
eines ungefilterten Scans.

`ALL_CHECK_NAMES` = `broken_up, dead_link, duplicate_stem, orphan, stale_moc, unparented`.

### Ablauf

```
1.  Exclusion wie oben umstellen   (Backup nicht vergessen)
2.  /garden-audit                  → 42 broken_up-Findings
3.  ein Häkchen setzen             → der property-residente Fall genügt
4.  /inbox                         → Apply durch Hashi
5.  Exclusion zurücksetzen
```

Der Konfig-Header sagt „Managed via `/garden-audit --configure`. Do not edit manually." Für einen
temporären, zurückgesetzten Testeingriff ist die Handbearbeitung vertretbar — aber sie ist ein
Eingriff, und Schritt 5 gehört dazu.

### Woran du erkennst, dass es funktioniert hat

**Im Report:**

- Split-Zeile: `Broken parents: 42 findings — 28 in the note body, 14 in a note property.`
- Der property-residente Block trägt zusätzlich:

  ```
  - **Fix target:** note property `up` — editing YAML properties.
    ⚠️ Comments inside this note's property block will not survive the edit.
  ```

- Seine Fix-Zeile spricht von **`up` property**, die body-residenten weiterhin von `` `up::` ``.
  Das ist der schnellste Sichtbeweis.

**Nach dem Apply:**

- Die Notiz hat im Frontmatter ein geändertes `up:`.
- **Kommentare in genau diesem Property-Block sind weg** — bekannt, unvermeidbar, deshalb die
  Warnung vor dem Häkchen. Wenn dort Kommentare stehen, die du behalten willst: vorher sichern.
- Die body-deklarierten Notizen verhalten sich unverändert.

### Wenn etwas anders aussieht

| Beobachtung | wahrscheinliche Ursache |
|---|---|
| weiterhin 0 broken_up nach dem Eingriff | Exclusion-Datei nicht neu geladen, oder Tippfehler in der Check-Liste |
| Split-Zeile fehlt ganz | keine `broken_up`-Findings — Exclusion greift noch |
| alle Findings withheld mit „stale cache" | `/explore-vault` fehlte, `up_value` steht nicht im Cache |
| Block ohne ⚠️-Warnung | sein `up_source` wurde nicht als `frontmatter` erkannt |
| **Apply meldet Erfolg, Notiz unverändert** | **genau der Defekt, den diese Spec behebt — bitte melden** |

Der letzte Fall wäre das eigentliche Signal: er würde bedeuten, dass die Action doch als Body-Fix
geroutet wurde. Nach dem, was verifiziert ist, kann das nicht passieren — es gibt keinen Pfad von
einem frontmatter-Finding zu `remove_up_link`/`add_relationship`. Falls doch, ist das der wichtigste
Fehlerbericht dieser Spec.

## Kosten (CON-3)

Zu protokollieren in `docs/evolution/inbox-cost-log.md` nach dem Apply-Lauf. Erwartung: **keine
zusätzlichen Kado-Calls**. `broken_up` ist cache-only — `_check_broken_up` hat keine
`graph_audit_fn`/`list_dir_fn`-Parameter und kann Kado strukturell nicht aufrufen. `up_value` kommt
aus Content, der bei `moc-tree-builder.py:410` ohnehin gelesen wurde.

## Historie — Vor-Refresh-Cache (2026-07-24)

Auf dem alten Cache (346 Einträge, kein `up_value`) ergab der Scan 29 `broken_up`-Findings, alle
zurückgehalten mit `Run /explore-vault to refresh it`, keines mit Apply-Häkchen, keine
body-orientierte Aktion angeboten. Bemerkenswert war dabei: die Findings waren **zurückgehalten**
und trotzdem **zuordenbar** — der Cache trug `up_source`, nur `up_value` fehlte. ADR-4 („wo steht
die Deklaration") und ADR-5 („ist das diesen Lauf fixbar") sind bewusst getrennte Fragen, und der
Report beantwortete beide. Das ist die ADR-5-Garantie auf echten Daten, und sie gilt weiterhin —
mit dem oben genannten Messvorbehalt.
