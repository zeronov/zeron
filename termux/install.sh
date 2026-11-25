#!/data/data/com.termux/files/usr/bin/bash
# ZERON BOOST installer for Termux. Run:
#   curl -fsSL https://github.com/USER/REPO/releases/download/latest/install.sh | ZB_REPO=USER/REPO bash
set -e
REPO="${ZB_REPO:-}"
if [ -z "$REPO" ]; then read -r -p "Your GitHub repo (user/name): " REPO </dev/tty; fi
mkdir -p "$HOME/.zeronboost"
echo "$REPO" > "$HOME/.zeronboost/repo"
echo "== Installing Termux packages =="
pkg install -y curl python android-tools termux-tools
BASE="https://github.com/$REPO/releases/download/latest"
echo "== Downloading tool and app =="
curl -fL "$BASE/zeron.py" -o "$HOME/.zeronboost/zeron.py"
curl -fL "$BASE/ZeronBoost.apk" -o "$HOME/ZeronBoost.apk"
printf '#!/data/data/com.termux/files/usr/bin/sh\nexec python "$HOME/.zeronboost/zeron.py" "$@"\n' > "$PREFIX/bin/zeron"
chmod +x "$PREFIX/bin/zeron"
echo
echo "Tool installed. After the app is installed and set up, just type:  zeron"
echo "Now opening the app installer. If Android blocks it, allow 'Install unknown apps' for Termux, then run: termux-open ~/ZeronBoost.apk"
termux-open "$HOME/ZeronBoost.apk" || true
