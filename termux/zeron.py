#!/usr/bin/env python3
"""ZERON BOOST for Termux - tunes your PS2 emulator's settings files safely.

* Talks to the emulator's data folder through adb (wireless debugging to this same phone),
  because Android 11+ blocks normal apps from Android/data.
* Backs up every file before editing. Only LOWERS heavy settings (or turns speed options on). Never raises quality.
* Only edits keys it recognizes; everything else is left alone and listed.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".zeronboost")
BK = os.path.join(DIR, "backups")
WORK = os.path.join(DIR, "work")
MAN = os.path.join(DIR, "manifest.json")
REPO_FILE = os.path.join(DIR, "repo")
KNOWN = ["xyz.aethersx2.android", "come.nanodevelopment.armsx2"]
HINTS = ("sx2", "ps2", "pcsx2")
APP = "com.zeronboost.android"
PROFILES = {"balanced": 0, "performance": 1, "maximum": 2}
LADDER = ["Balanced", "Performance", "Maximum", "Maximum + lighter EE", "Extreme (may glitch)"]
RESULTS = os.path.join(DIR, "results.json")

KV = re.compile(r'^(\s*)([A-Za-z0-9_.\-]+)(\s*=\s*)(.*?)(\s*)$')
UNKNOWN_HINTS = ("upscal", "blend", "aniso", "hack", "cycle", "skip", "texture", "filter", "mipmap", "dither", "deinterlac")


BACKEND = "adb"                       # "adb" (wireless debugging) or "rish" (Shizuku)
RISHDIR = os.path.join(DIR, "rish")
RISH = os.path.join(RISHDIR, "rish")
LSTAGE = os.path.join(HOME, "storage", "downloads", ".zb_stage")   # same folder as /sdcard/Download
RSTAGE = "/sdcard/Download/.zb_stage"
_rish_cache = {"t": 0.0, "ok": False}


def _run(args, timeout=90, env=None):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, "not found: " + args[0]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def _rish(cmd, timeout=90):
    env = dict(os.environ, RISH_APPLICATION_ID="com.termux")
    return _run(["sh", RISH, "-c", cmd], timeout, env)


def rish_ok():
    """True when Shizuku's rish gives a shell-level (uid 2000) terminal."""
    if _rish_cache["ok"] and time.time() - _rish_cache["t"] < 60:
        return True
    if not os.path.exists(RISH):
        return False
    rc, o = _rish("id", 25)
    ok = rc == 0 and "uid=2000" in o
    _rish_cache.update(t=time.time(), ok=ok)
    return ok


def _via_rish(args, timeout):
    """Run an 'adb ...' style command through rish. Files are moved through the shared Download folder."""
    sub = args[1] if len(args) > 1 else ""
    if sub == "shell":
        return _rish(" ".join(args[2:]), timeout)
    if sub == "pull":
        remote, local = args[2], args[3]
        rc, o = _rish("cp '%s' '%s'" % (remote, RSTAGE), timeout)
        if rc != 0:
            return rc, o
        try:
            os.makedirs(os.path.dirname(local) or ".", exist_ok=True)
            shutil.copyfile(LSTAGE, local)
            return 0, ""
        except Exception as e:
            return 1, str(e)
        finally:
            _rish("rm -f '%s'" % RSTAGE, 20)
    if sub == "push":
        local, remote = args[2], args[3]
        try:
            shutil.copyfile(local, LSTAGE)
        except Exception as e:
            return 1, str(e)
        rc, o = _rish("cp '%s' '%s'" % (RSTAGE, remote), timeout)
        _rish("rm -f '%s'" % RSTAGE, 20)
        return rc, o
    return 0, ""                           # devices / connect / pair / mdns / start-server: nothing to do


def sh(args, timeout=90):
    if BACKEND == "rish" and args and args[0] == "adb":
        return _via_rish(args, timeout)
    return _run(args, timeout)


def adb_ready():
    global BACKEND
    rc, out = _run(["adb", "devices"], 20)
    if rc == 0:
        for l in out.splitlines()[1:]:
            t = l.split()
            if len(t) >= 2 and t[-1] == "device":
                BACKEND = "adb"
                return True
    if rish_ok():
        BACKEND = "rish"
        return True
    return False


ADB_HELP = "This phone is not linked yet. Run:  zeron setup   (it walks you through it, no laptop needed)."

ADBTARGET = os.path.join(DIR, "adbtarget")

PAIR_STEPS = """
One-time phone link (about 1 minute). Wi-Fi must be on (a hotspot is fine).
  1. Settings > About phone > tap 'Build number' 7 times (turns on Developer options).
  2. Settings > Developer options > turn ON 'Wireless debugging'.
  3. Tap 'Pair device with pairing code'. A popup shows a 6-digit CODE and a PORT.
  4. Keep that popup open (use split screen / a floating Termux window) and answer below.
"""


def mdns():
    """Ask adb to discover the phone's own wireless-debugging ports (works on many phones)."""
    found = {}
    rc, o = sh(["adb", "mdns", "services"], timeout=15)
    for l in o.splitlines():
        m = re.search(r"_adb-tls-(connect|pairing)\._tcp\.?\s+(\S+):(\d+)\s*$", l.strip())
        if m:
            found[m.group(1)] = (m.group(2), m.group(3))
    return found


SHIZUKU_STEPS = """
PHONE-ONLY LINK with the free Shizuku app (no laptop, no split screen):
 1. Connect to Wi-Fi (any Wi-Fi, even without internet; a hotspot from another phone works).
 2. Install 'Shizuku' (Play Store, or github.com/RikkaApps/Shizuku). Open it.
 3. In Shizuku tap 'Start via Wireless debugging' and follow its screens (it opens Developer options for you;
    no Developer options? Settings > About phone > tap 'Build number' 7 times).
 4. Tap 'Pairing' in Shizuku, then in Developer options > Wireless debugging tap 'Pair device with pairing code'.
    A popup shows a 6-digit code. DO NOT close it: pull down the notification bar and type the code into
    Shizuku's notification box. It says pairing successful.
 5. Back in Shizuku tap 'Start'. It should say 'Shizuku is running'.
 6. In Shizuku tap 'Use Shizuku in terminal apps' > 'Export files' and choose the Download folder.
 7. Come back to Termux and press Enter here.
(Button names can differ a little between Shizuku versions.)
"""


