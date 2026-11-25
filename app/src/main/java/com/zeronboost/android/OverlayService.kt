package com.zeronboost.android

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.content.SharedPreferences
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.TextView

/**
 * Watches which app is in front (needs Usage Access). While your PS2 emulator is in front it shows a small
 * draggable box with MEASURED RAM, battery temperature, thermal state, battery saver and CPU clocks (if readable).
 */
class OverlayService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private var wm: WindowManager? = null
    private var view: TextView? = null
    private var lp: WindowManager.LayoutParams? = null
    private var targets: Set<String> = emptySet()
    private var ticks = 0
    private var lastQuery = 0L
    private val resumed = LinkedHashMap<String, MutableSet<String>>()
    private var fg: String? = null
    private var sessionStart = 0L
    private var maxTemp = 0f
    private var minFree = Long.MAX_VALUE
    private var ticksTotal = 0
    private var ticksThrottle = 0
    private var ticksSaver = 0
    private val tempHist = ArrayDeque<Pair<Long, Float>>()
    private var dimmed = false
    private var dndOn = false

    private val tick = object : Runnable {
        override fun run() {
            try { step() } catch (e: Exception) { /* keep running */ }
            handler.postDelayed(this, 1500)
        }
    }

    override fun onBind(i: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startAsForeground()
        undim()
        dndMode(false)
        wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        targets = loadTargets()
        handler.removeCallbacks(tick)
        handler.post(tick)
        return START_STICKY
    }

    override fun onDestroy() {
        handler.removeCallbacks(tick)
        endSession()
        undim()
        dndMode(false)
        hide()
        super.onDestroy()
    }

    private fun startAsForeground() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("zb", "ZERON BOOST", NotificationManager.IMPORTANCE_LOW))
        val n = Notification.Builder(this, "zb")
            .setContentTitle("ZERON BOOST")
            .setContentText("Waiting for your PS2 emulator")
            .setSmallIcon(android.R.drawable.ic_menu_info_details)
            .setOngoing(true)
            .build()
        startForeground(1, n)
    }

    private fun loadTargets(): Set<String> {
        val s = HashSet<String>()
        getSharedPreferences("zb", MODE_PRIVATE).getString("emu", null)?.let { s.add(it) }
        Emulators.detect(this).forEach { s.add(it.first) }
        return s
    }

    @Suppress("DEPRECATION")
    private fun updateForeground() {
        val usm = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val from = if (lastQuery == 0L) now - 3L * 3600 * 1000 else lastQuery
        val ev = usm.queryEvents(from, now)
        val e = UsageEvents.Event()
        var last: String? = fg
        while (ev.hasNextEvent()) {
            ev.getNextEvent(e)
            val pkg = e.packageName ?: continue
            val cls = e.className ?: ""
            when (e.eventType) {
                UsageEvents.Event.MOVE_TO_FOREGROUND -> {
                    resumed.getOrPut(pkg) { mutableSetOf() }.add(cls)
                    last = pkg
                }
                UsageEvents.Event.MOVE_TO_BACKGROUND -> {
                    resumed[pkg]?.remove(cls)
                    if (resumed[pkg].isNullOrEmpty()) {
                        resumed.remove(pkg)
                        if (last == pkg) last = resumed.keys.lastOrNull()
                    }
                }
            }
        }
        lastQuery = now
        fg = last
    }

    private fun step() {
        if (++ticks % 40 == 0) targets = loadTargets()
        val prefs = getSharedPreferences("zb", MODE_PRIVATE)
        val always = prefs.getBoolean("always", false)
        updateForeground()
        val show = Settings.canDrawOverlays(this) && (always || (fg != null && targets.contains(fg)))
        if (show && prefs.getBoolean("cool", false)) coolMode() else undim()
        dndMode(show && prefs.getBoolean("dnd", false))
        if (show) {
            ensureView()
            view?.text = buildText()
            val warn = lastWarnings
            view?.setTextColor(if (warn) 0xFFFFB84D.toInt() else Color.WHITE)
        } else {
            endSession()
            hide()
        }
    }

    private var lastWarnings = false

    private fun endSession() {
        if (sessionStart == 0L) return
        val secs = (System.currentTimeMillis() - sessionStart) / 1000
        sessionStart = 0L
        if (secs < 20 || ticksTotal == 0) return
        val thr = ticksThrottle * 100 / ticksTotal
        val sav = ticksSaver * 100 / ticksTotal
        val sb = StringBuilder("Last play session: ${secs / 60} min ${secs % 60} s\n")
        sb.append("Peak battery temp: ${"%.1f".format(maxTemp)}\u00B0C   Lowest free RAM: $minFree MB\n")
        sb.append("Throttled by heat: $thr% of the time   Battery saver on: $sav%")
        if (thr >= 20) sb.append("\n-> Heat is slowing your CPU: remove the case, lower brightness, avoid charging while playing.")
        else if (minFree < 300) sb.append("\n-> RAM ran very low: close other apps before playing.")
        else if (sav >= 20) sb.append("\n-> Battery saver was on: it slows the CPU. Turn it off.")
        getSharedPreferences("zb", MODE_PRIVATE).edit().putString("session", sb.toString()).apply()
    }

    private fun buildText(): String {
        val r = Sys.ram(this)
        val b = Sys.battery(this)
        val th = Sys.thermal(this)
        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        val f = Sys.curFreqsMhz()
        if (sessionStart == 0L) {
            sessionStart = System.currentTimeMillis()
            maxTemp = 0f; minFree = Long.MAX_VALUE; ticksTotal = 0; ticksThrottle = 0; ticksSaver = 0
        }
        ticksTotal++
        if (b.tempC > maxTemp) maxTemp = b.tempC
        if (r.availMb < minFree) minFree = r.availMb
        if (th >= 2) ticksThrottle++
        if (pm.isPowerSaveMode) ticksSaver++
        val sb = StringBuilder("ZERON BOOST\n")
        sb.append("RAM ${r.usedPct}%  (${r.availMb} MB free)\n")
        sb.append("Battery ${b.pct}%${if (b.charging) " +" else ""}  ${"%.1f".format(b.tempC)}\u00B0C\n")
        sb.append("Thermal: ${Sys.thermalName(th)}\n")
        if (f.isNotEmpty()) sb.append("CPU clock: max ${f.max()} / avg ${f.average().toInt()} MHz\n")
        else sb.append("CPU clock: n/a (blocked by this phone)\n")
        val w = ArrayList<String>()
        val now = System.currentTimeMillis()
        tempHist.addLast(now to b.tempC)
        while (tempHist.size > 1 && now - tempHist.first().first > 120000) tempHist.removeFirst()
        val spanMs = now - tempHist.first().first
        if (spanMs >= 45000) {
            val perMin = (b.tempC - tempHist.first().second) * 60000f / spanMs
            if (perMin >= 0.8f && b.tempC >= 38f) w.add("! Heating fast (+${"%.1f".format(perMin)}\u00B0C/min) - lower brightness, remove case")
        }
        if (dimmed) w.add("Cool mode: screen dimmed to cut heat")
        if (th >= 2) w.add("! Throttling likely - cool the phone")
        if (pm.isPowerSaveMode) w.add("! Battery saver ON (slows CPU)")
        if (r.usedPct >= 90) w.add("! RAM almost full")
        if (!b.charging && b.pct in 0..19) w.add("! Low battery, plug in")
        lastWarnings = w.isNotEmpty()
        if (getSharedPreferences("zb", MODE_PRIVATE).getBoolean("compact", false))
            return "ZB ${r.usedPct}% ${"%.0f".format(b.tempC)}\u00B0C ${if (w.isEmpty()) "ok" else "!"}"
        w.forEach { sb.append(it).append('\n') }
        return sb.toString().trimEnd()
    }

    private fun ensureView() {
        if (view != null) return
        val dm = resources.displayMetrics
        fun dp(x: Int) = (x * dm.density).toInt()
        val tv = TextView(this)
        tv.textSize = 11f
        tv.typeface = Typeface.MONOSPACE
        tv.setTextColor(Color.WHITE)
        tv.setPadding(dp(8), dp(6), dp(8), dp(6))
        val bg = GradientDrawable()
        bg.setColor(0xB3000000.toInt())
        bg.cornerRadius = dp(10).toFloat()
        tv.background = bg
        val prefs = getSharedPreferences("zb", MODE_PRIVATE)
        val p = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT
        )
        p.gravity = Gravity.TOP or Gravity.START
        p.x = prefs.getInt("ox", 20)
        p.y = prefs.getInt("oy", 120)
        tv.setOnTouchListener(object : View.OnTouchListener {
            var sx = 0; var sy = 0; var tx = 0f; var ty = 0f; var moved = false
            override fun onTouch(v: View, e: MotionEvent): Boolean {
                when (e.action) {
                    MotionEvent.ACTION_DOWN -> { sx = p.x; sy = p.y; tx = e.rawX; ty = e.rawY; moved = false }
                    MotionEvent.ACTION_MOVE -> {
                        if (Math.abs(e.rawX - tx) > 12f || Math.abs(e.rawY - ty) > 12f) moved = true
                        p.x = sx + (e.rawX - tx).toInt(); p.y = sy + (e.rawY - ty).toInt()
                        try { wm?.updateViewLayout(v, p) } catch (x: Exception) { }
                    }
                    MotionEvent.ACTION_UP -> {
                        if (moved) prefs.edit().putInt("ox", p.x).putInt("oy", p.y).apply()
                        else prefs.edit().putBoolean("compact", !prefs.getBoolean("compact", false)).apply()
                    }
                }
                return true
            }
        })
        try {
            wm?.addView(tv, p)
            view = tv
            lp = p
        } catch (e: Exception) { view = null }
    }

    private fun coolMode() {
        if (!Settings.System.canWrite(this)) return
        val b = Sys.battery(this)
        val th = Sys.thermal(this)
        val hot = th >= 2 || b.tempC >= 42f
        if (hot && !dimmed) {
            try {
                val cr = contentResolver
                val mode = Settings.System.getInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, 0)
                val br = Settings.System.getInt(cr, Settings.System.SCREEN_BRIGHTNESS, 128)
                getSharedPreferences("zb", MODE_PRIVATE).edit().putInt("dim_b", br).putInt("dim_m", mode).apply()
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, 0)
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS, maxOf(30, br * 40 / 100))
                dimmed = true
            } catch (e: Exception) { }
        } else if (dimmed && !hot && b.tempC < 39.5f && th < 2) {
            undim()
        }
    }

    /** Quiet notifications while the emulator is in front; puts the user's own Do Not Disturb setting back afterwards. */
    private fun dndMode(want: Boolean) {
        val nm = getSystemService(NotificationManager::class.java)
        if (!nm.isNotificationPolicyAccessGranted) return
        val prefs = getSharedPreferences("zb", MODE_PRIVATE)
        if (want && !dndOn) {
            prefs.edit().putInt("dnd_prev", nm.currentInterruptionFilter).apply()
            nm.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_PRIORITY)
            dndOn = true
        } else if (!want && (dndOn || prefs.contains("dnd_prev"))) {
            val prev = prefs.getInt("dnd_prev", NotificationManager.INTERRUPTION_FILTER_ALL)
            nm.setInterruptionFilter(if (prev <= 0) NotificationManager.INTERRUPTION_FILTER_ALL else prev)
            prefs.edit().remove("dnd_prev").apply()
            dndOn = false
        }
    }

    /** Puts the user's brightness back. Also runs at start-up, in case the app was closed while dimmed. */
    private fun undim() {
        val prefs = getSharedPreferences("zb", MODE_PRIVATE)
        if (!prefs.contains("dim_b")) { dimmed = false; return }
        try {
            if (Settings.System.canWrite(this)) {
                val cr = contentResolver
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS, prefs.getInt("dim_b", 128))
                Settings.System.putInt(cr, Settings.System.SCREEN_BRIGHTNESS_MODE, prefs.getInt("dim_m", 0))
            }
        } catch (e: Exception) { }
        prefs.edit().remove("dim_b").remove("dim_m").apply()
        dimmed = false
    }

    private fun hide() {
        val v = view ?: return
        try { wm?.removeView(v) } catch (e: Exception) { }
        view = null
    }
}
