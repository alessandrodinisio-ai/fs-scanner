# Proposal: Windows Support for fs-scanner

## Classificazione dei controlli attuali

### Controlli generali (cross-platform)

Questi funzionano già su qualsiasi OS senza modifiche:

| Componente | Dettaglio |
|------------|-----------|
| Scanner parallelo | `os.scandir()` + `ThreadPoolExecutor` — cross-platform |
| Categorizer | Mapping estensione → categoria — identico ovunque |
| Modelli dati | Dataclass Python — nessuna dipendenza OS |
| JSON reporter | Serializzazione deterministica — cross-platform |
| HTML dashboard | D3.js self-contained — funziona su qualsiasi browser |
| Terminal reporter | `rich` library — cross-platform |
| Comparison | Diff tra scan JSON — cross-platform |
| Config system | YAML + CLI flags — cross-platform |
| Progress tracker | `rich.progress` — cross-platform |
| Depth limiting | Logica Python pura |
| Min-size filtering | Logica Python pura |
| Symlink detection | `os.path.islink()` / `entry.is_symlink()` — cross-platform |
| Git orphan detection | `git count-objects`, `git rev-list` — funziona ovunque con git installato |

### Controlli specifici macOS

| Componente | Cosa fa su macOS | Equivalente Windows |
|------------|------------------|---------------------|
| **Exclusion paths** | Esclude /System, /Library, /usr, /bin, /sbin, /private, /var, /cores | Escludere C:\Windows, C:\Program Files, C:\ProgramData |
| **Excluded dir names** | .Spotlight-V100, .fseventsd, .Trashes | $Recycle.Bin, System Volume Information |
| **Excluded files** | .DS_Store | Thumbs.db, desktop.ini |
| **Sensitive dirs** | ~/.ssh, ~/.gnupg, ~/.aws/credentials | %USERPROFILE%\.ssh, %APPDATA%\gnupg |
| **Cache rules paths** | ~/Library/Caches/*, ~/Library/Logs | %LOCALAPPDATA%\Temp, %LOCALAPPDATA%\<App>\Cache |
| **Thunderbird path** | ~/Library/Thunderbird | %APPDATA%\Thunderbird |
| **Chrome cache** | ~/Library/Caches/Google | %LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache |
| **npm cache** | ~/.npm/_cacache | %APPDATA%\npm-cache |
| **pip cache** | ~/Library/Caches/pip | %LOCALAPPDATA%\pip\Cache |
| **Maven cache** | ~/.m2/repository | %USERPROFILE%\.m2\repository (invariato) |
| **Podman/Docker** | ~/.local/share/containers, ~/Library/Containers/com.docker.docker | %LOCALAPPDATA%\Docker, WSL2 disk |
| **App leftovers** | ~/Library/Application Support, ~/Library/Preferences/*.plist | %APPDATA%, %LOCALAPPDATA%, Registry |
| **Launch agents** | ~/Library/LaunchAgents/*.plist | Task Scheduler (schtasks), Startup folder |
| **Homebrew** | /opt/homebrew, /usr/local/Homebrew | Chocolatey (C:\ProgramData\chocolatey), Scoop (~\scoop), winget |
| **Xcode** | ~/Library/Developer/Xcode/DerivedData | Visual Studio: %LOCALAPPDATA%\Microsoft\VisualStudio\*\ComponentModelCache |
| **Mail** | ~/Library/Mail | %LOCALAPPDATA%\Microsoft\Outlook\*.ost |
| **iCloud** | ~/Library/Mobile Documents | %LOCALAPPDATA%\Microsoft\OneDrive (equivalent) |
| **Time Machine** | tmutil listlocalsnapshots | Volume Shadow Copies (vssadmin list shadows) |
| **Spotlight metadata** | mdls (kMDItemLastUsedDate) | Windows Search index (non facilmente queryabile) |
| **Dir size (TCC workaround)** | subprocess /usr/bin/du | Non necessario su Windows (no TCC) |
| **File permissions 600** | os.chmod(path, 0o600) | Win32 ACL (o skip su Windows) |

---

## Strategia di implementazione

### Approccio: Platform Abstraction Layer

```
src/fs_scanner/
├── platform/
│   ├── __init__.py        # Detect OS, export platform module
│   ├── base.py            # Abstract base class
│   ├── macos.py           # macOS-specific implementations
│   └── windows.py         # Windows-specific implementations
```

#### Interface comune

```python
# platform/base.py
from abc import ABC, abstractmethod
from pathlib import Path

class PlatformConfig(ABC):
    @abstractmethod
    def system_exclusion_paths(self) -> tuple[str, ...]: ...

    @abstractmethod
    def excluded_dir_names(self) -> tuple[str, ...]: ...

    @abstractmethod
    def excluded_file_names(self) -> tuple[str, ...]: ...

    @abstractmethod
    def sensitive_dirs(self) -> tuple[str, ...]: ...

    @abstractmethod
    def cache_rules(self, home: Path) -> list[dict]: ...

    @abstractmethod
    def dir_size(self, path: Path) -> int: ...

    @abstractmethod
    def package_manager_suggestions(self, home: Path) -> list: ...
```

### Fase 1: Refactoring (senza rompere macOS)

1. Estrarre costanti macOS-specifiche in `platform/macos.py`
2. Creare `platform/__init__.py` che auto-detect l'OS e importa il modulo giusto
3. Modificare `exclusions.py` per usare `platform.system_exclusion_paths()` invece di tuple hardcoded
4. Modificare `cache_rules.py` per usare `platform.cache_rules(home)` invece di path hardcoded

### Fase 2: Implementazione Windows

#### Exclusion Engine Windows

```python
# platform/windows.py
class WindowsPlatform(PlatformConfig):
    def system_exclusion_paths(self):
        return (
            r"C:\Windows",
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"C:\ProgramData",
            r"C:\$Recycle.Bin",
            r"C:\System Volume Information",
            r"C:\Recovery",
        )

    def excluded_dir_names(self):
        return ("$Recycle.Bin", "System Volume Information", "$WINDOWS.~BT")

    def excluded_file_names(self):
        return ("Thumbs.db", "desktop.ini", "pagefile.sys", "hiberfil.sys")
```

#### Cache Rules Windows

```python
def cache_rules(self, home: Path):
    local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    temp = Path(os.environ.get("TEMP", local / "Temp"))

    return [
        {"path": temp, "category": "Windows Temp", "risk": "safe",
         "reason": "Temporary files. Run: del /s /q %TEMP%\\*"},
        {"path": local / "Google" / "Chrome" / "User Data" / "Default" / "Cache",
         "category": "Chrome Cache", "risk": "safe"},
        {"path": local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache",
         "category": "Edge Cache", "risk": "safe"},
        {"path": roaming / "npm-cache",
         "category": "npm Cache", "risk": "safe",
         "reason": "Run: npm cache clean --force"},
        {"path": local / "pip" / "Cache",
         "category": "pip Cache", "risk": "safe",
         "reason": "Run: pip cache purge"},
        {"path": home / ".m2" / "repository",
         "category": "Maven Cache", "risk": "safe"},
        {"path": home / ".gradle" / "caches",
         "category": "Gradle Cache", "risk": "safe"},
        {"path": local / "NuGet" / "Cache",
         "category": "NuGet Cache", "risk": "safe",
         "reason": "Run: dotnet nuget locals all --clear"},
        {"path": local / "Docker" / "wsl",
         "category": "Docker WSL Disk", "risk": "caution",
         "reason": "Docker Desktop WSL2 disk image. Run: docker system prune -a"},
        {"path": roaming / "Thunderbird" / "Profiles",
         "category": "Thunderbird Email", "risk": "risky"},
        {"path": local / "Microsoft" / "Outlook",
         "category": "Outlook Data", "risk": "risky"},
        {"path": local / "Packages",
         "category": "Windows Store Apps Cache", "risk": "caution"},
        # Visual Studio
        {"path": local / "Microsoft" / "VisualStudio",
         "category": "Visual Studio Cache", "risk": "safe"},
        # Windows Update
        {"path": Path(r"C:\Windows\SoftwareDistribution\Download"),
         "category": "Windows Update Cache", "risk": "safe",
         "reason": "Old update files. Run (admin): dism /online /cleanup-image /startcomponentcleanup"},
    ]
```

#### Package Manager Windows (equivalente Homebrew)

```python
# suggestions/package_managers.py
def find_suggestions_windows(home: Path):
    suggestions = []

    # Chocolatey
    choco = Path(r"C:\ProgramData\chocolatey\lib")
    if choco.is_dir():
        # Check for old package versions
        ...

    # Scoop
    scoop = home / "scoop" / "cache"
    if scoop.is_dir():
        size = dir_size(scoop)
        suggestions.append(Suggestion(
            path=str(scoop), size=size,
            category="Scoop Cache",
            reason="Run: scoop cache rm *",
            risk_level=RiskLevel.SAFE))

    # winget
    winget_cache = local / "Microsoft" / "WinGet" / "Cache"
    ...

    return suggestions
```

#### Dir Size Windows

```python
def dir_size(self, path: Path) -> int:
    """Su Windows non serve il workaround du/TCC — os.walk funziona."""
    total = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                try:
                    total += os.path.getsize(os.path.join(dirpath, f))
                except (PermissionError, OSError):
                    pass
    except (PermissionError, OSError):
        pass
    return total
```

#### Volume Shadow Copies (equivalente Time Machine)

```python
# suggestions/shadow_copies.py (Windows)
def find_suggestions():
    """Detect Windows Volume Shadow Copies."""
    result = subprocess.run(
        ["vssadmin", "list", "shadows"],
        capture_output=True, text=True, timeout=10
    )
    # Parse output for shadow copy count and estimated size
    ...
```

---

## Mapping riepilogativo macOS → Windows

| Concetto macOS | Equivalente Windows |
|---------------|---------------------|
| ~/Library | %APPDATA%, %LOCALAPPDATA% |
| ~/Library/Caches | %LOCALAPPDATA%\Temp, %LOCALAPPDATA%\<App>\Cache |
| ~/Library/Application Support | %APPDATA%\<App>, %LOCALAPPDATA%\<App> |
| ~/Library/Logs | %LOCALAPPDATA%\CrashDumps, Event Viewer |
| ~/Library/LaunchAgents | Task Scheduler, Startup folder |
| ~/Library/Preferences/*.plist | Registry HKCU\Software\<App> |
| /Applications/*.app | C:\Program Files\*, %LOCALAPPDATA%\Programs\* |
| Homebrew | Chocolatey, Scoop, winget |
| Xcode DerivedData | Visual Studio cache, .vs/ folders |
| Time Machine (tmutil) | Volume Shadow Copy (vssadmin) |
| Spotlight (mdls) | Windows Search index (non esposto) |
| .DS_Store | Thumbs.db, desktop.ini |
| SIP/TCC protection | UAC, protected system dirs |
| os.chmod 0o600 | Win32 security ACL (icacls) |
| /usr/bin/du subprocess | os.walk diretto (no TCC problem) |

---

## Piano di rilascio

### v0.2 — Refactoring platform layer
- Estrarre costanti OS-specifiche in `platform/`
- Zero breaking changes su macOS
- Test: verificare che tutti i test passano invariati

### v0.3 — Windows basic support
- Exclusion engine Windows
- Cache rules Windows (Temp, Chrome, Edge, pip, npm, Maven)
- Scanner con `os.walk` diretto (no workaround du)
- Terminal + JSON output

### v0.4 — Windows advanced
- Package manager detection (Chocolatey, Scoop, winget)
- Visual Studio cache detection
- Windows Update cleanup suggestions
- Outlook/Thunderbird detection
- Volume Shadow Copies
- HTML dashboard (invariato, già cross-platform)

### v0.5 — Linux support (bonus)
- XDG paths (~/.cache, ~/.local/share)
- apt/dnf/pacman cache detection
- systemd journal logs
- Snap/Flatpak cache

---

## Effort stimato

| Fase | Giorni | Note |
|------|--------|------|
| Refactoring platform layer | 1-2 | Meccanico, nessun rischio |
| Windows exclusions + cache rules | 1 | Path mapping diretto |
| Windows package managers | 1 | Chocolatey/Scoop/winget |
| Testing su Windows | 1-2 | Serve una VM/macchina Windows |
| **Totale** | **4-7 giorni** | |

## Rischi

- **File locking**: su Windows i file aperti non possono essere misurati — servono try/except per `PermissionError` e `OSError` con errno specifici
- **Long paths**: Windows ha limite 260 char di default — usare `\\?\` prefix o abilitare long paths in manifest
- **Encoding**: path Windows possono avere caratteri non-UTF8 — usare `os.fsdecode` con gestione surrogati
- **Admin rights**: alcune directory richiedono UAC elevation — gestire come "permission denied" e continuare