def install_rish():
    """Copy the files Shizuku exported to Download into place."""
    src = os.path.join(HOME, "storage", "downloads")
    r, d = os.path.join(src, "rish"), os.path.join(src, "rish_shizuku.dex")
    if not (os.path.exists(r) and os.path.exists(d)):
        return False
    os.makedirs(RISHDIR, exist_ok=True)
    for f in (RISH, os.path.join(RISHDIR, "rish_shizuku.dex")):
        if os.path.exists(f):
            os.chmod(f, 0o600)
    shutil.copyfile(r, RISH)
    shutil.copyfile(d, os.path.join(RISHDIR, "rish_shizuku.dex"))
    os.chmod(RISH, 0o755)
    os.chmod(os.path.join(RISHDIR, "rish_shizuku.dex"), 0o400)   # Android 14 refuses writable dex files
    _rish_cache["ok"] = False
    return True


def try_connect():
    sh(["adb", "start-server"])
    if adb_ready():
        return True
    cands = []
    c = mdns().get("connect")
    if c:
        cands.append("%s:%s" % c)
    try:
        cands.append(open(ADBTARGET).read().strip())
    except Exception:
        pass
    for c in cands:
        if c:
            sh(["adb", "connect", c])
            if adb_ready():
                os.makedirs(DIR, exist_ok=True)
                with open(ADBTARGET, "w") as f:
                    f.write(c)
                return True
    return False


def pair_with_code():
    """Old method: needs the pairing popup AND Termux visible at the same time (split screen / floating window)."""
    print("""
Pairing-code method (needs split screen or a floating Termux window on top of Settings).
  Settings > Developer options > Wireless debugging > 'Pair device with pairing code'.""")
    for attempt in range(3):
        pp = mdns().get("pairing")
        if pp:
            host, port = pp
            print("Found the pairing popup automatically (port %s)." % port)
        else:
            host, port = "localhost", input("Type the PORT from the popup (example 41234): ").strip()
        code = input("Type the 6-digit pairing CODE: ").strip()
        rc, o = sh(["adb", "pair", "%s:%s" % (host, port), code])
        print(o.strip())
        if "uccessfully" in o:
            break
        print("That did not work. Check the code/port (they change each time) and try again.\n")
    else:
        return False
    time.sleep(2)
    c = mdns().get("connect")
    if not c:
        print("On the Wireless debugging screen, 'IP address & Port' shows something like 192.168.1.5:37123.")
        c = ("localhost", input("Type just the PORT (the number after the colon): ").strip())
    sh(["adb", "connect", "%s:%s" % c])
    if adb_ready():
        os.makedirs(DIR, exist_ok=True)
        with open(ADBTARGET, "w") as f:
            f.write("%s:%s" % c)
        return True
    return False


def ensure_adb(guide=True):
    """Get a shell-level link to this phone. Reconnects silently if linked before; otherwise guides you."""
    if try_connect():
        return True
    if install_rish() and adb_ready():
        print("Shizuku link found and installed.")
        return True
    if not guide:
        return False
    print(SHIZUKU_STEPS)
    try:
        for attempt in range(3):
            input("Press Enter when you have done step 7 (or Ctrl+C to stop)... ")
            if install_rish() and adb_ready():
                print("Phone linked through Shizuku. You do not need to repeat this unless you reboot (then just open Shizuku and tap Start).")
                return True
            if not os.path.exists(os.path.join(HOME, "storage", "downloads", "rish")):
                print("I can't see the exported files in your Download folder (rish and rish_shizuku.dex). Redo step 6.")
            else:
                print("Files found but Shizuku does not answer. Open Shizuku and check it says 'running', then try again.")
        x = input("Type P to try the pairing-code method instead, or press Enter to stop: ").strip().lower()
        if x == "p":
            return pair_with_code()
    except (EOFError, KeyboardInterrupt):
        print()
    return False


def load_man():
    try:
        with open(MAN) as f:
            return json.load(f)
    except Exception:
        return {}


def save_man(m):
    os.makedirs(DIR, exist_ok=True)
    with open(MAN, "w") as f:
        json.dump(m, f, indent=1)


# ---------- device facts (real reads) ----------
def device_facts():
    ram_gb = None
    try:
        for l in open("/proc/meminfo"):
            if l.startswith("MemTotal"):
                ram_gb = int(l.split()[1]) / 1048576.0
                break
    except Exception:
        pass
    cores = os.cpu_count() or 1
    maxf = None
    for i in range(cores):
        try:
            v = int(open("/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq" % i).read().strip())
            maxf = v if maxf is None else max(maxf, v)
        except Exception:
            pass
    return ram_gb, cores, (maxf / 1e6 if maxf else None)


def auto_profile():
    ram, cores, ghz = device_facts()
    if ram is not None and ghz is not None and ram >= 7 and ghz >= 2.8 and cores >= 8:
        p = "balanced"
    elif ram is not None and ghz is not None and ram >= 5 and ghz >= 2.4:
        p = "performance"
    else:
        p = "maximum"
    why = "RAM %s GB, %d cores, max %s (rule of thumb, not a benchmark)" % (
        "%.1f" % ram if ram else "?", cores, "%.1f GHz" % ghz if ghz else "clock unknown")
    return p, why, cores


# ---------- tuning rules ----------
def num(v):
    try:
        return float(v.strip())
    except ValueError:
        return None


SEEN = {}                                  # what the settings files said before we touched them
RNAME = {12: "OpenGL", 14: "Vulkan"}


