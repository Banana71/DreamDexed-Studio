# Welcome to DreamDexed-Studio!

Hi, I'm Peter (perhaps better known to many in the community as **Banana71** from *Soundplantage*). As a sound designer, I created the factory performances for both miniDexed and DreamDexed, among other projects.

Anyone who works extensively with FM synthesizers and hardware emulations quickly realizes that managing data, converting SysEx files, and handling backups via FTP can become quite tedious over time. That is exactly why DreamDexed-Studio was born. What originally started as a collection of small helper scripts to make my own daily work easier has now grown into a fully fledged desktop application. 

This tool is designed to make your workflow with miniDexed and DreamDexed as simple and efficient as possible.

---

## Chapter 1: Installation & Windows Security

The installation of DreamDexed-Studio is incredibly straightforward, as the program runs directly as a **"portable" app** and does not require a permanent installation on your system.

1. **Download:** Go to the GitHub repository `Banana71/DreamDexed-Studio` and navigate to the **Releases** section. Download the latest ZIP file (e.g., `DreamDexed-Studio v0.2.7.zip`).
2. **Extract:** Unzip the contents of the ZIP file to a location of your choice (e.g., your user folder or a dedicated applications directory).
3. **First Launch:** Open the extracted folder and launch **`DreamDexed-Studio.exe`**.

### ⚠️ Important Note on Windows Security Warnings (False Positives)
Since DreamDexed-Studio is an open-source project and is not (yet) digitally signed, the AI engines of Windows SmartScreen and Windows Defender will sound an alarm upon the first launch. **The program is absolutely virus-free.** Follow these steps to allow the application to run:

* **SmartScreen Window ("Windows protected your PC"):** Click on the **"More info"** link within the blue warning text. Only after doing this will a new button appear in the bottom right corner. Click **"Run anyway"**.
* **The Quarantine Case (If the EXE suddenly disappears):** If Windows Defender moves the file to quarantine with a message like `Win32/Wacapew.A!ml`, open your **Windows Security** -> **Virus & threat protection** -> **Protection history**. Click on the blocked entry, select **"Restore"** under the *Actions* menu, and the file will be instantly ready for use again.

---

## Chapter 3: Initial Setup (One-Time)

Once the program is running, you will need to configure the basic settings for your hardware and file paths. This only needs to be done once.

### Step 1: Configure the Connection to miniDexed / DreamDexed
1. Click the gear icon **"Edit Profiles"** in the top left corner.
2. **Profile Name:** Give your profile a custom name (e.g., `RD-300`, `DIY-MiniDexed`, or `DT-DX`).
3. **IP Address:** Enter the IP address of your Raspberry Pi (e.g., `192.168.178.20`).
   * *Tip for miniDexed:* The IP address is briefly displayed on the hardware screen during boot-up.
   * *Tip for DreamDexed:* Navigate to the "Status" item in the hardware menu to see the "Net IP".
   * *Alternative:* Check your local router's web interface to find the IP.
4. **User & Password:** These values are hardcoded into the system. Simply leave them at their defaults: **`admin` / `admin`**.
5. Click the **"Save/New"** button to save the profile.

### Step 2: Test the Connection
1. Ensure your miniDexed/DreamDexed is powered on and connected to the same network.
2. Click **"FTP Test"** in the app.
3. If successful, the app will read the first few lines of your `minidexed.ini` directly from the SD card. The log window will display the following:

<!-- Start of log template -->
--- FTP Test: RD-300 (192.168.178.20) ---
Connected!
Current directory on RD-300: /SD
Reading first 7 lines from minidexed.ini...
...
Test finished.
<!-- End of log template -->

4. Now, click **"Reconnect"** in the bottom right corner. The complete contents of your SD card will now be displayed on the right half of the program window (inside the Performance Manager).

### Step 3: Configure Paths, GUI & MIDI
Click **"Expand"** in the *"Path, Configuration & Master Volume"* section to reveal the advanced options.

