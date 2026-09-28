---
name: Herbarium Vault Audit
colors:
  surface: '#f6fbf3'
  surface-dim: '#d7dbd4'
  surface-bright: '#f6fbf3'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f5ee'
  surface-container: '#ebefe8'
  surface-container-high: '#e5eae2'
  surface-container-highest: '#dfe4dd'
  on-surface: '#181d19'
  on-surface-variant: '#414942'
  inverse-surface: '#2c322d'
  inverse-on-surface: '#edf2eb'
  outline: '#717972'
  outline-variant: '#c0c9c0'
  surface-tint: '#35684b'
  primary: '#023d23'
  on-primary: '#ffffff'
  primary-container: '#205438'
  on-primary-container: '#90c7a3'
  inverse-primary: '#9cd3af'
  secondary: '#2c694e'
  on-secondary: '#ffffff'
  secondary-container: '#aeeecb'
  on-secondary-container: '#316e52'
  tertiary: '#6f0011'
  on-tertiary: '#ffffff'
  tertiary-container: '#951120'
  on-tertiary-container: '#ffa19e'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b7efca'
  primary-fixed-dim: '#9cd3af'
  on-primary-fixed: '#002110'
  on-primary-fixed-variant: '#1c5034'
  secondary-fixed: '#b1f0ce'
  secondary-fixed-dim: '#95d4b3'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#0e5138'
  tertiary-fixed: '#ffdad8'
  tertiary-fixed-dim: '#ffb3b0'
  on-tertiary-fixed: '#410006'
  on-tertiary-fixed-variant: '#900b1d'
  background: '#f6fbf3'
  on-background: '#181d19'
  surface-variant: '#dfe4dd'
typography:
  headline-lg:
    fontFamily: Newsreader
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: Newsreader
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Newsreader
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
  taxon-italic:
    fontFamily: Newsreader
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  mono-accession:
    fontFamily: JetBrains Mono
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 20px
  mono-coordinate:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system is engineered for field botanists, herbarium collection managers, and botanical conservators operating in cold vaults, mobile compactor stacks, and dim archival corridors. The aesthetic balances classical natural-history taxonomy with tactile, utilitarian field hardware. 

The brand narrative marries archival reverence with industrial operational speed. It rejects fragile luxury or overly decorative tendencies in favor of a sturdy, tool-grade instrument feel: confident, hyper-legible, ergonomic, and physically reassuring under continuous single-handed usage.

### Design Movement
**Tactile Archival Utility:** A synthesis of classic editorial taxonomy (monumental botanical serifs) and heavy-duty field hardware instrumentation (dense monospace data strings, debossed stepper interfaces, 44px+ touch boundaries, and high-visibility physical state indicators).

## Colors

The palette directly references archival conservation media, preserved specimen folios, and specimen mounting paper, structured for high contrast in low-lux subterranean vault lighting.

### Palette Architecture
- **Primary (`#205438`) & Secondary (`#2d6a4f`):** Dense Fern Green and Forest Sage designate focused audit zones, primary affirmative triggers, and valid specimen records.
- **Deep Archival Ink (`#141915`):** The dominant neutral for maximum typographic contrast against warm backgrounds, replacing default cold blacks with deep carbon botanical ink.
- **Warm Alabaster Neutral (`#f5f4ef`) & Crisp Card Pure White (`#ffffff`):** Form the layered surface system; `#f5f4ef` creates a glare-free canvas, while `#ffffff` isolates discrete accession records.
- **Warm Parchment Border (`#e3dfd5`):** Defines tactile structural borders and physical hardware divides without harsh visual vibration.
- **Functional Semantics:**
  - **Soft Emerald Tint (`#eef6f0`):** Denotes synchronized database records, positive barcode read-backs, and active RF telemetry.
  - **Warning Ochre (`#d97706`):** Identifies coordinate mismatches, unfiled accession batches, and offline buffers.
  - **Alert Crimson (`#c93a40`):** Reserved for audit discrepancies, duplicate accession alerts, and missing physical specimens.

## Typography

The typographic hierarchy implements three distinct typefaces, each strictly assigned to a functional layer:

1. **Display & Binomials (`Newsreader`):** Used with editorial italics for botanical taxonomy (*e.g., Quercus robur var. pendula*), collector attributions, and vault section titles.
2. **Operational Interface & UI Controls (`Inter`):** Powers form controls, interactive steppers, state labels, modal dialogues, and instructions where legibility at arm's length is mandatory.
3. **Telemetry & Serial Accession Data (`JetBrains Mono`):** Dedicated to high-entropy strings, barcodes, batch IDs, optical scan outputs, and alphanumeric coordinate locations (*e.g., FL-01::CAB-04::SH-02*). Tabular figures prevent layout shifts during continuous rapid scanning.

