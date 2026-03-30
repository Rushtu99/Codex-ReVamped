# Publishing The Package

## 1. Initialize The Repo

```sh
cd /data/data/com.termux/files/home/codex-portable-setup
git init
git add .
git commit -m "Initial codex portable setup package"
```

## 2. Create A New Private Remote

Create a new empty private repository on your Git host, then add it:

```sh
git remote add origin <your-new-remote-url>
git branch -M main
git push -u origin main
```

## 3. Install On Another Machine

POSIX:

```sh
git clone <your-new-remote-url> codex-portable-setup
cd codex-portable-setup
./install.sh
./doctor.sh
```

Windows PowerShell:

```powershell
git clone <your-new-remote-url> codex-portable-setup
Set-Location codex-portable-setup
.\install.ps1
.\doctor.ps1
```

## 4. What To Keep Out Of Git

Do not commit any generated files from the target machine that contain secrets or live state, especially:

- `~/.codex/auth*.json`
- `~/.codex-lb/.env`
- `~/.codex-lb/store.db*`
- `~/.codex-lb/encryption.key`