* **Dexed Path (Path to your Cartridges):**
  1. Open the original **Dexed** desktop application on your PC, click the **CART** button, and right-click any folder (e.g., *SynprezFM*). Select **"Open Location"**.
  2. Inside this opened Windows directory, create a new folder (e.g., `Soundplantage`). This is where all your future imported patches will land.
  3. Copy the full path of this new folder (Right-click -> *Copy as path* or `Ctrl + Shift + C`).
  4. Paste this path into DreamDexed-Studio under **"Dexed Path"** and remove any quotation marks at the beginning and end (Example: `C:\Users\peter\AppData\Roaming\DigitalSuburban\Dexed\Cartridges\Soundplantage`).
* **GUI Scale:** If the app appears too large or too small on your monitor, you can adjust this value freely between **75% and 300%** (the default is 100% for a Full-HD resolution). Changes will take effect after restarting the app.
* **MIDI In / Out:**
  * Under **MIDI In**, select your connected MIDI controller/keyboard.
  * Under **MIDI Out**, select the interface leading to your miniDexed/DreamDexed (or the Pi itself if it is running in USB Gadget Mode).

#### MIDI Button Navigation (Optional)
* **What is this?** If you don't have a touchscreen or physical rotary encoders installed on your Raspberry Pi, you can configure miniDexed/DreamDexed to respond to simple button commands to navigate through the menus.
* If you have activated this feature in the `minidexed.ini` on your Pi, the **`PerformanceSelectChannel`** will be displayed here (the default is usually channel 10). You can click **"MIDI Button Config"** to map keys on your PC keyboard to simulate these hardware buttons. This is perfect for comfortably controlling the device right from your desk.

### Step 4: Save Settings and Final Test
1. Click the **"Save Config"** button.
2. Click **"Collapse ▲"** in the top left corner to cleanly hide the settings view.
3. If necessary, reboot your device using the **"DreamDexed reboot"** button in the very top row of the app.
4. **The MIDI Test:** Play a few keys on your connected keyboard. The integrated Chord Scanner in the app should immediately display the chords you are playing. If this works, your basic configuration is complete!
5. **The Navigation Test (Only if configured):** If you set up the MIDI Button Navigation in Step 3, press the corresponding keys on your PC keyboard. You should instantly see the device navigate through the menus on your miniDexed/DreamDexed display.

Once the MIDI test (and optionally the navigation test) is successful, your initial setup is complete and DreamDexed-Studio is fully ready for action!

### ⚠️ Important Note: Data Security & Backups
A brief word regarding the safety of your sounds:
During the development of DreamDexed-Studio, I placed an immense focus on ensuring your data remains safe. The program automatically creates background backups in many places before files are modified or overwritten.

Despite all due care, the golden rule of software applies: *No pipeline is 100% bug-free.* Since this tool interacts deeply with the file structure of your miniDexed/DreamDexed, **please regularly make manual backups of your most important performances and SD card contents to your PC.**

Please understand that DreamDexed-Studio is a pure open-source utility tool. I assume no responsibility or liability for lost sounds, overwritten performance lists, or corrupted SD card structures. Use at your own risk.

*In short: Backup your data—it makes for a much better night's sleep!*

---

## Chapter 4: The Right Window Half – The Performance Manager

The **Performance Manager** on the right side of the Studio is dedicated to managing, analyzing, and restructuring your performances. The interface is designed as a classic two-column file explorer:
* **Left Column (Source):** This is where you access your local backups, repositories, or import folders on your PC.
* **Right Column (Destination):** This is your active workspace, reflecting the current folder and bank structure on your device.

For quick orientation, the bottom two lines of the right window half offer a brief description of the explorer functions:
* **Left Side Controls (Source):** `Delete`, `Copy`, and `Drag & Drop`.
* **Right Side Controls (Destination):** `Del` (Delete), `Edit`, `Banks`, `Reindex`, and `Right Double Click` to quickly open or activate.

> **Important Workflow Note:** All file operations performed within the Performance Manager happen **directly live on the Raspberry Pi**. No separate save command is required.

### 4.1 Practical Example: Creating and Sorting a New "Favorite" Bank
To organize your sounds, you can create a dedicated bank for your favorite performances (e.g., "Favorite") and copy your preferred sounds into it.

* **Step 1: Activate the Destination Side**
  Click once anywhere inside the right explorer half (**Destination**) to bring this area into focus.