## Layout & Spacing

The layout is built on a mobile-first 4-column fluid grid tailored for rugged hand-held devices and one-handed thumb navigation. 

- **Outer Margins:** Fixed at `1rem` (16px) on compact handhelds, expanding to `1.5rem` (24px) on tablet inventory stations.
- **Vertical Rhythm:** Rooted in a strict 4px sub-grid with primary layout increments of 8px (`space-sm`), 12px (`space-md`), and 16px (`space-lg`).
- **Touch Target Threshold:** All tap boundaries enforce an unconditional minimum of 44px (height and width) to accommodate nitrile or cotton-gloved vault operators.
- **Viewport Constraints:** The primary workflow utilizes a fixed screen framework with an anchored coordinate selection header, a flexible continuous-feed center lane, and a rigid bottom dock housing the audit trigger and sync status.

## Elevation & Depth

This system avoids floating ethereal shadows and high-diffuse blurs in favor of structural physical layering and tactile mechanical relief.

- **Surface Tiers:** 
  - **Base Canvas (`#f5f4ef`):** The structural vault substrate.
  - **Raised Cards (`#ffffff`):** Specimen record containers elevated by a crisp `1px solid #e3dfd5` perimeter border paired with a physical contact shadow (`box-shadow: 0 1px 3px rgba(20, 25, 21, 0.06), 0 1px 2px rgba(20, 25, 21, 0.04)`).
  - **Inset / Recessed Wells:** Barcode inputs, coordinate steppers, and telemetry counters sit visually debossed into the card surface (`box-shadow: inset 0 1px 2px rgba(20, 25, 21, 0.06)` with a `1px solid #e3dfd5` line).
- **Sticky Planes & Drawers:** High-priority bottom persistence anchors (such as the audit commit bar) cast a directional upward shadow (`0 -4px 12px rgba(20, 25, 21, 0.08)`) over the scrollable accession feed.

## Shapes

The design system embraces a **Soft (Level 1)** industrial geometry. Corners feature compact, utilitarian radii (`0.25rem` / 4px base, `0.5rem` / 8px for cards and sheets) reminiscent of milled field computers and vintage steel index cabinets. Fully rounded pill treatments are strictly reserved for facility status capsules, synchronized tag badges, and binary toggle switches.

## Components

### Buttons & Interactive Steppers
- **Primary Hardware Button:** Minimum 48px height, solid `#205438` background, `#ffffff` typography (`Inter`, bold), 4px border radius. Active state produces a 1px downward translation with an intensified border tint.
- **Coordinate Steppers (`[ - ]` and `[ + ]`):** High-touch tactile toggles encased in an extruded segmented enclosure. Stepper buttons measure 44x44px minimum, featuring deep archival ink glyphs centered on `#ffffff` tiles, bordered by `#e3dfd5`. Pressed states flash `#eef6f0`.

### Segmented Facility & Compactor Pills
- Compact horizontal selector strips for `Vault`, `Floor`, `Compactor`, and `Shelf`. Selected segment fills with `#205438` with crisp white text; inactive segments sit on `#f5f4ef` with `#141915` text.

### Rapid Barcode Drawer & Continuous Accession Cards
- **Scanner Trigger Drawer:** Positioned at the upper half or reachable lower quadrant with an ambient debossed scan line guide and live text-entry fallback (`JetBrains Mono`).
- **Accession Feed Cards:** Crisp white background `#ffffff` with a left-edge 3px status bar:
  - Solid `#205438` for audited & synced.
  - `#d97706` for coordinate update pending.
  - `#c93a40` for flagged conflict.
- Includes scanned timestamp (`14:22:08`), monospace specimen catalog ID (`#2024-BOT-0894`), and the botanical Latin name in `Newsreader` italic.

### Audio / Haptic Chirp Indicators & Auto-Advance
- Embedded switch control styled after physical laboratory machinery with a knurled toggle visual. Accompanying audio-haptic feedback provides dual-sensory confirmation on valid decodes.

### Persistent Sticky Audit Commit Bar
- Fixed viewport bottom dock, height 64px, background `#ffffff`, top border `1px solid #e3dfd5`. 
- Houses the live network telemetry cluster on the left (`🟢 42ms Auto-sync ready` rendered in `JetBrains Mono` 11px uppercase) and the tactile primary "Commit Batch" trigger on the right.