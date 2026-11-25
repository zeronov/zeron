package com.zeronboost.android

import android.app.Activity
import android.app.ActivityManager
import android.app.AlertDialog
import android.app.AppOpsManager
import android.app.NotificationManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.ApplicationInfo
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.os.Process
import android.provider.Settings
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var prefs: SharedPreferences
    private lateinit var info: TextView
    private lateinit var status: TextView
    private lateinit var freeChk: CheckBox
    private lateinit var alwaysChk: CheckBox
    private lateinit var coolChk: CheckBox
    private lateinit var dndChk: CheckBox
    private val ui = Handler(Looper.getMainLooper())
    private var emus: List<Pair<String, String>> = emptyList()
    private var emu: String? = null

    private fun dp(x: Int) = (x * resources.displayMetrics.density).toInt()
    private fun toast(t: String) = Toast.makeText(this, t, Toast.LENGTH_LONG).show()

    private fun label(t: String, size: Float, color: Int, bold: Boolean = false): TextView {
        val v = TextView(this)
        v.text = t; v.textSize = size; v.setTextColor(color)
        if (bold) v.setTypeface(v.typeface, Typeface.BOLD)
        v.setPadding(0, dp(6), 0, dp(2))
        return v
    }

    private fun btn(text: String, color: Int = 0xFF2F8CFF.toInt(), onClick: () -> Unit): Button {
        val b = Button(this)
        b.text = text; b.setTextColor(Color.WHITE); b.isAllCaps = false
        val g = GradientDrawable()
        g.cornerRadius = dp(10).toFloat(); g.setColor(color)
        b.background = g
        b.setOnClickListener { onClick() }
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.topMargin = dp(8)
        b.layoutParams = lp
        return b
    }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        prefs = getSharedPreferences("zb", MODE_PRIVATE)
        val grey = 0xFF8A919B.toInt()
        val light = 0xFFC8CDD4.toInt()
        val col = LinearLayout(this)
        col.orientation = LinearLayout.VERTICAL
        col.setPadding(dp(18), dp(24), dp(18), dp(32))
        col.addView(label("ZERON BOOST", 26f, Color.WHITE, true))
        col.addView(label("PS2 emulator booster for Android", 13f, grey))
        info = label("", 13f, light); col.addView(info)
        status = label("", 13f, light); col.addView(status)

        freeChk = CheckBox(this)
        freeChk.text = "Free memory before launch (stops cached background apps)"
        freeChk.setTextColor(Color.WHITE)
        freeChk.isChecked = prefs.getBoolean("free", true)
        freeChk.setOnCheckedChangeListener { _, c -> prefs.edit().putBoolean("free", c).apply() }
        alwaysChk = CheckBox(this)
        alwaysChk.text = "Test mode: show overlay on every screen"
        alwaysChk.setTextColor(Color.WHITE)
        alwaysChk.isChecked = prefs.getBoolean("always", false)
        alwaysChk.setOnCheckedChangeListener { _, c -> prefs.edit().putBoolean("always", c).apply() }

        col.addView(btn("AUTO SET UP  (tap, allow, come back)", 0xFF2F8CFF.toInt()) {
            prefs.edit().putBoolean("setup", true).putInt("setupSteps", 0).apply()
            nextSetupStep()
        })
        coolChk = CheckBox(this)
        coolChk.text = "Cool mode: auto-dim the screen when the phone gets hot"
        coolChk.setTextColor(Color.WHITE)
        coolChk.isChecked = prefs.getBoolean("cool", false)
        coolChk.setOnCheckedChangeListener { _, c ->
            prefs.edit().putBoolean("cool", c).apply()
            if (c && !Settings.System.canWrite(this)) {
                toast("Turn ON 'Allow modify system settings' for ZERON BOOST, then press Back.")
                startActivity(Intent(Settings.ACTION_MANAGE_WRITE_SETTINGS, Uri.parse("package:$packageName")))
            }
        }
        dndChk = CheckBox(this)
        dndChk.text = "Quiet mode: Do Not Disturb while the emulator is open"
        dndChk.setTextColor(Color.WHITE)
        dndChk.isChecked = prefs.getBoolean("dnd", false)
        dndChk.setOnCheckedChangeListener { _, c ->
            prefs.edit().putBoolean("dnd", c).apply()
            val nm = getSystemService(NotificationManager::class.java)
            if (c && !nm.isNotificationPolicyAccessGranted) {
                toast("Turn ON Do Not Disturb access for ZERON BOOST, then press Back.")
                startActivity(Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS))
            }
        }
        col.addView(btn("1. Allow overlay (draw over other apps)", 0xFF23262B.toInt()) {
            if (!Settings.canDrawOverlays(this))
                startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            else toast("Already allowed")
        })
        col.addView(btn("2. Allow usage access (to see when the emulator is open)", 0xFF23262B.toInt()) {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        })
        col.addView(btn("3. Start automatic overlay", 0xFF23262B.toInt()) {
            if (!Settings.canDrawOverlays(this)) toast("Do step 1 first")
            else {
                startForegroundService(Intent(this, OverlayService::class.java))
                toast("Running. It shows itself when your emulator is open.")
            }
            refresh()
        })
        col.addView(btn("Choose emulator", 0xFF23262B.toInt()) { chooseEmulator() })
        col.addView(btn("Best emulator settings for my phone", 0xFF2F8CFF.toInt()) { showGuide() })
        col.addView(btn("Battery saver settings (turn it OFF)", 0xFF23262B.toInt()) {
            startActivity(Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS))
        })
        col.addView(btn("Battery optimization list (emulator: Not optimized)", 0xFF23262B.toInt()) {
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        })
        col.addView(coolChk)
        col.addView(dndChk)
        col.addView(freeChk)
        col.addView(btn("OPTIMIZE & LAUNCH EMULATOR", 0xFF2F8CFF.toInt()) { optimizeAndLaunch() })
        col.addView(btn("Stop overlay", 0xFF23262B.toInt()) { stopService(Intent(this, OverlayService::class.java)); toast("Stopped") })
        col.addView(btn("Copy the Termux command (auto-tunes your emulator)", 0xFF23262B.toInt()) {
            val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("zeron", "zeron"))
            toast("Copied: zeron  (paste it in Termux and press Enter)")
        })
        col.addView(alwaysChk)

        val sv = ScrollView(this)
        sv.setBackgroundColor(0xFF1B1D21.toInt())
        sv.addView(col)
        setContentView(sv)
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 1)
    }

    override fun onResume() {
        super.onResume()
        if (prefs.getBoolean("setup", false)) nextSetupStep()
        refresh()
    }

    /** Opens the next missing permission screen; called again each time you return, until everything is allowed. */
    private fun nextSetupStep() {
        val n = prefs.getInt("setupSteps", 0)
        if (n > 6) { prefs.edit().putBoolean("setup", false).apply(); toast("Setup stopped. Use buttons 1-3 if a permission was refused."); return }
        if (!Settings.canDrawOverlays(this)) {
            prefs.edit().putInt("setupSteps", n + 1).apply()
            toast("Turn ON 'Allow display over other apps' for ZERON BOOST, then press Back.")
            startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
        } else if (!hasUsage()) {
            prefs.edit().putInt("setupSteps", n + 1).apply()
            toast("Find ZERON BOOST in the list, turn ON usage access, then press Back.")
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        } else {
            prefs.edit().putBoolean("setup", false).apply()
            startForegroundService(Intent(this, OverlayService::class.java))
            toast("All set! Open your PS2 emulator - the overlay shows by itself.")
        }
    }

    private fun hasUsage(): Boolean {
        val ops = getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        @Suppress("DEPRECATION")
        val mode = if (Build.VERSION.SDK_INT >= 29)
            ops.unsafeCheckOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), packageName)
        else ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), packageName)
        return mode == AppOpsManager.MODE_ALLOWED
    }

    private fun refresh() {
        val (tp, why) = Sys.tier(this)
        val soc = if (Build.VERSION.SDK_INT >= 31) "${Build.SOC_MANUFACTURER} ${Build.SOC_MODEL}" else Build.HARDWARE
        info.text = "Phone: ${Build.MANUFACTURER} ${Build.MODEL}\nChip: $soc\n$why\n" +
            "Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})\n" +
            "Suggested profile: $tp (rule of thumb, not a benchmark)"
        emus = Emulators.detect(this)
        if (emu == null) emu = prefs.getString("emu", null)
        if (emu == null || emus.none { it.first == emu }) emu = emus.firstOrNull()?.first
        prefs.edit().putString("emu", emu).apply()
        val name = emus.firstOrNull { it.first == emu }?.second ?: "none found"
        val last = prefs.getString("last", null)
        val ses = prefs.getString("session", null)
        status.text = "Emulator: $name${if (emu != null) " ($emu)" else ""}\n" +
            "Overlay permission: ${if (Settings.canDrawOverlays(this)) "OK" else "NOT GRANTED"}\n" +
            "Usage access: ${if (hasUsage()) "OK" else "NOT GRANTED"}" +
            (if (last != null) "\n\nLast optimize:\n$last" else "") +
            (if (ses != null) "\n\n$ses" else "")
    }

    private fun showGuide() {
        val tv = TextView(this)
        tv.text = Guide.text(this)
        tv.textSize = 14f
        tv.setPadding(dp(18), dp(12), dp(18), dp(12))
        val sv = ScrollView(this)
        sv.addView(tv)
        AlertDialog.Builder(this).setTitle("Best settings for your phone").setView(sv).setPositiveButton("Close", null).show()
    }

    private fun chooseEmulator() {
        if (emus.size < 2) { toast(if (emus.isEmpty()) "No PS2 emulator found" else "Only one emulator found"); return }
        AlertDialog.Builder(this).setTitle("Choose emulator")
            .setItems(emus.map { "${it.second} (${it.first})" }.toTypedArray()) { _, i ->
                emu = emus[i].first; prefs.edit().putString("emu", emu).apply(); refresh()
            }.show()
    }

    private fun freeMemory(emuPkg: String): Int {
        val am = getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val pm = packageManager
        val keep = HashSet<String>()
        keep.add(packageName); keep.add(emuPkg)
        pm.resolveActivity(Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), 0)?.activityInfo?.packageName?.let { keep.add(it) }
        Settings.Secure.getString(contentResolver, Settings.Secure.DEFAULT_INPUT_METHOD)?.substringBefore('/')?.let { keep.add(it) }
        var n = 0
        for (ai in pm.getInstalledApplications(0)) {
            if (ai.flags and ApplicationInfo.FLAG_SYSTEM != 0) continue
            if (ai.packageName in keep || ai.packageName.startsWith("com.termux")) continue
            try { am.killBackgroundProcesses(ai.packageName); n++ } catch (e: Exception) { }
        }
        return n
    }

    private fun optimizeAndLaunch() {
        val pkg = emu
        if (pkg == null) { toast("Install your PS2 emulator first"); return }
        val notes = ArrayList<String>()
        val before = Sys.ram(this).availMb
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (pm.isPowerSaveMode) notes.add("! Battery saver is ON - it slows the CPU. Turn it off.")
        val bat = Sys.battery(this)
        if (!bat.charging && bat.pct in 0..29) notes.add("! Battery ${bat.pct}% and not charging - plug in for steady speed.")
        val th = Sys.thermal(this)
        if (th >= 2) notes.add("! Phone is hot (${Sys.thermalName(th)}) - let it cool; the CPU is being throttled.")
        val freeing = freeChk.isChecked
        val asked = if (freeing) freeMemory(pkg) else 0
        toast("Optimizing...")
        ui.postDelayed({
            val after = Sys.ram(this).availMb
            notes.add(0, "Free RAM: $before MB -> $after MB (measured)" + (if (freeing) ", asked $asked apps to stop" else ""))
            notes.add("Emulator settings: type  zeron  in Termux - it does everything automatically.")
            prefs.edit().putString("last", notes.joinToString("\n")).apply()
            if (Settings.canDrawOverlays(this)) startForegroundService(Intent(this, OverlayService::class.java))
            val li = packageManager.getLaunchIntentForPackage(pkg)
            if (li != null) startActivity(li) else toast("Could not launch $pkg")
        }, 1500)
    }
}
