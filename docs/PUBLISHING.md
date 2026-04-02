# Publishing The Package

## 1. Prepare The Repo

```sh
cd /data/data/com.termux/files/home/tmp-codex-lb-setup-compare
git add .
git commit -m "Repackage as Codex-ReVamped"
```

## 2. Point At The Public Remote

Set the canonical repository remote:

```sh
git remote set-url origin git@github.com:Rushtu99/Codex-ReVamped.git
git branch -M main
git push -u origin main
```

## 3. Install On Another Machine

POSIX:

```sh
git clone git@github.com:Rushtu99/Codex-ReVamped.git ~/.codex-revamped
cd ~/.codex-revamped
./install.sh
./doctor.sh
```

Windows PowerShell:

```powershell
git clone git@github.com:Rushtu99/Codex-ReVamped.git $HOME\.codex-revamped
Set-Location $HOME\.codex-revamped
.\install.ps1
.\doctor.ps1
```

## 4. What To Keep Out Of Git

Do not commit any generated files from the target machine that contain secrets or live state, especially:

- `~/.codex/auth*.json`
- `~/.codex-lb/.env`
- `~/.codex-lb/store.db*`
- `~/.codex-lb/encryption.key`
- `~/.codex-revamped/accounts.seed.json`
- `~/.codex-revamped/runtime.env`
