# Arbor Herbarium Curation Suite — Trainee Work Manual
**A Friendly, Plain-Language Guide for Museum Assistants, Interns, and Work-Placement Trainees**

---

## 📖 Welcome to Your New Curation Assistant

Welcome to the team! As a museum assistant, work-placement intern, or collection volunteer, your role is the heart of the herbarium: you help preserve biological history by making sure our physical plant specimens match our digital records.

This manual was written for you. You do not need any computer science experience or advanced botanical background to use Arbor. Arbor is designed to make auditing physical boxes, paper sheets, and handwritten labels fast, accurate, and comfortable.

---

## 📑 Table of Contents
1. [Chapter 1: Welcome to Arbor & Your Daily Purpose](#chapter-1-welcome-to-arbor--your-daily-purpose)
2. [Chapter 2: The Three Main Screen Areas](#chapter-2-the-three-main-screen-areas)
3. [Chapter 3: The 5-Step Daily Curation Routine](#chapter-3-the-5-step-daily-curation-routine)
4. [Chapter 4: What the Status Badges Mean](#chapter-4-what-the-status-badges-mean)
5. [Chapter 5: Looking at the Excel Spreadsheet (The Tab-by-Tab Guide)](#chapter-5-looking-at-the-excel-spreadsheet-the-tab-by-tab-guide)
6. [Chapter 6: Helpful Keyboard Shortcuts (Rest Your Mouse Hand)](#chapter-6-helpful-keyboard-shortcuts-rest-your-mouse-hand)
7. [Chapter 7: Changing the View (If Text Is Too Small or Crowded)](#chapter-7-changing-the-view-if-text-is-too-small-or-crowded)
8. [Chapter 8: Working with Specimen Photos](#chapter-8-working-with-specimen-photos)
9. [Chapter 9: Using the Mobile Companion in Collection Aisles](#chapter-9-using-the-mobile-companion-in-collection-aisles)
10. [Chapter 10: "Don't Panic!" Troubleshooting Guide](#chapter-10-dont-panic-troubleshooting-guide)

---

## Chapter 1: Welcome to Arbor & Your Daily Purpose

### The Digital Filing Cabinet
Think of Arbor as a visual assistant sitting on top of an ordinary Microsoft Excel workbook (`.xlsx`). 

Instead of forcing you to scroll through hundreds of wide columns and thousands of tiny cells in Excel, Arbor presents each physical specimen as a clean, easy-to-read card. When you make a change or click a button in Arbor, it quietly updates the real Excel spreadsheet on your computer. Nothing is hidden, and there are no complicated database servers running in the background.

### What Your Job Involves
During your shift, you will typically work through a batch of physical plant folders or high-resolution photos. Your daily goal is simple:
1. **Check the plant label**: Compare the typed text on the screen with the physical label on the paper sheet or photograph.
2. **Verify where it lives**: Confirm that the physical cabinet number and shelf number match the museum records.
3. **Flag mistakes**: If a name is misspelled, a label is illegible, or a box is misplaced, check the appropriate problem box.
4. **Mark it done**: Click **Mark Reviewed** (or press `Ctrl+Enter`) to give the specimen a green checkmark and move to the next sheet.

> **In the Excel Spreadsheet**: When you open your collection file in Arbor, Arbor reads the `Registration` and `Observation` sheets. Everything you see on screen reflects the exact data stored in those spreadsheet rows.

---

## Chapter 2: The Three Main Screen Areas

When you open Arbor, the workspace is arranged into three clean vertical columns designed to keep your eyes moving naturally from left to right:

```
┌─────────────────────────┬─────────────────────────┬─────────────────────────┐
│     1. LEFT COLUMN      │    2. CENTER COLUMN     │     3. RIGHT COLUMN     │
│   "Your Task List"      │  "Label Info & Storage" │    "Specimen Photos"    │
│                         │                         │                         │
│ • Specimen Directory    │ • Plant name & Family   │ • High-resolution scans │
│ • Accession ID cards    │ • Collector & Date      │ • Zoom, pan, and rotate │
│ • Status badges (Green, │ • Cabinet & Shelf locs  │ • Multi-photo gallery   │
│   Red, Amber, Gray)     │ • Problem checkboxes    │                         │
│ • Fast search bar       │ • [✓ MARK AS REVIEWED]  │                         │
└─────────────────────────┴─────────────────────────┴─────────────────────────┘
```

### 1. The Left Column: "Your Task List" (Specimen Directory)
* **What it is**: A vertical scroll of specimen cards representing every plant in your collection.
* **Top Search Bar**: Press `Ctrl+F` and start typing any ID number (e.g. `1042`) or plant name to jump straight to that card.
* **Card Information**: Each card displays the Specimen ID in bold, the scientific plant name, and a single colored status badge showing whether the plant is verified or needs attention.
* **Hiding the Sidebar**: If you need more room on a small laptop screen, press `Ctrl+O` or `F6` to smoothly collapse or expand this list.

### 2. The Center Column: "The Label Information & Storage Location"
* **Registration Form**: Displays the plant's scientific name (Genus, Species, Author), Family, Collector, Collection Date, and Collection Place.
* **Storage Location**: Shows where the plant physically lives in the herbarium (Building, Floor, Cabinet, Shelf, and Box Type).
* **Problem Checkboxes**: A set of checkboxes (e.g. *Genus Problem*, *Label Problem*, *Box Mismatch*) used to report issues.
* **The Big Green Button**: The prominent **✓ MARK AS REVIEWED** button at the top of this panel stamps your verification into the record.

### 3. The Right Column: "Specimen Photos"
* **High-Resolution Viewer**: Displays museum scans and photographs of the active specimen.
* **Image Toolbar**: Rotate upside-down sheets (`Alt+R`), zoom in to inspect faint pencil handwriting (`Ctrl++` / `Ctrl+-`), or reset the view (`Ctrl+0`).
* **Multi-Photo Dots**: If a specimen has multiple photos, click the thumbnail dots or press `Shift+Left` / `Shift+Right` to flip between them.

---

## Chapter 3: The 5-Step Daily Curation Routine

To help you work smoothly without mental fatigue, follow this 5-step rhythm for every specimen:

```
┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ 1. SELECT│ ──> │2. INSPECT│ ──> │ 3. FLAG IF   │ ──> │ 4. MARK DONE │ ──> │ 5. SAVE  │
│          │     │          │     │    WRONG     │     │   IF CORRECT │     │   WORK   │
│ Down Key │     │ Label vs │     │ Spacebar on  │     │ Ctrl + Enter │     │ Ctrl + S │
│ or Click │     │ Screen   │     │ Problem Box  │     │ (Turns Green)│     │ Hourly   │
└──────────┘     └──────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### Step 1: Select Your Specimen
Click any card in the left list, or simply press the `Down Arrow` key on your keyboard to advance down the list one card at a time.

### Step 2: Inspect the Physical Sheet or Photo
Look at the photograph on the right and compare it with the typed fields in the center:
* Is the botanical name spelled correctly?
* Does the collector's name and collection year match the label?
* Does the physical storage box on your desk match the Cabinet and Shelf listed on screen?

### Step 3: Flag if Anything Is Wrong
If something is misspelled, torn, illegible, or in the wrong box, do not worry! Simply click into the **Problems** section and check the relevant checkbox (or press `Space` while focused on the checkbox). The text box will gently highlight in yellow so anyone reviewing the file knows there is an open question.
> **In the Excel Spreadsheet**: Checking a problem box writes `TRUE` into that specific column on the `Observation` sheet (for example, `Species_Problem = TRUE` or `Box_Label_Problem = TRUE`).

### Step 4: Mark Done if Correct
If all details match reality, click the big green **✓ MARK AS REVIEWED** button at the top of the form, or press `Ctrl + Enter`.
* The card in the left list immediately receives a clean green `[ REV ]` badge.
* Arbor automatically advances your screen to the very next specimen so you can keep your hands on the keyboard.
> **In the Excel Spreadsheet**: This writes `TRUE` into the `Reviewed` column on the `Observation` sheet for that specimen's `ObjectID`, timestamps your review time into `ReviewedAt`, and records your username in the `Log` sheet.

### Step 5: Save Your Work
Before heading to lunch, taking a break, or ending your shift, press `Ctrl + S` to save all your work.
> **In the Excel Spreadsheet**: Arbor writes all pending updates directly to the `.xlsx` file on your hard drive.

---

## Chapter 4: What the Status Badges Mean

To prevent visual confusion, Arbor uses a strict **single-badge discipline**: each specimen card displays at most **one** high-contrast priority badge telling you the single most important action required.

| Status Badge | Badge Color | What It Means in Plain Language | Action Needed | What It Means in Excel (`Observation` Sheet) |
| :--- | :--- | :--- | :--- | :--- |
| `[ REV ]` | **Herb Green**<br>(`#3a7d44`) | **Reviewed & Verified**<br>The specimen has been thoroughly checked and confirmed correct. | None! It's finished. Move to the next sheet. | `Reviewed = TRUE`<br>(All problem columns are `FALSE` or blank) |
| `[ REV+ERR ]` | **Ochre Gold**<br>(`#F57C00`) | **Reviewed with Known Issue**<br>You checked the sheet, but an unresolvable issue was intentionally noted. | None. Supervisor knows an issue exists on this verified sheet. | `Reviewed = TRUE`<br>AND at least one problem flag is `TRUE` |
| `[ TAX ]` | **Coral Red**<br>(`#c93a40`) | **Plant Name Issue**<br>The scientific name, genus, species, or author citation is misspelled or uncertain. | Check the label spelling or click GBIF Verify in the toolbar. | `Genus_Problem = TRUE`, `Species_Problem = TRUE`, or `Family_Problem = TRUE` |
| `[ PROV ]` | **Warm Amber**<br>(`#d9a036`) | **Origin / Collector Issue**<br>The collector name, collection date, or locality is missing or questioned. | Check the label handwriting or insert a missing data marker (`?m`). | `Collector_Problem = TRUE`, `Collection_Date_Problem = TRUE`, etc. |
| `[ BOX ]` | **Earth Brown**<br>(`#795548`) | **Storage Box Issue**<br>The physical box label, folder housing, or storage location is mismatched. | Verify which cabinet/shelf the box sits on and update the location. | `Box_Label_Problem = TRUE` |
| `[ IMG ]` | **Ocean Blue**<br>(`#0284c7`) | **Photo Issue**<br>The photograph is missing, unlinked, blurry, or belongs to another plant. | Confirm the photo link or notify your supervisor to rescan. | `Images_Problem = TRUE` or `Images_Missing = TRUE` |
| `[ CFCT ]` | **Slate Blue**<br>(`#4a7b9d`) | **Ledger Conflict**<br>An old historical handwritten ledger book disagrees with modern data. | Press `Ctrl+H` to open the Conflict Resolver and compare sources. | Conflict detected against loaded Historical Books |
| `[ ERR ]` | **Coral Red**<br>(`#c93a40`) | **General Error**<br>An uncategorized issue or general quality note was flagged. | Read the Notes field to see what previous curators wrote. | `Other_problem = TRUE` |
| `[ UNREV ]` | **Cool Gray**<br>(`#757d77`) | **Pending Review**<br>A fresh or untouched record waiting for your inspection. | Inspect the specimen, verify fields, and click Mark Reviewed. | `Reviewed = FALSE` (or empty) |

---

## Chapter 5: Looking at the Excel Spreadsheet (The Tab-by-Tab Guide)

One of Arbor's greatest strengths is transparency: it stores everything in standard Microsoft Excel files (`.xlsx`). You can open the spreadsheet in Excel at any time to see your work.

### The Golden Rule: Close Excel Before Opening Arbor
> ⚠️ **Important Safety Rule**: Windows locks Excel files when Microsoft Excel has them open. Always **close Microsoft Excel** before launching or saving in Arbor. If you forget, Arbor will pop up a gentle reminder saying the file is in use.

### The Golden Key: `ObjectID`
In every sheet inside the Excel file, the very first column is **`ObjectID`** (e.g. `1001`, `1042`, or `O-V-0042`). This accession number is the golden key that links all the sheets together.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ARBOR EXCEL WORKBOOK STRUCTURE                        │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ 1. Registration │ 2. Observation  │ 3. Photo        │ 4. Unvalidated_source │
│ (Catalog Data)  │ (Your Curation) │ (Image Links)   │ (Illegible Notes)     │
│                 │                 │                 │                       │
│ • ObjectID      │ • ObjectID      │ • ObjectID      │ • ObjectID            │
│ • Genus         │ • Reviewed      │ • Online photo1 │ • Field_Name          │
│ • Species       │ • ReviewedAt    │ • Online photo2 │ • Unvalidated_Comment │
│ • Collector     │ • 11 Problems   │ • Local path    │                       │
│ • Date & Place  │ • Cabinet/Shelf │                 │                       │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

### The 4 Core Sheets Explained:

#### 1. `Registration` (The Master Specimen Catalog)
This sheet contains the permanent historical record of the specimen:
* **`ObjectID`**: The accession number.
* **`Genus` & `Species`**: The scientific botanical name.
* **`Family` & `Author`**: The higher classification and person who named the plant.
* **`Collector` & `Collection Date`**: Who found the plant in the wild and when.
* **`Collection Place`**: The geographic locality where the plant was collected.
* **`UID`**: An 8-character safety fingerprint (e.g. `7921ac45`) created automatically by Arbor to prevent accidental row mix-ups.

#### 2. `Observation` (Your Curation Work & Storage Location)
This is where your daily work in Arbor is saved!
* **`Reviewed`**: Displays `TRUE` if you marked the specimen as reviewed, or `FALSE` if it is still pending.
* **`ReviewedAt`**: An automatic timestamp recording the exact date and time the specimen was verified.
* **The 11 Problem Columns**: Columns like `Genus_Problem`, `Species_Problem`, `Collector_Problem`, and `Box_Label_Problem` store `TRUE` if flagged, or `FALSE` if clear.
* **Storage Coordinates**: `Building`, `Floor`, `Cabinet`, `Shelf`, and `Stored as` record where the plant physically lives in the museum stacks.

#### 3. `Photo` (Attached Photos & Scans)
Contains the file paths and web links for photos:
* Links high-resolution image files on your local drive or online museum repositories to the matching `ObjectID`.

#### 4. `Unvalidated_source` (Notes for Illegible Handwriting)
A scratchpad sheet for messy labels:
* If a 19th-century label is torn or unreadable, this sheet stores draft comments (e.g. *"Label partially eaten by insects; looks like 'Quercus' but uncertain"*) without corrupting the clean scientific name fields.

#### 5. `Log` (The Audit Trail)
Whenever an edit is made, Arbor quietly appends a row here recording the date, time, user, and what value changed (e.g. *"Changed Cabinet from 4 to 5"*). This protects you by providing a full history of all updates.

---

## Chapter 6: Helpful Keyboard Shortcuts (Rest Your Mouse Hand)

Clicking a mouse thousands of times a day can strain your wrist and fingers. Arbor is built to let you complete your entire curation shift using only your keyboard:

### Primary Daily Work Keys (The "Top 5")

| Shortcut Key | What It Does | Why You Will Love It |
| :--- | :--- | :--- |
| **`[Ctrl] + [Enter]`** | **Mark Reviewed & Advance** | Signs off on the active specimen and jumps immediately to the next card. |
| **`[Space]`** | **Toggle Problem Checkbox** | Checks or un-checks whichever problem box you are currently focused on. |
| **`[Down]` / `[Up]`** | **Next / Previous Specimen** | Moves down or up your specimen list card by card. |
| **`[Ctrl] + [Down]` / `[Up]`** | **Jump to Next Problem Card** | Skips clean records and jumps straight to cards with open problem flags. |
| **`[Ctrl] + [S]`** | **Save Active Session** | Writes all changes safely to the Excel workbook on your hard drive. |

### Searching & Finding Records
* **`[Ctrl] + [K]`**: Opens the **Universal Command Palette**. Type any specimen number (`#1042`), plant name, or command (e.g. `save`, `dark mode`, `export`) to jump immediately.
* **`[Ctrl] + [F]`**: Jumps your cursor directly into the search bar at the top of the Specimen Directory.
* **`[Ctrl] + [G]`**: Opens the **Filter Menu** to view only unreviewed specimens, only plants with photos, or only problem records.

### Typing & Editing Data
* **`[Ctrl] + [E]`** or **`[Ctrl] + [I]`**: Jumps your cursor into the first Registration form field so you can start typing immediately.
* **`[Ctrl] + [L]`** or **`[F4]`**: Jumps your cursor into the first Storage Location field (Cabinet / Shelf).
* **`[Ctrl] + [Z]`** / **`[Ctrl] + [Y]`**: Undo or redo any text edit.
* **`[Ctrl] + [H]`**: Opens the **Conflict Resolver** when historical books disagree with your sheet.

### Standard Museum Codes for Missing Information (ICEDIG)
When an old label has missing or damaged text, do not leave the field blank. Use these standard museum shortcuts while typing in any text box:

| Shortcut | Quick Code | What It Types | When to Use It |
| :--- | :--- | :--- | :--- |
| **`[Ctrl] + [Shift] + [M]`** | `?m` | `unknown:missing` | Information was omitted on the physical label (e.g. no date written). |
| **`[Ctrl] + [Shift] + [I]`** | `?i` | `unknown:indecipherable`| Text is faded, torn, water-damaged, or completely illegible. |
| **`[Ctrl] + [Shift] + [U]`** | `?u` | `unknown:undigitized` | Information was skipped during the initial digitization pass. |
| **`[Ctrl] + [Shift] + [W]`** | `?w` | `withheld` | Data is legally sensitive (e.g. exact GPS of an endangered orchid). |
| **`[Ctrl] + [Shift] + [Backspace]`**| *(None)* | *(Clears field)* | Erases the entire contents of the field cleanly. |

---

## Chapter 7: Changing the View (If Text Is Too Small or Crowded)

Everyone's eyes and monitors are different. If the text feels cramped on a small laptop or you want to see more cards at once on a desktop display, Arbor gives you **4 one-click layout profiles**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         4 DIRECTORY VIEW PROFILES                           │
├─────────────────┬─────────────────┬─────────────────┬───────────────────────┤
│ 1. Standard     │ 2. Compact      │ 3. Full Details │ 4. Minimalist         │
│ (78px height)   │ (64px height)   │ (92px height)   │ (Compact & Lean)      │
│                 │                 │                 │                       │
│ • Everyday view │ • Laptop dense  │ • Large text    │ • Pure ID & taxon     │
│ • Balanced info │ • 15+ cards     │ • Author names  │ • No badges / chips   │
│ • ID + name +   │ • Fast checking │ • Full storage  │ • Distraction-free    │
│   status badge  │   through boxes │   location line │   data transcription  │
└─────────────────┴─────────────────┴─────────────────┴───────────────────────┘
```

### How to Switch Profiles:
1. Press **`Ctrl + K`** and type `Card View`.
2. Select your preferred layout:
   * **`Card View: Standard (78px)`**: The default balanced view (~12 cards visible).
   * **`Card View: Compact (64px)`**: High-density view showing 15+ cards on screen at once.
   * **`Card View: Full Details (92px)`**: Expanded research view showing botanical authors (e.g. *L.*) and full Building/Floor/Cabinet/Shelf coordinates on every card.
   * **`Card View: Minimalist`**: Clean, bare view showing strictly the ID number and plant name without extra badges or chips.
3. You can also adjust profiles in **`Settings ⚙` $\rightarrow$ `Appearance` $\rightarrow$ `Directory Card Profiles`**, where an interactive live preview shows you how cards will look before you apply them.

### Toggling Workspace Panels
If you want to maximize screen space for inspecting photos or typing notes, use the function keys:
* **`[F6]`**: Toggle the Specimen Directory (left column) on or off.
* **`[F7]`**: Toggle the Registration Form (center column) on or off.
* **`[F8]`**: Toggle the Specimen Photos Viewport (right column) on or off.

---

## Chapter 8: Working with Specimen Photos

High-resolution scans let you inspect plant hairs, seeds, and faded ink labels without touching fragile 100-year-old paper sheets:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPECIMEN IMAGE VIEWPORT CONTROLS                         │
├──────────────────────────┬──────────────────────────────────────────────────┤
│ Action                   │ How to Do It                                     │
├──────────────────────────┼──────────────────────────────────────────────────┤
│ Rotate 90° Clockwise     │ Press [Alt] + [R] or click ↻ in the toolbar       │
│ Zoom In / Zoom Out       │ Press [Ctrl] + [+] / [-], or roll your Mouse Wheel│
│ Reset Zoom to Full Page  │ Press [Ctrl] + [0] or click ↺ in the toolbar     │
│ Pan Across Large Photo   │ Click and drag with your left mouse button       │
│ Browse Multiple Photos   │ Press [Shift] + [Left] / [Right], or [Ctrl] + [B]│
│ Detached Full-Res Popout │ Double-click anywhere on the image canvas        │
└──────────────────────────┴──────────────────────────────────────────────────┘
```

### The Detached High-Resolution Viewer
For very difficult handwriting or tiny pressed leaves, **double-click** the image. 
* A detached window (`ZoomableImagePopup`) appears on top of your workspace.
* Use your mouse wheel to zoom up to 500% into the scan.
* Click and drag to pan across the label.
* Press `Escape` to close the popout and return to your form.

---

## Chapter 9: Using the Mobile Companion in Collection Aisles

When auditing physical specimens deep in the museum vault aisles, you do not need to carry a heavy laptop or balance a keyboard on your knees. Arbor includes a built-in **Mobile Companion** that works on any smartphone or tablet browser:

```
┌────────────────────────┐      Local Wi-Fi      ┌────────────────────────┐
│  DESKTOP WORKSTATION   │ ───────────────────>  │  PHONE / TABLET BROWSER│
│                        │    Secure PIN Code    │                        │
│ • Runs Arbor           │                       │ • Step through records │
│ • Shows QR Code & PIN  │                       │ • Update Cabinet/Shelf │
│ • Holds Excel workbook │                       │ • Attach camera photos │
└────────────────────────┘                       └────────────────────────┘
```

### How to Connect in 4 Easy Steps:
1. **Launch the Server**: In Arbor on your desktop computer, click the **`📱 MOBILE`** menu at the top, or press `Ctrl+K` and type `Mobile Companion`.
2. **Scan the Screen**: A window appears displaying a QR code, a web address, and a 4-digit security PIN.
3. **Open on Your Phone**: Scan the QR code with your phone camera, or type the address into your phone's browser (Safari, Chrome, or Firefox).
4. **Enter Your PIN**: Enter the 4-digit PIN shown on your desktop screen to start your session.

### What You Can Do on Your Phone:
* **Browse Specimens**: Swipe left and right or tap Previous/Next to step through cards in your active batch.
* **Update Cabinet & Shelf Numbers**: Use large, finger-friendly **`+`** and **`-`** buttons to adjust Cabinet and Shelf numbers while standing right in front of the physical furniture.
* **Attach Photos**: Take a photo of a label or folder directly with your phone camera to attach it to the specimen record.
* **Works Completely Offline**: If your museum vault has thick concrete walls with no Wi-Fi, the Mobile Companion continues working in offline mode. It securely holds your updates in phone memory and uploads them automatically the moment you walk back into Wi-Fi range.

### Ending Your Mobile Session:
When you return to your desk, click **🔴 End Mobile Session** on your computer. Arbor will check for any updates made on your phone and ask:
> *"Mobile session ended with unsaved changes in memory. Save the workbook to disk now?"*

Click **Yes**, and Arbor writes all your mobile edits straight into your Excel workbook!

---

## Chapter 10: "Don't Panic!" Troubleshooting Guide

If something unexpected happens, do not panic! Arbor is engineered with multiple safety nets to protect your work:

### 1. "What does the yellow dot mean?"
* **What you see**: A small amber dot (`● Unsaved`) appears next to the specimen ID number in the top bar.
* **What it means**: You have typed edits or changed a problem box, but have not yet saved to disk.
* **The fix**: Press **`Ctrl + S`** to save your changes. The yellow dot will disappear.

### 2. "I accidentally marked a specimen as reviewed!"
* **What happened**: You pressed `Ctrl + Enter` by mistake on a sheet that is not finished.
* **The fix**: Simply click the **✓ MARK AS REVIEWED** button again (or press `Ctrl + Enter` a second time). The checkmark will turn off, the green badge will revert to cool gray `[ UNREV ]`, and the record is marked unreviewed again.

### 3. "The computer says: 'File is locked by another program'"
* **What happened**: Microsoft Excel is currently open on your computer with the same `.xlsx` file.
* **The fix**: 
  1. Switch to Microsoft Excel and close the workbook window.
  2. Return to Arbor and press **`Ctrl + S`**. Arbor will now save cleanly.

### 4. "I made a big mistake or deleted something by accident!"
* **Don't panic!** Arbor automatically creates timestamped safety backup copies in a hidden `.arbor_backups/` folder inside your project directory before every major operation.
* **The fix**: Notify your supervisor. They can restore your workbook to the exact state it was in 10 minutes ago with zero data loss.

### 5. "A text box is glowing with a yellow background"
* **What it means**: This is a helpful visual reminder! A problem checkbox is currently active for that specific field (for example, if `Species_Problem` is checked, the Species box glows yellow).
* **The fix**: Double-check the text on the physical label. If you resolve the issue and uncheck the problem box, the yellow highlight disappears.

### 6. "The photograph is missing or showing a black box"
* **The fix**:
  1. Press **`F8`** twice to toggle the photo viewport off and on again.
  2. If the photo was stored on an external USB hard drive, check that the drive cable is securely plugged into your computer.
  3. If the photo is still missing, check the **Images_Problem** checkbox to alert the digitization team.

---

*End of Trainee Work Manual. Happy Curating!*