* **Step 2: Create a New Bank via [F4]**
  Press the **[F4]** key. The Studio will automatically generate a new bank and assign the next available numerical index by default (e.g., `002_Favorite`).
  * *Note on the Index:* You can modify the three-digit index prefix at any time to control the order of the banks on your synthesizer's display.
  * > **💡 Pro-Tip (Selection Focus):** To create a new bank, no existing bank or file must be selected. If a bank is currently highlighted and blocking the `[F4]` command, you can instantly clear the selection focus by pressing the **[Esc]** key or by **clicking into the empty space** below the file list on the right side. Once the highlight disappears, press `[F4]` to generate your new bank.
* **Step 3: Enter the New Bank**
  Open the newly created, empty bank by **double-clicking** its name.
* **Step 4: Copy Performances**
  Navigate to the performance folder in the left column (**Source**) and open the bank containing the sound you want to copy. Select your favorite performance. You now have two ways to copy it to the right side:
  1. **Via Keyboard:** Press the **[F3]** key to copy the selected performance directly to the right column.
  2. **Via Mouse:** Click and hold the performance with the left mouse button and drag it over to the right column using **Drag & Drop**.
* **Step 5: Adjust the Sorting (Vertical Dragging)**
  Within your new bank, you can organize the order of the performances completely to your liking. Click a performance and drag it **vertically up or down** while holding the mouse button. The Studio will update the visual order instantly.
* **Step 6: Clean Up the Bank via [F5] (Reindex)**
  Once you are done sorting, press the **[F5]** key (or use the **"Reindex"** button in the footer). This feature is useful for two reasons:
  1. **Fixing the Sorting:** The Studio renames the files on the Raspberry Pi so that their three-digit numerical prefixes perfectly match your new visual arrangement.
  2. **Cleaning up the Numbering:** If you previously deleted individual performances from the bank, gaps will appear in the numerical prefixes (e.g., deleting sound `002` leaves a gap between `001` and `003`). The Reindex function closes these gaps and sequentially renumbers the bank seamlessly (e.g., changing `003` back to `002`).
  * > **Note on the Hardware:** The miniDexed/DreamDexed hardware itself does not care about gaps in the index. Skipping a number will not cause "dead sounds"; the device simply skips to the next available file when switching patches. Reindexing is primarily for visual neatness on your display and within the explorer.

### 4.2 Important for Hardware: The Reboot Requirement
For your miniDexed or DreamDexed to actually recognize and display the newly created bank and sorted sounds, you must restart the unit. To do this, press and hold the **"DreamDexed reboot"** button in the Studio for **2 seconds**.

**Background on how miniDexed / DreamDexed operates:**
This hardware behavior is hardcoded into the core of the synthesizer and cannot be altered by DreamDexed-Studio:
* **Banks** are read by the device **exclusively during the system boot process**. If you create a new bank (a new folder), it remains invisible to the hardware until the next reboot.
* **Performances within the banks**, however, are loaded dynamically the exact moment you **switch into that specific bank** on the hardware.

### 4.3 The Integrated Performance Editor (Editing & Renaming)
Any performance selected in the right column (**Destination**) can be opened and edited directly within the Studio, without needing to touch a single line of text code.

* **Opening the Editor:** Select the desired performance on the right side and open it either via a **double-click** or by pressing the **[F2]** key. This opens the *Performance Editor* window.
* **Adjusting Parameters:** Within this window, you can directly modify the most critical settings of your performance:
  * The global **Performance Name** (as seen on the device display).
  * The individual **Voice Names** (patch designations) of the loaded sounds.
  * Hardware assignments such as MIDI Channels (**CH**), Volume (**VOL**), Panorama (**PAN**), and much more.
* **Saving & Loading:** After clicking Save, the Studio writes the changes directly to the file on the Pi's SD card. As soon as you reload the performance on your miniDexed or DreamDexed, your changes will be active instantly.

### 4.4 The Mixer Overview (Visual Signal Flow Analysis)
Directly inside the opened editor window, you will find a separate tab named **"Mixer"**.

