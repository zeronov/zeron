#!/data/data/com.termux/files/usr/bin/bash
# Run INSIDE the unzipped project folder. Creates a public repo and uploads everything (your token stays on this phone).
set -e
pkg install -y git curl
read -r -p "GitHub username: " GU </dev/tty
read -r -p "New repo name [zeron-boost-android]: " GR </dev/tty
GR="${GR:-zeron-boost-android}"
read -r -s -p "GitHub token (typing is hidden; needs 'repo' + 'workflow' access): " GT </dev/tty
echo
curl -s -o /dev/null -w "create repo: HTTP %{http_code}\n" -H "Authorization: token $GT" -d "{\"name\":\"$GR\",\"private\":false}" https://api.github.com/user/repos
git init -q -b main 2>/dev/null || git init -q
git config user.email "zeron@example.com"; git config user.name "$GU"
git add -A
git commit -q -m "ZERON BOOST Android" || true
git branch -M main
git push -f "https://$GU:$GT@github.com/$GU/$GR.git" main
echo
echo "Uploaded. Open https://github.com/$GU/$GR/actions and wait for a green tick (about 5-10 minutes)."
echo "Then run:"
echo "curl -fsSL https://github.com/$GU/$GR/releases/download/latest/install.sh | ZB_REPO=$GU/$GR bash"