def make_rules(level, cores, renderer=None):
    """level 0-2 = profiles; 3 and 4 are extra speed steps used only by 'zeron smooth'."""
    P = min(level, 2)
    R = {
        "upscale_multiplier": ("capf", [2.0, 1.0, 1.0][P]),
        "maxanisotropy": ("capi", [4, 0, 0][P]),
        "accurate_blending_unit": ("capi", [1, 1, 0][P]),
    }
    if P > 0:
        R["fxaa"] = ("off", None)
        R["shadeboost"] = ("off", None)
        R["eecyclerate"] = ("capi", [0, 0, -1][P])
    if P > 0:
        R["hwdownloadmode"] = ("mini", 1)     # "Disable Readbacks": recommended for speed by NetherSX2 docs
    if level >= 3:
        R["eecyclerate"] = ("capi", -2)       # 60%
        R["eecycleskip"] = ("mini", 1)        # mild skip (official FAQ: negative rate + positive skip)
    if level >= 4:
        R["eecyclerate"] = ("capi", -3)       # 50%
        R["eecycleskip"] = ("mini", 2)
    if cores >= 4:
        R["vuthread"] = ("on", None)   # MTVU: speeds up emulation on multi-core phones
    if renderer in RNAME:
        R["renderer"] = ("set", renderer)   # only ever flips between OpenGL(12) and Vulkan(14)
    return R


def flip(val, on):
    t = val.strip()
    if t.lower() in ("true", "false"):
        w = "true" if on else "false"
        return w.capitalize() if t[:1].isupper() else w
    if t in ("0", "1"):
        return "1" if on else "0"
    return None


def tune_text(text, level, cores, renderer=None):
    R = make_rules(level, cores, renderer)
    lines = text.split("\n")
    changes, unknown = [], []
    for i, l in enumerate(lines):
        s = l.strip()
        if not s or s[0] in ";#[":
            continue
        m = KV.match(l)
        if not m:
            continue
        ind, key, sep, val, trail = m.groups()
        k = key.lower()
        if k == "renderer":
            try:
                SEEN["renderer"] = int(float(val.strip()))
            except ValueError:
                pass
        if k in R:
            kind, arg = R[k]
            nv = None
            x = num(val)
            if kind == "capf" and x is not None and x > arg:
                nv = "%.6f" % arg
            elif kind == "capi" and x is not None and int(x) > arg:
                nv = str(arg)
            elif kind == "set" and x is not None and int(x) in (-1, 12, 14) and int(x) != arg:
                nv = str(arg)
            elif kind == "mini" and x is not None and int(x) < arg:
                nv = str(arg)
            elif kind == "off" and val.strip().lower() in ("true", "1"):
                nv = flip(val, False)
            elif kind == "on" and val.strip().lower() in ("false", "0"):
                nv = flip(val, True)
            if nv is not None and nv != val:
                lines[i] = ind + key + sep + nv + trail
                changes.append((key, val.strip(), nv))
        elif len(unknown) < 8 and any(h in k for h in UNKNOWN_HINTS):
            unknown.append("%s=%s" % (key, val.strip()))
    return "\n".join(lines), changes, unknown


# ---------- file access (adb or local folder) ----------
class Target:
    def __init__(self, mode, root, pkg=None):
        self.mode, self.root, self.pkg = mode, root, pkg

    def list_ini(self):
        if self.mode == "local":
            out = []
            for sub in ("inis", "gamesettings"):
                d = os.path.join(self.root, sub)
                if os.path.isdir(d):
                    out += [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(".ini")]
            return out
        cmd = "find '%s/inis' '%s/gamesettings' -name '*.ini' 2>/dev/null" % (self.root, self.root)
        rc, o = sh(["adb", "shell", cmd])
        return [l.strip() for l in o.splitlines() if l.strip().endswith(".ini")]

    def pull(self, remote, local):
        os.makedirs(os.path.dirname(local), exist_ok=True)
        if self.mode == "local":
            shutil.copy2(remote, local)
            return True
        return sh(["adb", "pull", remote, local])[0] == 0

    def push(self, local, remote):
        if self.mode == "local":
            shutil.copy2(local, remote)
            return True
        return sh(["adb", "push", local, remote])[0] == 0


def find_target(a):
    if a.dir:
        return Target("local", a.dir)
    if not ensure_adb():
        print("Could not link to the phone. Run 'zeron' again when Wireless debugging is on.")
        sys.exit(1)
    pkg = a.pkg
    if not pkg:
        rc, out = sh(["adb", "shell", "pm", "list", "packages"])
        pk = [l.split(":", 1)[1].strip() for l in out.splitlines() if l.startswith("package:")]
        cand = [p for p in pk if p in KNOWN or any(h in p.lower() for h in HINTS)]
        if not cand:
            print("No PS2 emulator found. Use:  zeron tune --pkg <package name>")
            sys.exit(1)
        pkg = next((p for p in cand if p in KNOWN), cand[0])
        print("Emulator:", pkg)
    for root in ("/sdcard/Android/data/%s/files" % pkg, "/storage/emulated/0/Android/data/%s/files" % pkg):
        rc, o = sh(["adb", "shell", "[ -d '%s' ] && echo y" % root])
        if "y" in o.split():
            return Target("adb", root, pkg)
    print("Could not see %s's data folder. Open the emulator once, then try again." % pkg)
    sys.exit(1)


def work_path(remote):
    return os.path.join(WORK, "%s_%s" % (hashlib.sha256(remote.encode()).hexdigest()[:8], os.path.basename(remote)))


def ensure_backup(man, t, remote, local):
    """Keep the TRUE original of every file (first time we touch it)."""
    if remote in man and os.path.exists(man[remote]["backup"]):
        return
    os.makedirs(BK, exist_ok=True)
    bpath = os.path.join(BK, "%s_%s" % (time.strftime("%Y%m%d-%H%M%S"), os.path.basename(work_path(remote))))
    shutil.copy2(local, bpath)
    man[remote] = {"backup": bpath, "mode": t.mode}
    save_man(man)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as f:
        return f.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as f:
        f.write(text)


