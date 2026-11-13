# Arbor Desk Cheat Sheet — Keyboard Shortcuts & Status Badges
*Quick Reference Card for Herbarium Assistants & Museum Interns • Print & Tape Beside Your Monitor*

---

## 🚀 PRIMARY WORK KEYS (Rest Your Mouse Hand!)

```
┌─────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ KEYBOARD SHORTCUT               │ WHAT IT DOES AT YOUR DESK                                   │
├─────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ [ CTRL ] + [ ENTER ]            │ MARK REVIEWED & ADVANCE (Signs off sheet, advances to next) │
│ [ SPACE ]                       │ TOGGLE PROBLEM CHECKBOX (Flags or unflags selected problem) │
│ [ ↓ ]  /  [ ↑ ]                 │ MOVE DOWN / UP (Steps through cards in Specimen Directory)  │
│ [ CTRL ] + [ ↓ ]  /  [ ↑ ]      │ JUMP TO NEXT / PREV PROBLEM (Skips clean records directly)  │
│ [ CTRL ] + [ S ]                │ SAVE ACTIVE WORKBOOK (Writes all updates safely to Excel)   │
└─────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 🔍 SEARCHING & RECORD NAVIGATION

```
┌─────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ KEYBOARD SHORTCUT               │ ACTION                                                      │
├─────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ [ CTRL ] + [ K ]                │ OMNI-SEARCH & COMMAND PALETTE (Type #ID or command name)    │
│ [ CTRL ] + [ F ]                │ JUMP TO SEARCH BAR (Type genus, species, or accession #)    │
│ [ CTRL ] + [ G ]                │ FILTER MENU (Show only unreviewed, problem cards, or photos)│
│ [ ALT ] + [ ← ]  /  [ → ]       │ BROWSING HISTORY (Go back or forward in recent records)     │
└─────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 📝 TYPING DATA & MISSING LABEL CODES

```
┌─────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ KEYBOARD SHORTCUT               │ ACTION                                                      │
├─────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ [ CTRL ] + [ E ]  or  [ I ]     │ JUMP TO FIRST FORM FIELD (Start typing botanical details)   │
│ [ CTRL ] + [ L ]  or  [ F4 ]    │ JUMP TO STORAGE LOCATION (Start typing Cabinet or Shelf)    │
│ [ CTRL ] + [ Z ]  /  [ Y ]      │ UNDO / REDO (Reverts or re-applies your last text change)   │
│ [ CTRL ] + [ SHIFT ] + [ M ]    │ INSERT `unknown:missing` (?m) - Missing from paper label    │
│ [ CTRL ] + [ SHIFT ] + [ I ]    │ INSERT `unknown:indecipherable` (?i) - Unreadable / damaged │
│ [ CTRL ] + [ SHIFT ] + [ U ]    │ INSERT `unknown:undigitized` (?u) - Skipped for now         │
│ [ CTRL ] + [ SHIFT ] + [ W ]    │ INSERT `withheld` (?w) - Confidential / protected location  │
│ [ CTRL ] + [ SHIFT ] + [ BKSP ] │ CLEAR FIELD VALUE (Erases field contents completely)        │
└─────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 🖼️ SPECIMEN PHOTOS & VIEW CONTROLS

```
┌─────────────────────────────────┬─────────────────────────────────────────────────────────────┐
│ KEYBOARD SHORTCUT               │ ACTION                                                      │
├─────────────────────────────────┼─────────────────────────────────────────────────────────────┤
│ [ ALT ] + [ R ]                 │ ROTATE 90° CLOCKWISE (Fixes upside-down specimen scans)     │
│ [ CTRL ] + [ + ]  /  [ - ]      │ ZOOM IN / ZOOM OUT (Inspects fine hairs, seeds, and pencil) │
│ [ CTRL ] + [ 0 ]                │ RESET ZOOM VIEW (Fits full paper sheet back onto screen)    │
│ [ SHIFT ] + [ ← ]  /  [ → ]     │ NEXT / PREVIOUS PHOTO (Flips between multiple specimen scans│
│ [ DOUBLE-CLICK PHOTO ]          │ DETACHED HIGH-RES POPUP (Scroll-wheel zoom up to 500%)      │
│ [ F6 ]  /  [ F7 ]  /  [ F8 ]    │ TOGGLE PANELS (F6: Directory list • F7: Form • F8: Photos)  │
│ [ F1 ]                          │ OPEN ON-SCREEN SHORTCUTS HUD (Interactive search cheat sheet)│
└─────────────────────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 🏷️ COMPACT BADGE COLOR GUIDE (What Badges Mean in Excel)

| Badge | Color | Meaning for the Trainee | Excel Column (`Observation` Sheet) |
| :---: | :---: | :--- | :--- |
| **`[ REV ]`** | **Green** | Verified clean and confirmed correct | `Reviewed = TRUE` (No problem flags) |
| **`[ REV+ERR ]`** | **Orange**| Verified physically, but a noted issue remains | `Reviewed = TRUE` + Problem Flag `TRUE` |
| **`[ TAX ]`** | **Red** | Plant name spelling, genus, or species issue | `Genus_Problem = TRUE` / `Species_Problem = TRUE` |
| **`[ PROV ]`** | **Amber** | Collector name, date, or locality missing | `Collector_Problem = TRUE` / `Date_Problem = TRUE` |
| **`[ BOX ]`** | **Brown** | Storage box mismatch, damaged housing | `Box_Label_Problem = TRUE` |
| **`[ IMG ]`** | **Blue** | Photo scan is missing, blurry, or unlinked | `Images_Problem = TRUE` / `Images_Missing = TRUE` |
| **`[ CFCT ]`** | **Purple**| Historical ledger book or GBIF disagrees | Mismatch against loaded Historical Books |
| **`[ UNREV ]`** | **Gray** | New or pending record waiting for review | `Reviewed = FALSE` (or blank) |

---

## 🛡️ "DON'T PANIC!" SAFETY TIP
> **You cannot break anything.** Arbor automatically creates timestamped safety backups in the `.arbor_backups/` folder before every major operation, so mistakes can be undone in seconds. If Microsoft Excel is open on your desktop, close it before clicking save so Windows does not lock the file!
