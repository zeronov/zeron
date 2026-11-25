package com.zeronboost.android

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import android.os.PowerManager
import java.io.File

data class Bat(val pct: Int, val tempC: Float, val charging: Boolean)
data class Ram(val usedPct: Int, val availMb: Long, val totalMb: Long)

/** Everything here is read from real Android APIs / sysfs. Nothing is estimated unless the label says so. */
object Sys {
    fun ram(ctx: Context): Ram {
        val am = ctx.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val mi = ActivityManager.MemoryInfo()
        am.getMemoryInfo(mi)
        val total = mi.totalMem / 1048576
        val avail = mi.availMem / 1048576
        return Ram(((total - avail) * 100 / maxOf(total, 1L)).toInt(), avail, total)
    }

    fun battery(ctx: Context): Bat {
        val i = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = i?.getIntExtra("level", -1) ?: -1
        val scale = i?.getIntExtra("scale", 100) ?: 100
        val temp = (i?.getIntExtra("temperature", 0) ?: 0) / 10f
        val status = i?.getIntExtra("status", 0) ?: 0
        val charging = status == 2 || status == 5
        return Bat(if (level >= 0 && scale > 0) level * 100 / scale else -1, temp, charging)
    }

    fun thermal(ctx: Context): Int {
        if (Build.VERSION.SDK_INT >= 29) {
            val pm = ctx.getSystemService(Context.POWER_SERVICE) as PowerManager
            return pm.currentThermalStatus
        }
        return -1
    }

    fun thermalName(s: Int): String = when (s) {
        0 -> "normal"
        1 -> "light"
        2 -> "MODERATE"
        3 -> "SEVERE"
        4, 5, 6 -> "CRITICAL"
        else -> "n/a"
    }

    private fun readLong(path: String): Long? = try {
        File(path).readText().trim().toLong()
    } catch (e: Exception) {
        null
    }

    fun cores(): Int = Runtime.getRuntime().availableProcessors()

    fun chipName(): String =
        if (Build.VERSION.SDK_INT >= 31 && Build.SOC_MODEL.isNotBlank() && Build.SOC_MODEL != "unknown")
            "${Build.SOC_MANUFACTURER} ${Build.SOC_MODEL}"
        else Build.HARDWARE

    /** MediaTek Helio/Dimensity phones use Arm Mali GPUs, which PS2 emulators run slower on than Snapdragon (Adreno). */
    fun isMediaTek(): Boolean {
        val s = (chipName() + " " + Build.HARDWARE + " " + Build.BOARD).lowercase()
        return s.contains("mt6") || s.contains("mt8") || s.contains("mediatek") || s.contains("helio") || s.contains("dimensity")
    }

    /** Current CPU clocks in MHz; empty if this phone does not let apps read them. */
    fun curFreqsMhz(): List<Long> =
        (0 until cores()).mapNotNull { readLong("/sys/devices/system/cpu/cpu$it/cpufreq/scaling_cur_freq") }.map { it / 1000 }

    fun maxFreqMhz(): Long? =
        (0 until cores()).mapNotNull { readLong("/sys/devices/system/cpu/cpu$it/cpufreq/cpuinfo_max_freq") }.maxOrNull()?.div(1000)

    /** Rule-of-thumb profile (NOT a benchmark): returns profile name and the facts it used. */
    fun tier(ctx: Context): Pair<String, String> {
        val r = ram(ctx)
        val ghz = (maxFreqMhz() ?: 0L) / 1000.0
        val c = cores()
        val p = when {
            r.totalMb >= 7000 && ghz >= 2.8 && c >= 8 -> "Balanced"
            r.totalMb >= 5000 && ghz >= 2.4 -> "Performance"
            else -> "Maximum"
        }
        val f = if (ghz > 0) "%.1f GHz".format(ghz) else "clock unknown"
        return p to "RAM ${r.totalMb} MB, $c cores, max $f"
    }
}

object Emulators {
    val known = listOf(
        "xyz.aethersx2.android" to "AetherSX2 / NetherSX2",
        "come.nanodevelopment.armsx2" to "ARMSX2",
        "com.virtualapplications.play" to "Play!"
    )

    fun detect(ctx: Context): List<Pair<String, String>> {
        val pm = ctx.packageManager
        val out = LinkedHashMap<String, String>()
        for (ai in pm.getInstalledApplications(0)) {
            val p = ai.packageName
            if (p == ctx.packageName) continue
            val label = try { pm.getApplicationLabel(ai).toString() } catch (e: Exception) { p }
            val lp = p.lowercase()
            val ll = label.lowercase()
            val hit = known.any { it.first == p } || listOf("sx2", "ps2", "pcsx2").any { lp.contains(it) || ll.contains(it) }
            if (hit) out[p] = label
        }
        return out.map { it.key to it.value }
    }
}
