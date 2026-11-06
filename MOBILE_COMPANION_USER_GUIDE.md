# Arbor Mobile Companion — Field & Curator Guide

The **Arbor Mobile Companion** is a dedicated, zero-install mobile web application that turns any smartphone or tablet into a companion terminal for physical specimen auditing in herbarium vaults, compactors, and collection stacks.

---

## 1. Quick Start & Pairing

```
┌────────────────────────────────────────────────────────┐
│ 1. On your Desktop Workstation:                        │
│    Click 📱 MOBILE in the top navigation bar.          │
│                                                        │
│ 2. Choose your Network Mode:                           │
│    • 🌐 Public (Internet): Campus & Eduroam Wi-Fi      │
│    • 📶 LAN only: Private Home / Offline Travel Router │
│                                                        │
│ 3. Click ▶ Start Mobile Session                        │
│                                                        │
│ 4. Scan the on-screen QR Code with your phone camera   │
└────────────────────────────────────────────────────────┘
```

### Network Modes Explained

* **🌐 Public (Internet) [Recommended for Institutions]**:
  * **When to use**: On university, museum, or hospital Wi-Fi networks (such as **Eduroam**).
  * **Why**: Institutional networks enforce "Client Isolation" firewalls that prevent mobile phones from talking directly to laptops on the local network. The Public mode establishes an encrypted tunnel (via Cloudflare or Pinggy/SSH) that bypasses network firewalls seamlessly.
  * **Warm-up**: While the secure tunnel connects in the background (3–10 seconds), Arbor displays the local LAN QR code immediately as a fast fallback. Once the tunnel is live, the QR code updates automatically.

* **📶 LAN only [Fast & Offline]**:
  * **When to use**: When your laptop and phone are connected to a private home Wi-Fi network or a portable travel router inside an underground vault with no internet access.
  * **Why**: Direct, ultra-low latency peer-to-peer connection without sending any traffic through the outside web.

### Pairing Options
* **QR Code**: Open your phone's camera or barcode scanner and tap the prompt. The secure session token is embedded in the link—no passwords required.
* **Copy Link Button**: Click **📋 Copy** in the desktop pairing window to copy the full URL to your clipboard for instant sharing via chat or email.
* **4-Digit PIN**: If opening a saved bookmark or bare URL on your phone without the token, enter the 4-digit PIN displayed on your laptop screen.

---

## 2. The Vault Walkthrough & Offline Trust Engine

Herbarium vaults are often located in basements or shielded behind heavy steel doors where Wi-Fi drops completely. The Mobile Companion is engineered with an **offline-first trust architecture**:

```
📱 Curator Edits Specimen
         │
         ▼
[Is Wi-Fi Connected?]
   ├── YES ──► Saved immediately to Workstation (✓ Synced)
   │
   └── NO ───► Saved immediately to Phone's IndexedDB Queue
               Banner shows: "⚠️ Offline — 4 edits queued on device"
               (Zero data loss; phone retains all values)
                     │
                     ▼ (Curator walks back into Wi-Fi range)
               Automatic Reconnection & Auto-Flush
               Banner shows: "🔄 Connected — Syncing 4 queued edits..."
               Desktop receives: "📥 Synced 4 offline edits"
```

### Tri-State Psychological Feedback
1. **While Typing / Editing**: Inputs register changes immediately.
2. **Auto-Save on Blur / Debounce**: Edits are committed immediately when you tap away or pause typing (800ms).
3. **Sync Confirmation**:
   * When connected, a toast confirms: `✓ Saved & synchronized`.
   * When offline, a confident badge confirms: `💾 Saved offline (queued for sync)`.

> [!IMPORTANT]
> **Never worry about losing data in the vault:**
> If you lose connection, continue auditing normally! All coordinate changes, review checkmarks, and field edits are preserved in hardware-backed storage on your mobile device and will flush automatically to the desktop the instant connection is restored.

---

## 3. Curatorial Auditing Workflows

### 3.1. Specimen Lookup & Rapid Stepping
* **Universal Search**: Type genus, species, accession number, or cabinet into the top search bar.
* **Filter Pills**: Tap `🕒 Unreviewed` or `⚠ Flagged` to step strictly through specimens requiring attention.
* **Steppers**: Use the **← Prev** and **Next →** buttons in the header to advance through specimen sheets consecutively without returning to the list.