def load_results():
    try:
        with open(RESULTS) as f:
            return json.load(f)
    except Exception:
        return {}


def save_result(key, data):
    r = load_results()
    r[key] = data
    os.makedirs(DIR, exist_ok=True)
    with open(RESULTS, "w") as f:
        json.dump(r, f, indent=1)


def pick_level(a, t):
    ram, cores, ghz = device_facts()
    res = load_results().get(t.pkg or "local")
    if a.profile != "auto":
        lvl = PROFILES[a.profile]
        print("Level:", LADDER[lvl], "(your choice)")
    elif res and "best_level" in res:
        lvl = res["best_level"]
        print("Level:", LADDER[lvl], "(learned from your last 'zeron smooth' test)")
    else:
        p, why, cores = auto_profile()
        lvl = PROFILES[p]
        print("Level:", LADDER[lvl], "-", why)
    return lvl, cores


def cmd_tune(a, t=None):
    t = t or find_target(a)
    level, cores = pick_level(a, t)
    return do_tune(t, level, cores)


def do_tune(t, level, cores, renderer=None):
    files = t.list_ini()
    if not files:
        print("No settings files found under %s. Start the emulator once, close it, then run again." % t.root)
        return 1
    man = load_man()
    total = 0
    for remote in files:
        name = os.path.basename(remote)
        local = work_path(remote)
        if not t.pull(remote, local):
            print("  ! could not read", name)
            continue
        ensure_backup(man, t, remote, local)
        new, changes, unknown = tune_text(read_text(local), level, cores, renderer)
        if not changes:
            print("  %s: %s" % (name, ("left alone (scale unknown): " + ", ".join(unknown)) if unknown else "nothing to change"))
            continue
        write_text(local, new)
        if t.push(local, remote):
            total += len(changes)
            print("  %s:" % name)
            for k, o, n in changes:
                print("     %s: %s -> %s" % (k, o, n))
            if unknown:
                print("     left alone (scale unknown): %s" % ", ".join(unknown))
        else:
            print("  ! could not write", name, "(is the emulator running? close it first)")
    print("Done: %d value(s) changed. Undo any time with:  zeron restore" % total)
    if total == 0:
        print("If nothing changed, your emulator may use different setting names. Send the 'left alone' lines to Claude.")
    return 0


# ---------- real FPS measurement through adb (SurfaceFlinger) ----------
def sf_layers(pkg):
    rc, o = sh(["adb", "shell", "dumpsys SurfaceFlinger --list"])
    ls = [l.strip() for l in o.splitlines() if pkg in l]
    sv = [l for l in ls if "SurfaceView" in l]
    return sv or ls


def parse_latency(text):
    """'dumpsys SurfaceFlinger --latency' -> list of actual-present timestamps (ns). Invalid rows are dropped."""
    out = []
    for l in text.strip().splitlines()[1:]:
        p = l.split()
        if len(p) >= 3:
            try:
                v = int(p[1])
            except ValueError:
                continue
            if 0 < v < 9000000000000000000:
                out.append(v)
    return out