* **Purpose of the Mixer:** This visual mixing console is **read-only**. The values cannot be edited here; instead, it serves as a perfect, quick overview of your sound's entire routing.
* **What you see at a glance:**
  * You can immediately trace the signal path and utilization of all 8 Tone Generators (TGs).
  * **Effects & Highlights:** Active modules such as the **EQ** (Equalizer) or **Comp** (Compressor) are highlighted with a distinct color (dark green background), allowing you to instantly see where the signal is being processed.
* > **Hardware Note on miniDexed vs. DreamDexed:** 
  > * On a standard **miniDexed**, the effects section is naturally leaner: The overview will only show you the global *PlateReverb* and the *Compressor* (which functions strictly as a limiter on the miniDexed).
  > * Only when paired with a **DreamDexed** does the Mixer overview unfold its full depth, displaying all advanced, globally utilized master and insert effects.

### 4.5 The Sound Designer Highlight: "set Temp.syx"
If you realize while editing a performance that the FM sounds require deeper, fundamental sound design adjustments, the most powerful tool of the Studio comes into play:

* **The "set Temp.syx" Function:** This button instantly extracts the exact DX7 voice data (envelopes, frequencies, algorithms) of all utilized Tone Generators (TGs) from the currently active performance.
* **Automatic Bank Generation:** Instead of copying these voices individually, the Studio compiles them into a fully fledged **DX7 Voice Bank (containing up to 8 voices)**. This bank is exported as a temporary `.syx` file directly into your defined *Dexed Path*.
* **The Real-Time Workflow:**
  1. Open the original **Dexed** desktop software on your PC and load this freshly generated bank.
  2. Select the patch you want to edit and tweak it visually using all of Dexed's sliders and operator graphics.
  3. **The Magic:** If your Dexed editor on the PC is configured correctly (with its MIDI Out routed to the Pi), your parameter tweaks in Dexed will arrive **at the miniDexed/DreamDexed in real time**. You will hear every single adjustment instantly on the hardware.
* This allows any performance to be handed over to Dexed incredibly fast and edited directly at the core sound level.

### 4.6 Exporting DX7 Voice Sheets
For documentation or sharing your sounds without relying on binary SysEx files, the Studio includes a specialized data sheet generator (`perf2sheet.py`).

* **Exporting from the Editor:** Click the **Data Sheet icon** directly inside the *Performance Editor*. The Studio extracts the cryptic hex values of the selected voice and translates them into a fully human-readable text document.
* **Storage Location:** The generated sheets are automatically saved in the `Base/VoiceSheets` directory.
* **Perfect for Forums & Reddit:** Since platforms like Reddit or traditional music forums often block binary file attachments (`.syx` or `.ini`), a Voice Sheet is the ideal alternative. You can simply copy the formatted text and paste it into your post to share the exact structure of your patch (envelopes, rates, operator frequencies from OP1 to OP6) with the community—plus, it looks highly professional!
* **Direct Viewing in Studio:** You don't need to open your operating system's file manager. The created Voice Sheets can be selected, opened, and viewed directly within the Studio interface via the left column (**Source / PC (local)**).

---

## Chapter 5: The Integrated Chord Scanner (Chord Recognition)

In addition to managing performances, DreamDexed-Studio features a highly useful live tool: an integrated Chord Scanner.

* **Purpose:** If you have a MIDI keyboard connected to your PC, the Studio analyzes your live playing in the background, detects the chords, and displays the chord name directly within the GUI. This is incredibly practical for keeping track of harmonic structures during sound design sessions or while testing performances.
* **UI Placement:** The chord display is prominently placed in the header area, directly above the log window. This ensures that the main area remains clear for text logs while allowing you to monitor status updates just to the left of it.
* **Setup & Configuration:**
  1. Open the configuration area by clicking the **"Expand ▼"** button.
  2. Under **"MIDI In"**, you will find a dropdown menu that automatically lists all MIDI input devices available on your PC.
  3. Select your keyboard or MIDI interface. Once selected, the scanner starts automatically in the background.
  4. If you do not wish to use this feature, simply set the menu to **"No MIDI"**—this completely deactivates the scanner and frees up system resources.
* **Display Behavior:** To prevent visual clutter and distraction, the detected chord name will automatically fade out after 1.5 seconds once you stop playing.