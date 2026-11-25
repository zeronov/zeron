ZERON BOOST for Android (v0.6) - PS2 emulator booster, fully automatic

WHAT IT IS (two parts)
1) The ZERON BOOST app (APK): a small floating box that appears BY ITSELF over your PS2 emulator and shows MEASURED
   RAM, battery temperature, thermal state, battery saver, CPU clocks. After each play it tells you the real cause of lag.
   Tap "AUTO SET UP" once: it opens the permission screens for you, one after another.
2) The Termux tool: just type   zeron   and it does everything:
   links to your phone (first time only), backs up and tunes your emulator settings, turns battery saver off,
   opens the emulator, WATCHES real frame speed while you play (no prompts), and LEARNS:
     - game lagged  -> lighter settings automatically next launch
     - two smooth games -> tries cleaner graphics next time (never returns to a level that lagged)
     - lag caused by heat -> tells you to cool the phone instead of ruining your settings
   Levels: Balanced > Performance > Maximum > Maximum + lighter EE. It only LOWERS heavy settings.

NEW IN v0.6 (made for MediaTek phones like the Tecno Spark 40 / Helio G81, Mali-G52)
- The app now recognizes your chip and gives an honest reality check in "Best emulator settings for my phone":
  Mali GPUs run PS2 slower than Snapdragon; light 2D/simple 3D games are most likely to reach full speed; heavy 3D games
  often will not. No app can change the chip.
- Recommends the newest ARMSX2 emulator (v2.9+): its Automatic Performance Tuning (tries resolution, blending, texture
  download mode, GS thread and CPU clock per game and keeps only what helps) and its Mali driver option (MaliSX2; the
  makers list Mali-G57 and newer, so a G52 may not load it - the emulator falls back by itself).
- Termux tool levels now follow the emulator makers' advice: "Disable Readbacks" at Performance and up; levels 3-4
  underclock the emulated CPU (EE cycle rate 60%/50%) with a mild/moderate cycle skip.

v0.5
- Renderer learning (Termux tool): when a game lags, 'zeron' first tries the OTHER renderer (Vulkan <-> OpenGL), measures
  it on your next game, keeps it if it is better and switches back if it is worse. Only after that does it make
  graphics lighter. (It only flips between those two; settings it does not recognize are never touched.)
- Quiet mode (tick the box, allow Do Not Disturb access): notifications are silenced while the emulator is open and
  your own Do Not Disturb setting is restored afterwards.
- Tap the overlay box to shrink it to one line (clean screen); tap again to expand; drag to move.

v0.4 (works with just the app, no Termux link needed)
- "Best emulator settings for my phone": a checklist (renderer, resolution, filtering, MTVU, EE cycle rate...) matched to
  your chip, plus phone settings. Shortcuts open Battery saver and Battery optimization screens for you.
- Cool mode (tick the box, allow "modify system settings"): when heat starts throttling the CPU, the screen dims by
  itself and your brightness is restored afterwards. Heat is the #1 reason PS2 emulation lags on phones.
- Early heat warning in the overlay: shows "Heating fast (+X C/min)" BEFORE throttling starts.
- Phone link without a laptop or split screen: 'zeron setup' now offers the free Shizuku app route (steps printed).
- Fixed signing key: from now on a new version installs OVER the old one. THIS ONE TIME uninstall the old ZERON BOOST
  first (older builds were signed with a different random key).

UPDATING FROM AN OLDER VERSION
1. Termux:  rm -rf ~/zeron-boost-android ; unzip ~/storage/downloads/ZeronBoost-Android.zip -d ~
   cd ~/zeron-boost-android ; bash termux/push_to_github.sh   (same username and repo name as before)
2. Wait for the green tick on GitHub Actions.
3. Uninstall the old ZERON BOOST (once), then run:  zeron update   (or the curl install line again) and install.

PUT IT ON YOUR PHONE (all from Termux; your token never leaves your phone)
1. Install Termux from F-Droid (not Play Store). Download ZeronBoost-Android.zip from Claude.
2. Termux:  termux-setup-storage      (allow)
   pkg install -y unzip
   unzip ~/storage/downloads/ZeronBoost-Android.zip -d ~
   cd ~/zeron-boost-android
   bash termux/push_to_github.sh
   (GitHub token needs 'repo' and 'workflow' permission. Repo is made PUBLIC so Termux can download the build.)
3. Wait ~5-10 min for a green tick at the Actions link it prints.
4. Run the 'curl ... | bash' line it prints. Allow "Install unknown apps" for Termux. Install the app.
5. Open the app, tap AUTO SET UP, allow the two switches (it takes you there).
6. In Termux type:   zeron
   First time only it asks you to link the phone: enable Developer options > Wireless debugging > Pair device with
   pairing code, then type the PORT and 6-digit CODE it asks for (it finds the port by itself on many phones).
   After that, just type zeron before every gaming session.

OTHER COMMANDS (optional)
  zeron restore   put every original setting back (also turns battery saver etc. back to how they were)
  zeron doctor    check heat, battery saver, RAM, storage
  zeron smooth    deliberate test: you load a scene, it measures each level (more precise, needs Enter presses)

HONEST LIMITS
- Nothing can make a weak phone run PS2 games at full speed. This removes waste, finds the cleanest settings your phone
  can hold, and tells you plainly when heat or the chip is the limit.
- Android will not let normal apps edit another app's files or read its FPS, which is why Termux + adb (wireless
  debugging on this same phone) is used. The pairing is one-time; after a reboot it reconnects by itself if it can find
  the port, otherwise it asks again.
- Keep Termux open in the background while playing (it holds a wake lock). Some phone makers still kill background apps:
  set Termux battery usage to 'Unrestricted'.
- Setting names (upscale_multiplier, EECycleRate, vuThread, ...) come from the PCSX2 family and are not verified on your
  emulator version. Anything not recognized is left alone and printed: send that text to Claude to add rules.
- Not compiled or tested on a real phone by the author. The first GitHub build may show errors: send them to Claude.