### 3.2. Physical Coordinate Auditing (Location Tab)
The **Location Tab** provides tactile, high-speed coordinate entry:
* **Building**: Dropdown matching active museum collections (e.g., *Økern*, *Lid's hus*).
* **Floor**: Signed continuous integer stepping (`−` / `+` or direct value).
* **Cabinet & Shelf**: 
  * Tap `−` / `+` to increment/decrement shelf numbers.
  * Or **tap the number directly** to open the mobile numeric keypad for rapid 2-digit entry.
* **Stored As**: 1-tap storage presets (*Herbarium Sheet*, *Box*, *Envelope*, *Jar*, *Packet*, *Custom*).

### 3.3. "Copy from Previous" (1-Tap Replication)
When auditing a folder containing 20 specimen sheets that all share the same physical cabinet, shelf, and floor:
1. Set the correct coordinates on the first specimen.
2. Advance to the next specimen.
3. Tap **📋 Copy from Previous** at the top of the Location tab.
4. All physical coordinates duplicate instantly, saving dozens of repetitive keystrokes.

### 3.4. Batch Location Registrator
To relocate an entire stack of specimen folders to a new room or cabinet:
1. Tap the **📦 Batch Relocation** icon in the header toolbar.
2. Set your **Target Location Anchor** (Building, Cabinet, Shelf).
3. Scan barcodes or enter Object IDs into the rapid accession queue.
4. Tap **Commit Batch Location** to update all scanned records simultaneously.

### 3.5. Tactical Haptic Feedback & Glove Calibration
Auditing specimens requires looking back and forth between physical cabinet tags, shelf boxes, and the phone screen. The Mobile Companion delivers sensory vibration confirmations without requiring constant eye contact:
* **Steppers**: Crisp vibration tick on Cabinet/Shelf `−` / `+` clicks.
* **Review Status**: Double confirmation pulse when marked Reviewed; single pulse when cleared.
* **Copy Previous Location**: Distinct tactile acknowledgment.
* **Flag Problem**: Noticeable warning pulse when flagging a discrepancy.

> [!TIP]
> **Adjusting Haptic Strength**:
> Open **⚙ Settings** on your phone to toggle haptics or adjust intensity:
> * **Light**: Subtle clicks for bare hands in quiet offices.
> * **Medium** *(Default)*: Balanced tactile response for standard nitrile gloves.
> * **Strong**: Firm pulses for heavy archival cotton gloves.
> * **⚡ Test Button**: Tap `⚡ Test` in the settings drawer to test the selected strength on your handheld device immediately.
> *(Note: The Web Vibration API is natively supported on Android Chrome/Firefox; iOS Safari WebKit restricts vibration).*

### 3.6. Accidental Refresh & Tab Closure Guard
If you accidentally swipe down to refresh or swipe backwards to close the browser tab in the vault:
* The application intercepts the gesture and confirms whether you wish to leave if any field is actively being edited.
* Background app switching or phone lock triggers an immediate `pagehide` flush, saving in-flight keystrokes to IndexedDB or the server before the browser pauses.

---

## 4. ICEDIG Missing Data Standards

When transcribing damaged, faded, or incomplete historical labels, use standard ICEDIG markers rather than leaving ambiguous blank fields:

| Marker String | Standard Meaning |
| :--- | :--- |
| `unknown:missing` | Information was omitted on the physical label. |
| `unknown:indecipherable` | Text is physically illegible, damaged, or torn. |
| `unknown:undigitized` | Information was skipped during initial digitization. |
| `withheld` | Data withheld due to conservation or legal sensitivity. |

> [!TIP]
> **In-App Cheat Sheet**: Tap the **⚙ Settings** icon in the mobile header anytime to view the ICEDIG quick-reference table directly on your phone.

---

## 5. Ending the Session & Auto-Save Options

### Desktop Auto-Save Preference
By default, all edits synced from your mobile phone are held securely in workstation memory (RAM). When you stop the server, Arbor provides two safe persistence paths:

1. **Prompt to Save (Default — `Auto-save: OFF`)**:
   * When you click **🔴 End Mobile Session** or close the launch dialog with unsaved edits, Arbor prompts you:
     > *"Mobile session ended with unsaved changes in memory. Save the workbook to disk now?"*
   * Clicking **Yes** automatically executes a background asynchronous save (`save_session`), preventing accidental loss if you step away or close Arbor.
2. **Silent Auto-Save (`Auto-save: ON`)**:
   * Automatically persists in-memory edits to disk the moment the server is stopped, without prompting.
   * **Quick Toggle**: You can click the `[ ⏸️ Auto-save on stop: OFF ]` / `[ 💾 Auto-save on stop: ON ]` pill directly in the Mobile Companion launch window at any time to switch modes, or configure it permanently in Desktop **Settings ▾ General ▾ Autosave & Storage**.

