package com.zeronboost.android

import android.content.Context

/** Plain-language checklist tailored to this phone. Values mirror what the Termux tool applies automatically. */
object Guide {
    fun text(ctx: Context): String {
        val (tier, why) = Sys.tier(ctx)
        val mtk = Sys.isMediaTek()
        val sb = StringBuilder()
        sb.append("Your phone: ${Sys.chipName()}\n$why\nStarting level: $tier\n\n")
        if (mtk) {
            sb.append("REALITY CHECK (MediaTek phone, Mali GPU)\n")
            sb.append("- The emulator makers say Mali GPUs run PS2 games slower than Snapdragon (Adreno) ones. On chips like Helio G81, light 2D and simple 3D games are the most likely to run at full speed; heavy 3D games often stay below it. No app can change the chip. What can be done is removing everything that wastes speed.\n")
            sb.append("- Best bet: the newest ARMSX2 emulator (v2.9 or later). It has Automatic Performance Tuning (it tries resolution, blending, texture download mode, GS thread and CPU clock per game and keeps only what makes the game faster) and a Mali GPU driver option. Turn the tuning on for every game.\n")
            sb.append("- The Mali driver option (MaliSX2) officially lists newer Mali GPUs (G57 and up). A G52 may not be supported: if it fails to load, the emulator falls back by itself. Try it, keep it only if the game is faster.\n")
            sb.append("- ARMSX2's IOP thread option is meant for phones with at least 4 big CPU cores. Many budget MediaTek chips have 2, so leave it off.\n\n")
        } else {
            sb.append(when (tier) {
                "Balanced" -> "Your chip is strong: many PS2 games can reach full speed even at 2x resolution.\n\n"
                "Performance" -> "Good chip: many games reach full speed at native resolution; the heaviest ones may dip.\n\n"
                else -> "Lighter chip: light and medium games can reach full speed with the settings below; the heaviest games may stay under it. That is the chip's limit, not a setting.\n\n"
            })
        }
        sb.append("1) IN YOUR EMULATOR (Settings > Graphics / System). Names can differ a little between versions.\n")
        sb.append("- Renderer: Vulkan first (makers recommend it, even on Mali). If it is slower or looks broken, test OpenGL in the same scene.\n")
        sb.append("- Internal resolution: ${if (tier == "Balanced") "2x (about 720p)" else "Native (1x)"}.\n")
        sb.append("- Anisotropic filtering: ${if (tier == "Balanced") "2x or 4x at most" else "Off"}. FXAA: Off.\n")
        sb.append("- Blending accuracy: ${if (tier == "Maximum") "Minimum" else "Basic"}.\n")
        sb.append("- Hardware download mode: Disable Readbacks (recommended for speed).\n")
        sb.append("- Multithreaded VU1 (MTVU): ON.\n")
        sb.append("- EE cycle rate: ${if (tier == "Maximum") "75%" else "100% (default)"}. EE cycle skip: Off.\n")
        sb.append("- If a VSync option exists, turn it OFF. Leave frame limit on Normal.\n")
        sb.append("If a game still dips, the makers' advice is to underclock the emulated CPU: EE cycle rate 60% with EE cycle skip Mild, then 50% with Moderate. Go one step at a time; low values can make games run slow or glitch.\n")
        sb.append("Check each game's own settings so nothing overrides these.\n\n")
        sb.append("2) ON YOUR PHONE\n")
        sb.append("- Battery saver OFF (it slows the CPU). Use the button in this app.\n")
        sb.append("- Battery optimization: set your emulator to Not optimized (button in this app).\n")
        sb.append("- If your phone has a Game mode / Performance mode, set it to Performance for the emulator.\n")
        sb.append("- Do Not Disturb ON while playing (Quiet mode box in this app).\n")
        sb.append("- Keep game files on internal storage, not an SD card.\n\n")
        sb.append("3) HEAT (the number one cause of lag on phones)\n")
        sb.append("- Remove the case, avoid charging while playing, lower brightness.\n")
        sb.append("- Turn on Cool mode in this app: it dims the screen by itself when the phone gets hot and restores it afterwards.\n")
        sb.append("- Tap the overlay box to shrink it to one line (keeps the screen clean); drag it to move it.\n")
        sb.append("- After a play session this app shows how much of the time heat slowed your CPU.")
        return sb.toString()
    }
}