def iv_stats(iv, minn=30):
    iv = [x for x in iv if 0 < x < 1.0]
    if len(iv) < minn:
        return None
    srt = sorted(iv)
    med = srt[len(srt) // 2]
    p99 = srt[min(len(srt) - 1, int(len(srt) * 0.99))]
    return {"avg": len(iv) / sum(iv), "low1": 1.0 / p99,
            "stutter_pct": 100.0 * sum(1 for x in iv if x > 2 * med) / len(iv), "frames": len(iv)}


def fps_stats(stamps):
    s = sorted(set(stamps))
    return iv_stats([(b - a) / 1e9 for a, b in zip(s, s[1:])])


class Frames:
    """Collects frame gaps from overlapping 'latency' dumps. Gaps are only taken INSIDE one dump, so a slow poll
    (the Shizuku route is slower) can never create fake long gaps."""
    def __init__(self):
        self.seen, self.iv = set(), []

    def add(self, text):
        lst = sorted(parse_latency(text))
        for a, b in zip(lst, lst[1:]):
            d = (b - a) / 1e9
            if b not in self.seen and 0 < d < 1.0:
                self.iv.append(d)
        self.seen.update(lst)


def measure(pkg, seconds):
    layers = sf_layers(pkg)
    if not layers:
        return None
    layer = layers[0].replace("'", "")
    fr, end, i, tmax = Frames(), time.time() + seconds, 0, 0
    while time.time() < end:
        rc, o = sh(["adb", "shell", "dumpsys SurfaceFlinger --latency '%s'" % layer], timeout=20)
        if rc == 0:
            fr.add(o)
        if i % 5 == 0:
            ts = thermal_status()
            if ts is not None:
                tmax = max(tmax, ts)
        i += 1
        time.sleep(1.0)
    st = iv_stats(fr.iv)
    if st:
        st["thermal_max"] = tmax
    return st


def verdict(st, ref):
    if st is None:
        return "unknown"
    if st.get("manual"):
        return "smooth" if st["avg"] >= 0.97 * ref else "almost" if st["avg"] >= 0.9 * ref else "slow"
    if st["avg"] >= 0.97 * ref and st["low1"] >= 0.80 * ref and st["stutter_pct"] <= 3:
        return "smooth"
    return "almost" if st["avg"] >= 0.90 * ref else "slow"


def apply_level(t, base, level, cores):
    n = 0
    for remote, text in base.items():
        new, changes, unknown = tune_text(text, level, cores)
        loc = work_path(remote)
        write_text(loc, new)
        if t.push(loc, remote):
            n += len(changes)
    return n


SYSTEM = os.path.join(DIR, "system.json")


def batt():
    rc, o = sh(["adb", "shell", "dumpsys battery"])
    if rc != 0:
        return None
    m = re.search(r"temperature:\s*(-?\d+)", o)
    l = re.search(r"level:\s*(\d+)", o)
    if not m:
        return None
    return {"temp": int(m.group(1)) / 10.0, "level": int(l.group(1)) if l else None,
            "powered": bool(re.search(r"(AC|USB|Wireless) powered: true", o))}


def thermal_status():
    rc, o = sh(["adb", "shell", "dumpsys thermalservice"])
    m = re.search(r"Thermal Status:\s*(\d+)", o)
    return int(m.group(1)) if (rc == 0 and m) else None


def cool_down(hot=40.0, ok=38.0, max_wait=300):
    """A hot phone throttles and makes later tests look worse than they are, so wait for it to cool first."""
    b = batt()
    if not b or b["temp"] < hot:
        return
    print("   Phone is %.1f C. Waiting until it is under %.0f C so the test is fair (max %d s)..." % (b["temp"], ok, max_wait))
    end = time.time() + max_wait
    while time.time() < end:
        time.sleep(20)
        b = batt()
        if not b or b["temp"] <= ok:
            break
        print("   ...%.1f C" % b["temp"])


def sget(key):
    rc, o = sh(["adb", "shell", "settings get global %s" % key])
    return o.strip() if rc == 0 else None


def system_tweaks(pkg):
    """Real Android-level helpers through adb. Recorded, and undone by 'zeron restore'."""
    try:
        with open(SYSTEM) as f:
            saved = json.load(f)
    except Exception:
        saved = {}
    notes = []
    lp = sget("low_power")
    if lp == "1":
        saved.setdefault("low_power", "1")
        rc, _ = sh(["adb", "shell", "settings put global low_power 0"])
        notes.append("Battery saver was ON (it slows the CPU) -> turned OFF" if rc == 0 else "! Battery saver is ON and could not be turned off: turn it off by hand")
    elif lp == "0":
        notes.append("Battery saver: off (good)")
    rc, o = sh(["adb", "shell", "cmd game set --mode performance --user 0 %s" % pkg])
    if rc == 0 and not re.search(r"(?i)error|unknown|exception|usage", o):
        saved["game_mode"] = pkg
        notes.append("Game mode: Performance requested (some phone makers ignore it)")
    else:
        notes.append("Game mode: not supported on this phone (skipped)")
    rc, o = sh(["adb", "shell", "dumpsys deviceidle whitelist"])
    if rc == 0 and pkg not in o:
        rc2, o2 = sh(["adb", "shell", "dumpsys deviceidle whitelist +%s" % pkg])
        if rc2 == 0 and "Added" in o2:
            saved["doze_pkg"] = pkg
            notes.append("Battery optimization: emulator exempted so Android will not pause it")
    ph = sget("settings_enable_monitor_phantom_procs")
    if ph in ("1", "true", "null", None) and "phantom" not in saved:
        rc, _ = sh(["adb", "shell", "settings put global settings_enable_monitor_phantom_procs false"])
        if rc == 0:
            saved["phantom"] = ph or "null"
            notes.append("Termux protected from being closed by Android while it watches your game")
    os.makedirs(DIR, exist_ok=True)
    with open(SYSTEM, "w") as f:
        json.dump(saved, f)
    return notes


def restore_system():
    try:
        with open(SYSTEM) as f:
            saved = json.load(f)
    except Exception:
        return []
    out = []
    if saved.get("low_power") == "1":
        sh(["adb", "shell", "settings put global low_power 1"]); out.append("Battery saver turned back ON")
    if saved.get("game_mode"):
        sh(["adb", "shell", "cmd game set --mode standard --user 0 %s" % saved["game_mode"]]); out.append("Game mode back to standard")
    if saved.get("doze_pkg"):
        sh(["adb", "shell", "dumpsys deviceidle whitelist -%s" % saved["doze_pkg"]]); out.append("Battery optimization restored")
    if saved.get("phantom"):
        v = saved["phantom"]
        sh(["adb", "shell", "settings delete global settings_enable_monitor_phantom_procs" if v == "null" else "settings put global settings_enable_monitor_phantom_procs %s" % v])
    try:
        os.remove(SYSTEM)
    except OSError:
        pass
    return out


def cmd_doctor(a):
    ram, cores, ghz = device_facts()
    print("Chip: %d cores, max %s, RAM %s GB" % (cores, "%.1f GHz" % ghz if ghz else "clock unknown", "%.1f" % ram if ram else "?"))
    try:
        for l in open("/proc/meminfo"):
            if l.startswith("MemAvailable"):
                mb = int(l.split()[1]) // 1024
                print("Free RAM now: %d MB%s" % (mb, "   ! low: close other apps" if mb < 1500 else ""))
    except Exception:
        pass
    try:
        gb = shutil.disk_usage(HOME).free / 1e9
        print("Free storage: %.1f GB%s" % (gb, "   ! low storage can cause stutter" if gb < 5 else ""))
    except Exception:
        pass
    if not adb_ready():
        print(ADB_HELP)
    else:
        b = batt()
        if b:
            print("Battery: %s%%, %.1f C, %s%s" % (b["level"], b["temp"], "charging" if b["powered"] else "on battery",
                  "   ! hot: expect throttling" if b["temp"] >= 40 else ""))
            if b["powered"]:
                print("   Tip: charging while gaming adds heat; if it gets hot, unplug or use a cooler.")
        ts = thermal_status()
        if ts is not None:
            print("Thermal state: %d (%s)%s" % (ts, ["normal", "light", "MODERATE", "SEVERE", "CRITICAL", "EMERGENCY", "SHUTDOWN"][min(ts, 6)],
                  "   ! CPU is being throttled right now" if ts >= 2 else ""))
        lp = sget("low_power")
        if lp == "1":
            print("! Battery saver is ON: it slows the CPU. 'zeron go' / 'zeron smooth' will turn it off for you.")
    print("Always: keep game files (ISO/CHD) on internal storage, not an SD card; remove thick cases; lower screen brightness.")
    return 0


def launch(pkg):
    sh(["adb", "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"])


def cmd_smooth(a):
    """Measure -> adjust -> measure. Finds the CLEANEST level that still runs at full speed on THIS phone."""
    if a.dir:
        print("'smooth' needs adb (it measures real speed). Use 'tune --dir' for a plain edit.")
        return 1
    t = find_target(a)
    pkg = t.pkg
    ref = 50.0 if a.region == "pal" else 59.94
    ram, cores, ghz = device_facts()
    p, why, cores = auto_profile()
    start = a.start if a.start is not None else max(0, PROFILES[p] - 1)
    top = 4 if a.risky else 3
    files = t.list_ini()
    if not files:
        print("No settings files found. Start the emulator once, close it, then run again.")
        return 1
    sh(["adb", "shell", "am", "force-stop", pkg])
    man, base = load_man(), {}
    for r in files:
        loc = work_path(r)
        if t.pull(r, loc):
            ensure_backup(man, t, r, loc)
            base[r] = read_text(loc)
    if not a.no_system:
        for n in system_tweaks(pkg):
            print(" *", n)
    b = batt()
    if b:
        print(" * Battery %s%%, %.1f C" % (b["level"], b["temp"]))
    print("""
SMOOTH TEST - how it works
 * It tries the cleanest settings first and only gets lighter if your phone can't keep full speed.
 * Each round: it applies a level, opens the emulator, YOU load the same scene (a save state is best),
   press Enter, and it measures real frame speed for %d seconds.
 * Full speed = about %.0f FPS output (%s). Games that run at 30 FPS inside still present at this rate.
 * If the phone is hot, it waits for it to cool; if heat or first-time hitches spoil a result it retests.
 * Ctrl+C stops any time; 'zeron restore' returns your original settings.
""" % (a.seconds, ref, "PAL" if a.region == "pal" else "NTSC"))
    tested, retested, level = [], set(), start
    try:
        while True:
            sh(["adb", "shell", "am", "force-stop", pkg])
            cool_down()
            n = apply_level(t, base, level, cores)
            print("=== Level %d: %s  (%d value(s) changed) ===" % (level, LADDER[level], n))
            launch(pkg)
            input("Load your scene, then press Enter to measure... ")
            st = measure(pkg, a.seconds)
            if st is None:
                x = input("Android would not give frame data. Type the FPS/speed you see in the emulator (or Enter to skip): ").strip()
                try:
                    v = float(x.replace("%", ""))
                    if "%" in x or v > 70:
                        v = v * ref / 100.0
                    st = {"avg": v, "low1": v, "stutter_pct": 0.0, "frames": 0, "manual": True}
                except ValueError:
                    st = None
            v = verdict(st, ref)
            if st:
                print("   avg %.1f FPS | 1%% low %.1f | stutter frames %.1f%%  -> %s" % (st["avg"], st["low1"], st["stutter_pct"], v.upper()))
                if st.get("thermal_max", 0) >= 2:
                    print("   ! the phone was throttling (hot) during this test")
            else:
                print("   no measurement -> UNKNOWN")
            if v != "smooth" and st and st.get("thermal_max", 0) >= 2 and (level, "heat") not in retested:
                retested.add((level, "heat"))
                print("   Heat can fake a bad result: cooling down and retesting this level once.\n")
                continue
            hitch = bool(st) and not st.get("manual") and st["avg"] >= 0.97 * ref and (st["low1"] < 0.80 * ref or st["stutter_pct"] > 3)
            if hitch and (level, "hitch") not in retested:
                retested.add((level, "hitch"))
                print("   Speed is fine but there are hitches (often shaders compiling the first time). Retesting once after warm-up.\n")
                continue
            tested.append((level, st, v))
            if v == "smooth" or level >= top:
                break
            level += 1
            print("   Not smooth yet - trying a lighter level.\n")
    except KeyboardInterrupt:
        print("\nStopped. Current settings stay; undo with: zeron restore")
        return 130
    rank = {"smooth": 3, "almost": 2, "slow": 1, "unknown": 0}
    smooth = [x for x in tested if x[2] == "smooth"]
    measured = [x for x in tested if x[1]]
    if smooth:
        best = smooth[0][0]
        print("\nRESULT: Level %d (%s) runs smooth - and it is the cleanest level that does." % (best, LADDER[best]))
    elif measured:
        bx = max(measured, key=lambda x: (rank[x[2]], x[1]["low1"]))
        best = bx[0]
        print("\nRESULT: no level reached full speed on this game. Smoothest measured: Level %d (%s), %.1f FPS (1%% low %.1f)."
              % (best, LADDER[best], bx[1]["avg"], bx[1]["low1"]))
        if any(x[1].get("thermal_max", 0) >= 2 for x in measured):
            print("Heat was a factor: remove the case, lower brightness, unplug the charger, let it cool, then run 'zeron smooth' again.")
        else:
            print("This phone's chip is the limit for this game; try the other renderer (Vulkan/OpenGL) in the emulator or a lighter game.")
    else:
        best = tested[-1][0]
        print("\nRESULT: could not measure. Keeping Level %d. Use the emulator's FPS counter to judge." % best)
    if best != tested[-1][0]:
        sh(["adb", "shell", "am", "force-stop", pkg])
        apply_level(t, base, best, cores)
    bst = dict((x[0], x[1]) for x in tested).get(best)
    save_result(pkg, {"best_level": best, "avg": bst["avg"] if bst else None, "time": time.strftime("%Y-%m-%d %H:%M")})
    print("Saved. From now on 'zeron go' uses this level automatically.")
    return 0


def restore_files(a):
    man = load_man()
    if not man:
        print("Nothing to restore.")
        return 0
    if a.dir:
        t = Target("local", a.dir)
    elif any(v.get("mode") == "adb" for v in man.values()):
        if not adb_ready():
            print(ADB_HELP)
            return 1
        t = Target("adb", "")
    else:
        t = Target("local", "")
    keep, n = {}, 0
    for remote, v in man.items():
        tt = Target(v.get("mode", "adb"), "")
        if os.path.exists(v["backup"]) and tt.push(v["backup"], remote):
            n += 1
        else:
            keep[remote] = v
    save_man(keep)
    print("Restored %d file(s)." % n + (" %d could not be restored (still listed)." % len(keep) if keep else ""))
    return 0


def pid_alive(pkg):
    rc, o = sh(["adb", "shell", "pidof %s" % pkg], timeout=15)
    return rc == 0 and o.strip() != ""


def watch(pkg, poll=1.0):
    """Hands-free: watches real frame speed while you play, ~10 s per window, until you close the game."""
    sh(["termux-wake-lock"])
    print("Watching your game. Just play normally and close it when you are done (keep Termux open in the background).")
    t0 = time.time()
    while time.time() - t0 < 90 and not pid_alive(pkg):
        time.sleep(2)
    fr, wins, cur, layer, miss, polls = Frames(), [], {"start": 0, "therm": 0, "n": 0}, None, 0, 0
    while True:
        if not pid_alive(pkg):
            miss += 1
            if miss >= 3:
                break
            time.sleep(2)
            continue
        miss = 0
        if layer is None or polls % 20 == 0:
            ls = sf_layers(pkg)
            layer = ls[0].replace("'", "") if ls else layer
        if layer:
            rc, o = sh(["adb", "shell", "dumpsys SurfaceFlinger --latency '%s'" % layer], timeout=20)
            if rc == 0:
                fr.add(o)
        if polls % 5 == 0:
            ts = thermal_status()
            if ts is not None:
                cur["therm"] = max(cur["therm"], ts)
        polls += 1
        cur["n"] += 1
        if cur["n"] >= 7:
            w = iv_stats(fr.iv[cur["start"]:], 20)
            if w:
                w["therm"] = cur["therm"]
                wins.append(w)
            cur = {"start": len(fr.iv), "therm": 0, "n": 0}
        time.sleep(poll)
    sh(["termux-wake-unlock"])
    return wins


def analyze_windows(wins, ref):
    if len(wins) < 12:                      # under ~2 minutes of play
        return {"verdict": "short", "windows": len(wins)}
    slow = [w for w in wins if w["avg"] < 0.9 * ref]
    hot = [w for w in slow if w["therm"] >= 2]
    cold = [w for w in slow if w["therm"] < 2]
    share, heat = len(cold) / len(wins), len(hot) / len(wins)
    avg = sum(w["avg"] for w in wins) / len(wins)
    if share <= 0.10 and heat <= 0.20:
        v = "smooth"
    elif share <= 0.10:
        v = "heat"
    else:
        v = "slow"
    return {"verdict": v, "windows": len(wins), "avg": avg, "slow_pct": 100 * share, "heat_pct": 100 * heat}


def adapt(pkg, level, verdict, top=3, avg=None, seen=None):
    """Learns from real play. On lag it first tries the OTHER renderer (Vulkan/OpenGL, often a big difference),
    then lighter settings; after two smooth games it tries cleaner graphics (never a level that lagged)."""
    r = load_results().get(pkg, {})
    data = dict(r)
    bad, streak, new = set(r.get("bad", [])), r.get("streak", 0), level
    renderer = r.get("renderer")
    cur = renderer if renderer is not None else seen
    pend = r.get("flip_pending")
    if verdict == "smooth":
        data.pop("flip_pending", None)
        streak += 1
        if streak >= 2 and level > 0 and (level - 1) not in bad:
            new, streak = level - 1, 0
            msg = "Two smooth games in a row: next time I will try cleaner graphics."
        else:
            msg = "Smooth! Keeping these settings."
    elif verdict == "slow":
        if pend is None and cur in RNAME and not r.get("flip_done_%d" % level):
            data["flip_done_%d" % level] = True
            data["flip_pending"] = {"from": cur, "prev_avg": avg}
            renderer, streak = 26 - cur, 0              # 12 <-> 14
            msg = "It lagged. Next launch I will try the %s renderer first (often a big difference) before making graphics lighter." % RNAME[renderer]
        else:
            pre = ""
            if pend is not None:
                data.pop("flip_pending", None)
                if avg is not None and pend.get("prev_avg") is not None and avg < pend["prev_avg"] - 2:
                    renderer = pend["from"]
                    pre = "The other renderer was slower, so I switched back. "
                else:
                    pre = "The other renderer did not fix it. "
            bad.add(level)
            streak = 0
            if level < top:
                new = level + 1
                msg = pre + "Next launch will use lighter settings automatically."
            else:
                msg = pre + "Still lagging at the lightest safe level: this phone's chip is the limit for this game."
    elif verdict == "heat":
        streak = 0
        msg = "The lag came from HEAT, not settings. Cool the phone (remove case, lower brightness, unplug charger). Settings kept."
    else:
        msg = "That session was too short to judge (need about 2 minutes). Nothing changed."
    data.update({"best_level": new, "streak": streak, "bad": sorted(bad), "time": time.strftime("%Y-%m-%d %H:%M")})
    if renderer is not None:
        data["renderer"] = renderer
    save_result(pkg, data)
    return new, msg


def cmd_auto(a):
    """The one command: link phone -> tune -> launch -> watch you play -> learn. No prompts after the first-time link."""
    print("ZERON BOOST - automatic mode")
    t = find_target(a)
    pkg = t.pkg
    ref = 50.0 if getattr(a, "region", "ntsc") == "pal" else 59.94
    ram, cores, ghz = device_facts()
    res = load_results().get(pkg, {})
    if "best_level" in res:
        level, why = res["best_level"], "learned from your earlier games"
    else:
        p, why, cores = auto_profile()
        level = PROFILES[p]
    print("Settings level: %s (%s)" % (LADDER[level], why))
    b = batt()
    if b:
        print("Battery %s%%, %.1f C" % (b["level"], b["temp"]))
        cool_down()
    renderer = res.get("renderer")
    if renderer in RNAME:
        print("Renderer: %s%s" % (RNAME[renderer], " (testing it because the last game lagged)" if res.get("flip_pending") else ""))
    SEEN.clear()
    if do_tune(t, level, cores, renderer) != 0:
        return 1
    if not getattr(a, "no_system", False):
        for n in system_tweaks(pkg):
            print(" *", n)
    sh(["adb", "shell", "am", "force-stop", pkg])
    launch(pkg)
    wins = watch(pkg)
    an = analyze_windows(wins, ref)
    new, msg = adapt(pkg, level, an["verdict"], avg=an.get("avg"), seen=SEEN.get("renderer"))
    if an["verdict"] != "short":
        print("\nSession: %d windows, average %.1f FPS output, %.0f%% of the time slow (not heat), %.0f%% slow from heat."
              % (an["windows"], an["avg"], an["slow_pct"], an["heat_pct"]))
    print(msg)
    print("Run 'zeron' again any time. 'zeron restore' puts your original settings back.")
    return 0


def cmd_restore(a):
    rc = restore_files(a)
    if os.path.exists(SYSTEM):
        if adb_ready():
            for l in restore_system():
                print(l)
        else:
            print("Phone-level tweaks are still recorded; reconnect adb and run 'zeron restore' again to undo them.")
    return rc


def cmd_status(a):
    p, why, cores = auto_profile()
    print("Suggested profile:", p.upper(), "-", why)
    print("adb connected:", "yes" if adb_ready() else "NO")
    if not adb_ready():
        print(ADB_HELP)
    print("Backups listed:", len(load_man()))
    return 0


def cmd_pair(a):
    rc, o = sh(["adb", "pair", "localhost:%s" % a.port, a.code])
    print(o.strip())
    return rc


def cmd_connect(a):
    rc, o = sh(["adb", "connect", "localhost:%s" % a.port])
    print(o.strip())
    return rc


def cmd_go(a):
    t = find_target(a)
    rc = cmd_tune(a, t)
    if rc != 0:
        return rc
    if not a.no_system:
        for n in system_tweaks(t.pkg):
            print(" *", n)
    sh(["adb", "shell", "am", "force-stop", t.pkg])
    launch(t.pkg)
    print("Launched", t.pkg, "- the ZERON BOOST overlay appears by itself if you started it in the app.")
    return 0


def cmd_app(a):
    rc, o = sh(["am", "start", "-n", APP + "/.MainActivity"])
    print("Opened ZERON BOOST app." if rc == 0 else "Open the ZERON BOOST app from your app drawer. (" + o.strip()[:80] + ")")
    return 0


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "zeron"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def cmd_update(a):
    try:
        repo = open(REPO_FILE).read().strip()
    except Exception:
        print("No repo saved. Re-run the install command.")
        return 1
    base = "https://github.com/%s/releases/download/latest" % repo
    download(base + "/zeron.py", os.path.join(DIR, "zeron.py"))
    apk = os.path.join(HOME, "ZeronBoost.apk")
    download(base + "/ZeronBoost.apk", apk)
    print("Updated tool. Opening installer for the app...")
    sh(["termux-open", apk])
    return 0


def main():
    ap = argparse.ArgumentParser(prog="zeron", description="ZERON BOOST for Termux")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--profile", default="auto", choices=["auto"] + list(PROFILES))
        p.add_argument("--pkg")
        p.add_argument("--dir", help="folder that contains inis/ (for rooted/old Android)")
        p.add_argument("--no-system", action="store_true", help="do not change phone-level settings (battery saver, game mode)")
    for n, f, h in (("tune", cmd_tune, "tune emulator settings"), ("go", cmd_go, "tune, then launch the emulator")):
        p = sub.add_parser(n, help=h); common(p); p.set_defaults(f=f)
    p = sub.add_parser("smooth", help="measure real speed and find the cleanest settings that run smooth")
    common(p); p.add_argument("--region", default="ntsc", choices=["ntsc", "pal"]); p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--start", type=int, choices=range(0, 5)); p.add_argument("--risky", action="store_true", help="allow level 4 (may glitch)")
    p.set_defaults(f=cmd_smooth)
    p = sub.add_parser("restore", help="put original settings back"); p.add_argument("--dir"); p.set_defaults(f=cmd_restore)
    p = sub.add_parser("auto", help="EVERYTHING automatically (same as typing just: zeron)")
    common(p); p.add_argument("--region", default="ntsc", choices=["ntsc", "pal"]); p.set_defaults(f=cmd_auto)
    p = sub.add_parser("setup", help="link this phone's adb (one time)"); p.set_defaults(f=lambda a: 0 if ensure_adb() else 1)
    p = sub.add_parser("status", help="show device facts and adb state"); p.set_defaults(f=cmd_status)
    p = sub.add_parser("doctor", help="check heat, battery saver, RAM and storage"); p.set_defaults(f=cmd_doctor)
    p = sub.add_parser("pair", help="pair adb"); p.add_argument("port"); p.add_argument("code"); p.set_defaults(f=cmd_pair)
    p = sub.add_parser("connect", help="connect adb"); p.add_argument("port"); p.set_defaults(f=cmd_connect)
    p = sub.add_parser("app", help="open the ZERON BOOST app"); p.set_defaults(f=cmd_app)
    p = sub.add_parser("update", help="download newest tool + app"); p.set_defaults(f=cmd_update)
    a = ap.parse_args()
    os.makedirs(DIR, exist_ok=True)
    if not getattr(a, "f", None):
        return cmd_auto(argparse.Namespace(profile="auto", pkg=None, dir=None, no_system=False, region="ntsc"))
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main() or 0)
