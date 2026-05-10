import sys
import os
import json
import base64
import hashlib
import secrets
from urllib.parse import urlparse, parse_qs, unquote
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QTimer, QObject
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QPushButton,
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QProgressBar, QFrame, QStatusBar, QSizePolicy,
    QStackedWidget, QMenu, QFileDialog,
    QDialog, QWidgetAction, QSpinBox, QFormLayout,
    QDialogButtonBox, QScrollArea, QGroupBox, QStyle
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineDownloadRequest, QWebEnginePage
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QColor, QLinearGradient,
    QShortcut, QKeySequence
)

# ── Asset resolver ─────────────────────────────────────────────────────────────
def asset(filename):
    base = sys._MEIPASS if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", filename)

def _icon_data_url(filename):
    """Return a base64 data URL for a file in assets/, or None if missing."""
    try:
        with open(asset(filename), "rb") as f:
            data = f.read()
        ext  = filename.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg",
                "jpeg": "image/jpeg", "ico": "image/x-icon"}.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return None


VERSION          = "1.0.3"
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/kbnspacecmd/browser/master/version.json"

DATA_DIR = os.path.join(os.path.expanduser("~"), ".externo")
os.makedirs(DATA_DIR, exist_ok=True)
BOOKMARKS_FILE  = os.path.join(DATA_DIR, "bookmarks.json")   # guest fallback
SHORTCUTS_FILE  = os.path.join(DATA_DIR, "shortcuts.json")   # guest fallback
USERS_FILE      = os.path.join(DATA_DIR, "users.json")
SESSION_FILE    = os.path.join(DATA_DIR, "session.json")

def _user_data_file(name: str) -> str:
    """Return the correct data file path for the current user (or guest)."""
    user = UserManager.get().current_user() if UserManager._inst else None
    if user:
        d = os.path.join(DATA_DIR, "profiles", user)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, name)
    return os.path.join(DATA_DIR, name)

# ── Theme system ───────────────────────────────────────────────────────────────
THEMES = {
    "externo_dark": {
        "bg":        "#08121e",
        "titlebar":  "#0b1a30",
        "toolbar":   "#0d2040",
        "border":    "#163560",
        "field_bg":  "#060f1c",
        "accent":    "#00c8e8",
        "accent_hv": "#00a8c8",
        "accent2":   "#00e676",
        "text":      "#ddf2ff",
        "dim":       "#3a6888",
        "brand":     "#00e5ff",
        "close_hv":  "#c0392b",
    },
}
_active_theme = "externo_dark"

def T(key):
    return THEMES[_active_theme][key]

def _version_gt(a: str, b: str) -> bool:
    def parts(v):
        return [int(x) for x in v.strip().split(".")]
    try:
        return parts(a) > parts(b)
    except Exception:
        return False

def _si(name):
    sp = getattr(QStyle.StandardPixmap, name, None)
    if sp is None:
        return QIcon()
    return QApplication.style().standardIcon(sp)


# ── Landing page HTML ──────────────────────────────────────────────────────────
_LANDING_HTML_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>New Tab</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg:      #08121e;
    --card:    #0d1f38;
    --border:  #163560;
    --accent:  #00c8e8;
    --accent2: #00e676;
    --text:    #ddf2ff;
    --dim:     #5a82a8;
  }
  html, body {
    height: 100%; background: var(--bg); color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    overflow: hidden;
  }
  body {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    gap: 36px;
  }

  /* ── Logo ── */
  .logo-area { display: flex; flex-direction: column; align-items: center; gap: 14px; }
  .shield {
    width: 96px; height: 108px;
    background: linear-gradient(160deg, #00c8e8 0%, #00e676 100%);
    clip-path: polygon(8% 0%, 92% 0%, 100% 60%, 50% 100%, 0% 60%);
    display: flex; align-items: center; justify-content: center;
    font-size: 56px; font-weight: 900; color: #fff;
    letter-spacing: -2px;
    filter: drop-shadow(0 6px 24px rgba(0,200,120,.35));
    animation: float 4s ease-in-out infinite;
  }
  @keyframes float {
    0%, 100% { transform: translateY(0); }
    50%       { transform: translateY(-6px); }
  }
  .brand-name {
    font-size: 26px; font-weight: 800; letter-spacing: 5px;
    background: linear-gradient(90deg, #00c8e8, #00e676);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .tagline { font-size: 12px; color: var(--dim); letter-spacing: 2px; text-transform: uppercase; }

  /* ── Search ── */
  .search-wrap {
    width: min(580px, 88vw);
    display: flex; border-radius: 30px; overflow: hidden;
    border: 1.5px solid var(--border);
    background: var(--card);
    transition: border-color .2s, box-shadow .2s;
  }
  .search-wrap:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 4px rgba(0,200,232,.12);
  }
  #q {
    flex: 1; padding: 15px 22px; background: transparent;
    border: none; outline: none; color: var(--text); font-size: 15px;
  }
  #q::placeholder { color: var(--dim); }
  .go-btn {
    padding: 0 26px;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    border: none; cursor: pointer;
    color: #08121e; font-weight: 800; font-size: 14px; letter-spacing: .5px;
    transition: opacity .18s;
  }
  .go-btn:hover { opacity: .84; }

  /* ── Quick tiles ── */
  .tiles { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; max-width: 680px; }
  .tile {
    width: 86px; padding: 16px 8px 12px;
    display: flex; flex-direction: column; align-items: center; gap: 7px;
    background: var(--card); border: 1px solid var(--border); border-radius: 16px;
    text-decoration: none; color: var(--text);
    transition: background .16s, border-color .16s, transform .15s;
    cursor: pointer; position: relative;
  }
  .tile:hover { background: #122040; border-color: var(--accent); transform: translateY(-3px); }
  .tile-icon { width: 40px; height: 40px; border-radius: 10px; object-fit: contain; image-rendering: auto; }
  .tile-icon.hires { width: 52px; height: 52px; margin: -6px 0 -2px; object-fit: contain; }
  .tile-label { font-size: 11px; color: var(--dim); letter-spacing: .3px; text-align: center; }

  /* ── User shortcut tiles ── */
  .remove-btn {
    display: none; position: absolute; top: 5px; right: 5px;
    width: 18px; height: 18px; border-radius: 50%;
    background: rgba(192,57,43,.9); border: none;
    color: #fff; font-size: 11px; font-weight: bold; line-height: 18px;
    text-align: center; padding: 0; cursor: pointer;
    transition: background .15s;
  }
  .remove-btn:hover { background: #c0392b; }
  .user-tile:hover .remove-btn { display: block; }

  /* ── Add-shortcut tile ── */
  .add-tile { border-style: dashed; opacity: .6; }
  .add-tile:hover { opacity: 1; border-color: var(--accent2); }
  .add-icon {
    width: 40px; height: 40px; border-radius: 10px;
    border: 2px dashed var(--accent);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; color: var(--accent); font-weight: 300;
  }

  /* ── Footer ── */
  .footer {
    position: fixed; bottom: 16px;
    font-size: 11px; color: var(--border); letter-spacing: 1px;
  }
</style>
</head>
<body>

<div class="logo-area">
  <div class="shield">E</div>
  <div class="brand-name">EXTERNO BROWSER</div>
  <div class="tagline">Fast &bull; Private &bull; Yours</div>
</div>

<form class="search-wrap" id="sf">
  <input id="q" type="text" placeholder="Search Google or enter a URL&hellip;" autofocus autocomplete="off">
  <button type="submit" class="go-btn">Go</button>
</form>

<div class="tiles">
{tiles}
</div>

<div class="footer">2026 &mdash; Externo Browser. All rights reserved.</div>

<script>
document.getElementById('sf').addEventListener('submit', function(e) {
  e.preventDefault();
  var q = document.getElementById('q').value.trim();
  if (!q) return;
  if (/^https?:\\/\\//i.test(q)) {
    window.location.href = q;
  } else if (/^[\\w\\-]+\\.[\\w]{2,}(\\/|$)/.test(q)) {
    window.location.href = 'https://' + q;
  } else {
    window.location.href = 'https://www.google.com/search?q=' + encodeURIComponent(q);
  }
});
function removeShortcut(url) {
  window.location.href = 'externo://remove-shortcut?url=' + encodeURIComponent(url);
}
function addShortcut() {
  window.location.href = 'externo://add-shortcut';
}
</script>
</body>
</html>"""

_DEFAULT_TILES = [
    ("Google",   "https://google.com",   "google.com",  None),
    ("YouTube",  "https://youtube.com",  "youtube.com", None),
    ("GitHub",   "https://github.com",   "github.com",  None),
    ("Reddit",   "https://reddit.com",   "reddit.com",  None),
    ("X",        "https://x.com",        "x.com",       None),
    ("SunnyMC",  "https://sunnymc.net",  "sunnymc.net", "sunnymc_logo.png"),
]

def _build_landing_html():
    tiles = ""
    for label, url, domain, local_icon in _DEFAULT_TILES:
        if local_icon:
            src     = _icon_data_url(local_icon) or f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
            img_cls = "tile-icon hires"
        else:
            src     = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
            img_cls = "tile-icon"
        tiles += (
            f'  <a class="tile" href="{url}">\n'
            f'    <img class="{img_cls}" src="{src}" alt="{label}">\n'
            f'    <span class="tile-label">{label}</span>\n'
            f'  </a>\n'
        )
    for sc in ShortcutsManager.get().all():
        name   = sc["name"]
        url    = sc["url"]
        label  = (name[:11] + "…") if len(name) > 12 else name
        domain = urlparse(url).hostname or url
        favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=64"
        safe   = url.replace("'", "\\'")
        tiles += (
            f'  <div class="tile user-tile" onclick="location.href=\'{safe}\'">\n'
            f'    <img class="tile-icon" src="{favicon}" alt="{label}">\n'
            f'    <span class="tile-label">{label}</span>\n'
            f'    <button class="remove-btn" onclick="event.stopPropagation();removeShortcut(\'{safe}\')" title="Remove">×</button>\n'
            f'  </div>\n'
        )
    tiles += (
        '  <div class="tile add-tile" onclick="addShortcut()">\n'
        '    <div class="add-icon">+</div>\n'
        '    <span class="tile-label">Add shortcut</span>\n'
        '  </div>\n'
    )
    return _LANDING_HTML_TMPL.replace("{tiles}", tiles)


def _build_history_html():
    import time
    entries = HistoryManager.get().all()

    def _day_label(ts):
        now = time.time()
        age = now - ts
        if age < 86400:
            return "Today"
        if age < 172800:
            return "Yesterday"
        if age < 604800:
            return "Last 7 Days"
        return "Older"

    grouped: dict[str, list] = {}
    order = []
    for e in entries:
        label = _day_label(e["ts"])
        if label not in grouped:
            grouped[label] = []
            order.append(label)
        grouped[label].append(e)

    rows = ""
    for group in order:
        rows += f'<div class="group-label">{group}</div>\n'
        for e in grouped[group]:
            url    = e["url"].replace('"', "&quot;")
            title  = (e["title"] or e["url"])[:80].replace("<", "&lt;").replace(">", "&gt;")
            domain = urlparse(e["url"]).hostname or e["url"]
            ts_str = time.strftime("%H:%M", time.localtime(e["ts"]))
            favicon = f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
            safe_url = e["url"].replace("'", "\\'")
            rows += (
                f'<div class="row" onclick="location.href=\'{safe_url}\'">\n'
                f'  <img class="fav" src="{favicon}" alt="">\n'
                f'  <div class="info">\n'
                f'    <span class="title">{title}</span>\n'
                f'    <span class="url">{url}</span>\n'
                f'  </div>\n'
                f'  <span class="time">{ts_str}</span>\n'
                f'</div>\n'
            )

    empty = "" if entries else '<div class="empty">No browsing history yet.</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>History</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #08121e; color: #ddf2ff;
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
  }}
  .topbar {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 22px 48px 14px;
    border-bottom: 1px solid #163560;
    position: sticky; top: 0; background: #08121e; z-index: 10;
  }}
  .topbar h1 {{ font-size: 22px; font-weight: 700; color: #00c8e8; letter-spacing: 1px; }}
  .clear-btn {{
    background: #5a1a1a; color: #ff7070; border: none; border-radius: 8px;
    padding: 8px 20px; font-size: 13px; cursor: pointer; transition: background 0.15s;
  }}
  .clear-btn:hover {{ background: #c0392b; color: #fff; }}
  .content {{ max-width: 820px; margin: 0 auto; padding: 20px 24px 60px; }}
  .group-label {{
    font-size: 11px; font-weight: 700; letter-spacing: 2px;
    color: #3a6888; text-transform: uppercase;
    margin: 24px 0 8px; padding-bottom: 4px;
    border-bottom: 1px solid #163560;
  }}
  .row {{
    display: flex; align-items: center; gap: 14px;
    padding: 10px 14px; border-radius: 10px; cursor: pointer;
    transition: background 0.12s;
  }}
  .row:hover {{ background: #0d2040; }}
  .fav {{ width: 20px; height: 20px; border-radius: 4px; flex-shrink: 0; }}
  .info {{ flex: 1; overflow: hidden; }}
  .title {{ display: block; font-size: 13px; color: #ddf2ff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .url   {{ display: block; font-size: 11px; color: #3a6888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }}
  .time  {{ font-size: 11px; color: #3a6888; flex-shrink: 0; }}
  .empty {{ color: #3a6888; text-align: center; margin-top: 80px; font-size: 15px; }}
</style>
</head>
<body>
<div class="topbar">
  <h1>&#128336; History</h1>
  <button class="clear-btn" onclick="if(confirm('Clear all browsing history?'))location.href='externo://clear-history'">Clear All</button>
</div>
<div class="content">
{rows}{empty}
</div>
</body>
</html>"""


# ── Account manager ────────────────────────────────────────────────────────────
class AccountManager:
    _inst = None

    @classmethod
    def get(cls):
        if not cls._inst:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self.user = None
        self.syncing = False

    def is_logged_in(self):
        return self.user is not None


# ── Feature registry ───────────────────────────────────────────────────────────
class FeatureRegistry:
    _features = {
        "vpn":         {"enabled": False, "label": "VPN",          "icon": "🛡", "soon": True},
        "ai_assistant":{"enabled": False, "label": "AI Assistant", "icon": "✦", "soon": True},
        "reader_mode": {"enabled": False, "label": "Reader Mode",  "icon": "📖","soon": True},
        "extensions":  {"enabled": False, "label": "Extensions",   "icon": "🧩","soon": True},
    }

    @classmethod
    def is_enabled(cls, key):
        return cls._features.get(key, {}).get("enabled", False)

    @classmethod
    def toggle(cls, key):
        if key in cls._features:
            cls._features[key]["enabled"] = not cls._features[key]["enabled"]


# ── User / session manager ────────────────────────────────────────────────────
class UserManager:
    _inst = None

    @classmethod
    def get(cls):
        if not cls._inst:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self._users: dict = {}
        self._current: str | None = None
        self._load_users()
        self._load_session()

    def _load_users(self):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                self._users = json.load(f)
        except Exception:
            self._users = {}

    def _save_users(self):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._users, f, indent=2)

    def _load_session(self):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                self._current = json.load(f).get("user")
                if self._current and self._current not in self._users:
                    self._current = None
        except Exception:
            self._current = None

    def _save_session(self):
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"user": self._current}, f)

    def _hash(self, password: str, salt: str = "") -> str:
        if not salt:
            salt = secrets.token_hex(16)
        h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"{salt}:{h}"

    def _verify(self, password: str, stored: str) -> bool:
        salt, _ = stored.split(":", 1)
        return self._hash(password, salt) == stored

    def register(self, username: str, email: str, password: str):
        if not username or not email or not password:
            return False, "All fields are required."
        if username in self._users:
            return False, "Username is already taken."
        if any(u["email"].lower() == email.lower() for u in self._users.values()):
            return False, "Email is already registered."
        if len(password) < 6:
            return False, "Password must be at least 6 characters."
        self._users[username] = {"email": email, "password": self._hash(password)}
        self._save_users()
        return True, "Account created."

    def login(self, identifier: str, password: str):
        user, data = None, None
        if identifier in self._users:
            user, data = identifier, self._users[identifier]
        else:
            for u, d in self._users.items():
                if d["email"].lower() == identifier.lower():
                    user, data = u, d
                    break
        if not user:
            return False, "No account found with that username or email."
        if not self._verify(password, data["password"]):
            return False, "Incorrect password."
        self._current = user
        self._save_session()
        return True, user

    def logout(self):
        self._current = None
        self._save_session()

    def current_user(self) -> str | None:
        return self._current

    def is_logged_in(self) -> bool:
        return self._current is not None


# ── Shortcuts manager (new-tab page tiles) ────────────────────────────────────
class ShortcutsManager:
    _inst = None

    @classmethod
    def get(cls):
        if not cls._inst:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self._sc: list[dict] = []
        self._file = _user_data_file("shortcuts.json")
        self._load()

    @classmethod
    def reset(cls):
        cls._inst = None

    def _load(self):
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                self._sc = json.load(f)
        except Exception:
            self._sc = []

    def _save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._sc, f, indent=2)

    def all(self):
        return list(self._sc)

    def add(self, name: str, url: str):
        if not any(s["url"] == url for s in self._sc):
            self._sc.append({"name": name, "url": url})
            self._save()

    def remove(self, url: str):
        self._sc = [s for s in self._sc if s["url"] != url]
        self._save()


# ── History manager ────────────────────────────────────────────────────────────
class HistoryManager:
    _inst = None
    MAX_ENTRIES = 5000

    @classmethod
    def get(cls):
        if not cls._inst:
            cls._inst = cls()
        return cls._inst

    @classmethod
    def reset(cls):
        cls._inst = None

    def __init__(self):
        self._entries: list[dict] = []
        self._file = _user_data_file("history.json")
        self._load()

    def _load(self):
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                self._entries = json.load(f)
        except Exception:
            self._entries = []

    def _save(self):
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2)
        except Exception:
            pass

    def add(self, url: str, title: str):
        import time
        entry = {"url": url, "title": title or url, "ts": time.time()}
        self._entries.insert(0, entry)
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[:self.MAX_ENTRIES]
        self._save()

    def all(self):
        return list(self._entries)

    def clear(self):
        self._entries = []
        self._save()


# ── Bookmark manager ───────────────────────────────────────────────────────────
class BookmarkManager:
    _inst = None

    @classmethod
    def get(cls):
        if not cls._inst:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self._bm: list[dict] = []
        self._file = _user_data_file("bookmarks.json")
        self._load()

    @classmethod
    def reset(cls):
        cls._inst = None

    def _load(self):
        try:
            with open(self._file, "r", encoding="utf-8") as f:
                self._bm = json.load(f)
        except Exception:
            self._bm = []

    def _save(self):
        with open(self._file, "w", encoding="utf-8") as f:
            json.dump(self._bm, f, indent=2)

    def all(self):
        return list(self._bm)

    def has(self, url: str) -> bool:
        return any(b["url"] == url for b in self._bm)

    def add(self, title: str, url: str):
        if not self.has(url):
            self._bm.append({"title": title or url, "url": url})
            self._save()

    def remove(self, url: str):
        self._bm = [b for b in self._bm if b["url"] != url]
        self._save()

    def toggle(self, title: str, url: str) -> bool:
        if self.has(url):
            self.remove(url)
            return False
        else:
            self.add(title, url)
            return True


# ── Account dialog (login + sign-up) ──────────────────────────────────────────
class AccountDialog(QDialog):
    def __init__(self, parent=None, start="login"):
        super().__init__(parent)
        self.setWindowTitle("Externo Account")
        self.setFixedWidth(420)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog  {{ background: {T('bg')}; color: {T('text')}; }}
            QLabel   {{ color: {T('text')}; font-size: 13px; }}
            QLineEdit {{
                background: {T('field_bg')}; color: {T('text')};
                border: 1.5px solid {T('border')}; border-radius: 10px;
                padding: 11px 16px; font-size: 14px;
                selection-background-color: {T('accent')};
            }}
            QLineEdit:focus {{ border-color: {T('accent')}; background: {T('titlebar')}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_login())
        self._stack.addWidget(self._build_signup())
        layout.addWidget(self._stack)
        self._stack.setCurrentIndex(0 if start == "login" else 1)

    # ── shared helpers ─────────────────────────────────────────────────────────

    def _section(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(44, 36, 44, 36)
        v.setSpacing(14)
        return w, v

    def _gradient_btn(self, label):
        b = QPushButton(label)
        b.setFixedHeight(48)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {T('accent')}, stop:1 {T('accent2')});
                color: #08121e; border: none; border-radius: 10px;
                font-size: 15px; font-weight: 800; letter-spacing: .4px;
            }}
            QPushButton:hover  {{ opacity: .88; }}
            QPushButton:pressed {{ opacity: .72; }}
        """)
        return b

    def _link_btn(self, label):
        b = QPushButton(label)
        b.setFlat(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T('accent')};
                border: none; font-size: 13px; font-weight: 600; padding: 0;
            }}
            QPushButton:hover {{ color: {T('accent_hv')}; }}
        """)
        return b

    def _msg_label(self):
        lbl = QLabel("")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setVisible(False)
        lbl.setWordWrap(True)
        return lbl

    def _set_error(self, lbl, text):
        lbl.setText(text)
        lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        lbl.setVisible(True)

    def _set_ok(self, lbl, text):
        lbl.setText(text)
        lbl.setStyleSheet(f"color: {T('accent2')}; font-size: 12px;")
        lbl.setVisible(True)

    # ── login page ─────────────────────────────────────────────────────────────

    def _build_login(self):
        page, v = self._section()

        logo = LogoWidget(52)
        v.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Sign in to Externo")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {T('text')}; font-size: 17px;")
        v.addWidget(title)

        self._login_msg = self._msg_label()
        v.addWidget(self._login_msg)

        self._login_id = QLineEdit()
        self._login_id.setPlaceholderText("Username or email")
        v.addWidget(self._login_id)

        self._login_pw = QLineEdit()
        self._login_pw.setPlaceholderText("Password")
        self._login_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_pw.returnPressed.connect(self._do_login)
        v.addWidget(self._login_pw)

        btn = self._gradient_btn("Sign In")
        btn.clicked.connect(self._do_login)
        v.addWidget(btn)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(QLabel("Don't have an account?"))
        lnk = self._link_btn("Sign up")
        lnk.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        row.addWidget(lnk)
        row.addStretch()
        v.addLayout(row)
        return page

    # ── sign-up page ───────────────────────────────────────────────────────────

    def _build_signup(self):
        page, v = self._section()

        logo = LogoWidget(52)
        v.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Create your account")
        title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {T('text')}; font-size: 17px;")
        v.addWidget(title)

        self._signup_msg = self._msg_label()
        v.addWidget(self._signup_msg)

        self._su_user = QLineEdit(); self._su_user.setPlaceholderText("Username")
        self._su_email = QLineEdit(); self._su_email.setPlaceholderText("Email address")
        self._su_pw = QLineEdit()
        self._su_pw.setPlaceholderText("Password  (min. 6 characters)")
        self._su_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._su_pw2 = QLineEdit()
        self._su_pw2.setPlaceholderText("Confirm password")
        self._su_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self._su_pw2.returnPressed.connect(self._do_signup)

        for field in (self._su_user, self._su_email, self._su_pw, self._su_pw2):
            v.addWidget(field)

        btn = self._gradient_btn("Create Account")
        btn.clicked.connect(self._do_signup)
        v.addWidget(btn)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(QLabel("Already have an account?"))
        lnk = self._link_btn("Sign in")
        lnk.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        row.addWidget(lnk)
        row.addStretch()
        v.addLayout(row)
        return page

    # ── actions ────────────────────────────────────────────────────────────────

    def _do_login(self):
        ok, result = UserManager.get().login(
            self._login_id.text().strip(), self._login_pw.text())
        if ok:
            self.accept()
        else:
            self._set_error(self._login_msg, result)

    def _do_signup(self):
        pw, pw2 = self._su_pw.text(), self._su_pw2.text()
        if pw != pw2:
            self._set_error(self._signup_msg, "Passwords do not match.")
            return
        ok, msg = UserManager.get().register(
            self._su_user.text().strip(),
            self._su_email.text().strip(), pw)
        if ok:
            UserManager.get().login(self._su_user.text().strip(), pw)
            self.accept()
        else:
            self._set_error(self._signup_msg, msg)


# ── Logo widget ────────────────────────────────────────────────────────────────
class LogoWidget(QLabel):
    def __init__(self, size=26, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet("background: transparent;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = asset("logo.png")
        if os.path.exists(path):
            px = QPixmap(path).scaled(size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.setPixmap(px)
        else:
            self.setPixmap(self._painted(size))

    def _painted(self, s):
        px = QPixmap(s, s)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, s, s)
        g.setColorAt(0, QColor(T("accent")))
        g.setColorAt(1, QColor(T("accent2")))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        r = s * 0.22
        p.drawRoundedRect(0, 0, s, s, r, r)
        p.setPen(QColor("#fff"))
        p.setFont(QFont("Segoe UI", int(s * 0.52), QFont.Weight.Bold))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "E")
        p.end()
        return px


# ── Auto-updater ───────────────────────────────────────────────────────────────
class _UpdateSignal(QObject):
    found            = pyqtSignal(str, str, str)  # version, download_url, notes
    download_done    = pyqtSignal(str)             # bat_path
    download_failed  = pyqtSignal(str)             # error message


class UpdateBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setVisible(False)
        self.setObjectName("UpdateBanner")
        self.setStyleSheet("""
            QFrame#UpdateBanner {
                background: #071f12;
                border: none;
                border-bottom: 1px solid #00e676;
            }
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 8, 0)
        row.setSpacing(10)

        icon = QLabel("↑")
        icon.setStyleSheet("color: #00e676; font-size: 16px; font-weight: bold; background: transparent;")

        self._msg = QLabel()
        self._msg.setStyleSheet("color: #ddf2ff; font-size: 12px; background: transparent;")
        self._msg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._action_btn = QPushButton("Update Now")
        self._action_btn.setFixedHeight(26)
        self._action_btn.setStyleSheet("""
            QPushButton {
                background: #00e676; color: #001a08;
                border: none; border-radius: 6px;
                padding: 0 14px; font-size: 12px; font-weight: 700;
            }
            QPushButton:hover { background: #00c853; }
            QPushButton:disabled { background: #163560; color: #3a6888; }
        """)

        dismiss = QPushButton("✕")
        dismiss.setFixedSize(22, 22)
        dismiss.setStyleSheet("""
            QPushButton {
                background: transparent; color: #3a6888;
                border: none; font-size: 10px; border-radius: 4px;
            }
            QPushButton:hover { background: #163560; color: #ddf2ff; }
        """)
        dismiss.clicked.connect(self.hide)

        row.addWidget(icon)
        row.addWidget(self._msg)
        row.addWidget(self._action_btn)
        row.addWidget(dismiss)

    def show_update(self, version: str, notes: str, on_update):
        self._msg.setText(f"Update available: <b>v{version}</b> — {notes}")
        self._action_btn.setText("Update Now")
        self._action_btn.setEnabled(True)
        try:
            self._action_btn.clicked.disconnect()
        except Exception:
            pass
        self._action_btn.clicked.connect(on_update)
        self.setVisible(True)

    def set_status(self, text: str, btn_label: str = "", on_click=None):
        self._msg.setText(text)
        if btn_label:
            self._action_btn.setText(btn_label)
            self._action_btn.setEnabled(True)
            try:
                self._action_btn.clicked.disconnect()
            except Exception:
                pass
            if on_click:
                self._action_btn.clicked.connect(on_click)
        else:
            self._action_btn.setEnabled(False)
            self._action_btn.setText("…")


# ── Tab chip ───────────────────────────────────────────────────────────────────
class TabChip(QFrame):
    sig_close  = pyqtSignal(object)
    sig_select = pyqtSignal(object)

    def __init__(self, title="New Tab"):
        super().__init__()
        self.setFixedHeight(40)
        self.setMinimumWidth(110)
        self.setMaximumWidth(220)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._active = False

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 6, 0)
        row.setSpacing(6)

        self.icon_lbl = QLabel("○")
        self.icon_lbl.setFixedWidth(13)
        self.icon_lbl.setStyleSheet(f"font-size: 10px; color: {T('dim')}; background: transparent;")

        self.title_lbl = QLabel(self._trim(title))
        self.title_lbl.setStyleSheet(f"color: {T('dim')}; font-size: 12px; background: transparent;")

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.clicked.connect(lambda: self.sig_close.emit(self))
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; font-size: 9px; border-radius: 8px;
            }}
            QPushButton:hover {{ background: {T('close_hv')}; color: #fff; }}
        """)

        row.addWidget(self.icon_lbl)
        row.addWidget(self.title_lbl, stretch=1)
        row.addWidget(self.close_btn)
        self._refresh()

    def set_active(self, active):
        self._active = active
        self._refresh()

    def set_title(self, title):
        self.title_lbl.setText(self._trim(title))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self.close_btn.underMouse():
            self.sig_select.emit(self)
        super().mousePressEvent(e)

    @staticmethod
    def _trim(t):
        return t[:20] + "…" if len(t) > 20 else t

    def _refresh(self):
        if self._active:
            self.setStyleSheet(f"""
                QFrame {{
                    background: {T('toolbar')};
                    border: none;
                    border-bottom: 2px solid {T('accent')};
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {T('text')}; font-size: 12px; font-weight: 600; background: transparent;")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                }}
            """)
            self.title_lbl.setStyleSheet(f"color: {T('dim')}; font-size: 12px; background: transparent;")


# ── Title bar ──────────────────────────────────────────────────────────────────
class TitleBar(QFrame):
    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self._drag = None
        self.setFixedHeight(40)
        self.setObjectName("TitleBar")
        self.setStyleSheet(f"QFrame#TitleBar {{ background: {T('titlebar')}; border: none; }}")

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(0)

        # Logo + brand
        self._logo = LogoWidget(32)
        brand = QLabel("EXTERNO")
        brand.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        brand.setStyleSheet(f"color: {T('brand')}; letter-spacing: 3px; padding: 0 10px 0 4px;")

        # Tab strip — + lives inside the strip as its last item so it always
        # moves with the newest tab and never freezes mid-screen.
        self._tabs: list[TabChip] = []
        self._tab_row = QHBoxLayout()
        self._tab_row.setSpacing(3)
        self._tab_row.setContentsMargins(0, 0, 0, 0)
        self._tab_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        tab_wrap = QWidget()
        tab_wrap.setStyleSheet("background: transparent;")
        tab_wrap.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        tab_wrap.setLayout(self._tab_row)

        # + is the permanent last item in _tab_row; new chips are inserted before it
        self._new_tab_btn = self._icon_btn("+", "New tab  Ctrl+T", size=28, font_size=17)
        self._new_tab_btn.clicked.connect(lambda: win.new_tab())
        self._tab_row.addWidget(self._new_tab_btn)

        # Drag spacer fills everything to the right of the strip
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.account_btn = self._icon_btn("👤", "Account", size=28, font_size=13)
        self.account_btn.clicked.connect(self._on_account)
        self._refresh_account_btn()

        self.min_btn   = self._win_btn("─", T("border"), T("text"))
        self.max_btn   = self._win_btn("□", T("border"), T("text"))
        self.close_btn = self._win_btn("✕", T("close_hv"), "#fff")
        self.min_btn.clicked.connect(win.showMinimized)
        self.max_btn.clicked.connect(self._toggle_max)
        self.close_btn.clicked.connect(win.close)

        row.addWidget(self._logo)
        row.addWidget(brand)
        row.addWidget(tab_wrap)
        row.addWidget(spacer)
        row.addWidget(self.account_btn)
        row.addSpacing(4)
        row.addWidget(self.min_btn)
        row.addWidget(self.max_btn)
        row.addWidget(self.close_btn)

    def add_tab(self, chip):
        self._tabs.append(chip)
        # Insert before the + button which is always the last item
        self._tab_row.insertWidget(self._tab_row.count() - 1, chip)

    def remove_tab(self, chip):
        self._tabs.remove(chip)
        self._tab_row.removeWidget(chip)
        chip.setParent(None)

    def set_active(self, chip):
        for t in self._tabs:
            t.set_active(t is chip)

    def tab_at(self, idx):
        return self._tabs[idx]

    def index_of(self, chip):
        return self._tabs.index(chip)

    def count(self):
        return len(self._tabs)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag and e.buttons() == Qt.MouseButton.LeftButton:
            if self._win.isMaximized():
                self._win.showNormal()
            self._win.move(e.globalPosition().toPoint() - self._drag)

    def mouseDoubleClickEvent(self, _):
        self._toggle_max()

    def _toggle_max(self):
        self._win.showNormal() if self._win.isMaximized() else self._win.showMaximized()

    def _on_account(self):
        um = UserManager.get()
        if um.is_logged_in():
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{
                    background: {T('titlebar')}; color: {T('text')};
                    border: 1px solid {T('border')}; border-radius: 8px; padding: 4px;
                    font-size: 13px;
                }}
                QMenu::item {{ padding: 8px 22px 8px 14px; border-radius: 5px; }}
                QMenu::item:selected {{ background: {T('border')}; }}
                QMenu::item:disabled {{ color: {T('dim')}; }}
                QMenu::separator {{ height: 1px; background: {T('border')}; margin: 4px 0; }}
            """)
            header = menu.addAction(f"Signed in as  {um.current_user()}")
            header.setEnabled(False)
            menu.addSeparator()
            menu.addAction("Sign Out", self._do_logout)
            pos = self.account_btn.mapToGlobal(self.account_btn.rect().bottomLeft())
            pos.setX(pos.x() - 80)
            menu.exec(pos)
        else:
            dlg = AccountDialog(self._win)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self._refresh_account_btn()
                self._reload_user_data()

    def _do_logout(self):
        UserManager.get().logout()
        self._refresh_account_btn()
        self._reload_user_data()

    def _reload_user_data(self):
        BookmarkManager.reset()
        ShortcutsManager.reset()
        self._win._on_auth_changed()

    def _refresh_account_btn(self):
        um = UserManager.get()
        if um.is_logged_in():
            initial = um.current_user()[0].upper()
            self.account_btn.setText(initial)
            self.account_btn.setFixedSize(28, 28)
            self.account_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                        stop:0 {T('accent')}, stop:1 {T('accent2')});
                    color: #08121e; border: none; border-radius: 14px;
                    font-size: 13px; font-weight: 800;
                }}
                QPushButton:hover {{ opacity: .85; }}
            """)
        else:
            self.account_btn.setText("👤")
            self.account_btn.setFixedSize(28, 28)
            self.account_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {T('dim')};
                    border: none; border-radius: 14px; font-size: 13px;
                }}
                QPushButton:hover {{ background: {T('border')}; color: {T('text')}; }}
            """)

    def _icon_btn(self, text, tip="", size=32, font_size=14):
        b = QPushButton(text)
        b.setFixedSize(size, size)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: {size // 2}px; font-size: {font_size}px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: {T('text')}; }}
        """)
        return b

    def _win_btn(self, text, hover_bg, hover_fg):
        b = QPushButton(text)
        b.setFixedSize(40, 32)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {T('dim')}; border: none; font-size: 13px; }}
            QPushButton:hover {{ background: {hover_bg}; color: {hover_fg}; }}
        """)
        return b


# ── Navigation bar ─────────────────────────────────────────────────────────────
class NavBar(QFrame):
    sig_navigate       = pyqtSignal(str)
    sig_bookmark_toggle = pyqtSignal()
    sig_open_menu      = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(52)
        self.setStyleSheet(f"QFrame {{ background: {T('toolbar')}; border-bottom: 1px solid {T('border')}; }}")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(6)

        nav_ss = f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: 8px;
                font-size: 20px; min-width: 34px; min-height: 34px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: {T('text')}; }}
            QPushButton:disabled {{ color: {T('dim')}; }}
        """
        self.back_btn    = QPushButton("‹")
        self.forward_btn = QPushButton("›")
        self.reload_btn  = QPushButton("↺")
        self.home_btn    = QPushButton("⌂")
        for b in (self.back_btn, self.forward_btn, self.reload_btn, self.home_btn):
            b.setStyleSheet(nav_ss)
            b.setFixedSize(36, 36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search or enter address")
        self.url_bar.setFixedHeight(36)
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background: {T('field_bg')}; color: {T('text')};
                border: 1.5px solid {T('border')}; border-radius: 18px;
                padding: 0 18px; font-size: 13px;
                selection-background-color: {T('accent')};
            }}
            QLineEdit:focus {{ border: 1.5px solid {T('accent')}; }}
        """)
        self.url_bar.returnPressed.connect(self._go)

        # Bookmark star button
        self.star_btn = QPushButton("☆")
        self.star_btn.setFixedSize(32, 32)
        self.star_btn.setToolTip("Bookmark this page  Ctrl+D")
        self.star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.star_btn.clicked.connect(self.sig_bookmark_toggle.emit)
        self._star_ss_off = f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: 8px; font-size: 16px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: {T('accent2')}; }}
        """
        self._star_ss_on = f"""
            QPushButton {{
                background: transparent; color: #f5c518;
                border: none; border-radius: 8px; font-size: 16px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: #e6b800; }}
        """
        self.star_btn.setStyleSheet(self._star_ss_off)

        self.vpn_btn = self._feat_btn("🛡", "VPN (coming soon)",           "vpn")
        self.ai_btn  = self._feat_btn("✦",  "AI Assistant (coming soon)",  "ai_assistant")
        self.ext_btn = self._feat_btn("⋯",  "Settings & more",             None)
        self.ext_btn.clicked.connect(self.sig_open_menu.emit)

        self.go_btn = QPushButton("Go")
        self.go_btn.setFixedSize(52, 34)
        self.go_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T('accent')}; color: #fff;
                border: none; border-radius: 17px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background: {T('accent_hv')}; }}
        """)
        self.go_btn.clicked.connect(self._go)

        row.addWidget(self.back_btn)
        row.addWidget(self.forward_btn)
        row.addWidget(self.reload_btn)
        row.addWidget(self.home_btn)
        row.addSpacing(4)
        row.addWidget(self.url_bar, stretch=1)
        row.addWidget(self.star_btn)
        row.addSpacing(4)
        row.addWidget(self.vpn_btn)
        row.addWidget(self.ai_btn)
        row.addWidget(self.ext_btn)
        row.addSpacing(2)
        row.addWidget(self.go_btn)

    def set_url(self, url: str):
        self.url_bar.setText(url)
        self.url_bar.setCursorPosition(0)

    def set_bookmarked(self, bookmarked: bool):
        self.star_btn.setText("★" if bookmarked else "☆")
        self.star_btn.setStyleSheet(self._star_ss_on if bookmarked else self._star_ss_off)

    def _go(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        if "." in text and " " not in text:
            url = text if text.startswith("http") else "https://" + text
        else:
            url = "https://www.google.com/search?q=" + text.replace(" ", "+")
        self.sig_navigate.emit(url)

    def _feat_btn(self, icon, tip, feature_key):
        b = QPushButton(icon)
        b.setFixedSize(32, 32)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: 8px; font-size: 15px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: {T('text')}; }}
            QPushButton:checked {{ color: {T('accent2')}; background: {T('border')}; }}
        """)
        b.setCheckable(feature_key is not None)
        if feature_key:
            b.clicked.connect(lambda *_, k=feature_key: FeatureRegistry.toggle(k))
        return b


# ── Bookmark bar ───────────────────────────────────────────────────────────────
class BookmarkBar(QFrame):
    sig_navigate = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        self.setVisible(False)
        self.setStyleSheet(f"""
            QFrame {{ background: {T('titlebar')}; border-bottom: 1px solid {T('border')}; }}
        """)
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(10, 0, 10, 0)
        self._row.setSpacing(4)
        self._row.addStretch()
        self._rebuild()

    def refresh(self):
        self._rebuild()

    def _rebuild(self):
        while self._row.count():
            item = self._row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        bm = BookmarkManager.get()
        for b in bm.all():
            url   = b["url"]
            title = b["title"][:20] + "…" if len(b["title"]) > 20 else b["title"]
            btn = QPushButton(f"🔖 {title}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(url)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {T('text')};
                    border: none; border-radius: 4px;
                    font-size: 12px; padding: 2px 8px;
                }}
                QPushButton:hover {{ background: {T('border')}; }}
            """)
            btn.clicked.connect(lambda _, u=url: self.sig_navigate.emit(u))

            # Right-click to delete
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, u=url, bt=btn: self._bm_context(bt, u, pos))
            self._row.addWidget(btn)

        self._row.addStretch()

    def _bm_context(self, btn, url, pos):
        menu = QMenu(self)
        menu.setStyleSheet(self._menu_ss())
        menu.addAction("✕  Remove bookmark", lambda: self._remove(url))
        menu.exec(btn.mapToGlobal(pos))

    def _remove(self, url):
        BookmarkManager.get().remove(url)
        self._rebuild()

    @staticmethod
    def _menu_ss():
        return f"""
            QMenu {{
                background: {T('titlebar')}; color: {T('text')};
                border: 1px solid {T('border')}; border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {T('border')}; }}
        """


# ── Download item ──────────────────────────────────────────────────────────────
class DownloadItem(QFrame):
    sig_done = pyqtSignal(object)

    def __init__(self, download: QWebEngineDownloadRequest):
        super().__init__()
        self._dl = download
        self.setFixedHeight(42)
        self.setStyleSheet(f"""
            QFrame {{
                background: {T('titlebar')}; border-top: 1px solid {T('border')};
                border-radius: 0;
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)

        self._name_lbl = QLabel(download.downloadFileName())
        self._name_lbl.setStyleSheet(f"color: {T('text')}; font-size: 12px;")
        self._name_lbl.setMaximumWidth(260)

        self._bar = QProgressBar()
        self._bar.setFixedHeight(6)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(f"""
            QProgressBar {{ background: {T('border')}; border: none; border-radius: 3px; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {T('accent')}, stop:1 {T('accent2')});
                border-radius: 3px;
            }}
        """)

        self._status_lbl = QLabel("Starting…")
        self._status_lbl.setStyleSheet(f"color: {T('dim')}; font-size: 11px;")
        self._status_lbl.setMinimumWidth(80)

        self._open_btn = QPushButton("Open")
        self._open_btn.setFixedSize(54, 26)
        self._open_btn.setVisible(False)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T('accent2')}; color: #000;
                border: none; border-radius: 5px; font-size: 11px; font-weight: bold;
            }}
            QPushButton:hover {{ background: #00c060; }}
        """)
        self._open_btn.clicked.connect(self._open_file)

        cancel_btn = QPushButton("✕")
        cancel_btn.setFixedSize(24, 24)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: 4px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {T('close_hv')}; color: #fff; }}
        """)
        cancel_btn.clicked.connect(self._dismiss)

        row.addWidget(self._name_lbl)
        row.addWidget(self._bar, stretch=1)
        row.addWidget(self._status_lbl)
        row.addWidget(self._open_btn)
        row.addWidget(cancel_btn)

        download.receivedBytesChanged.connect(self._on_progress)
        download.stateChanged.connect(self._on_state)
        download.accept()

    def _on_progress(self):
        total = self._dl.totalBytes()
        recv  = self._dl.receivedBytes()
        if total > 0:
            self._bar.setMaximum(int(total))
            self._bar.setValue(int(recv))
            mb = recv / 1_048_576
            self._status_lbl.setText(f"{mb:.1f} MB")
        else:
            self._bar.setMaximum(0)

    def _on_state(self, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            self._bar.setValue(self._bar.maximum() or 100)
            self._status_lbl.setText("Done")
            self._open_btn.setVisible(True)
            QTimer.singleShot(8000, self._dismiss)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadCancelled:
            self._status_lbl.setText("Cancelled")
            QTimer.singleShot(2000, self._dismiss)
        elif state == QWebEngineDownloadRequest.DownloadState.DownloadInterrupted:
            self._status_lbl.setText("Failed")
            QTimer.singleShot(3000, self._dismiss)

    def _open_file(self):
        path = os.path.join(self._dl.downloadDirectory(), self._dl.downloadFileName())
        os.startfile(path)

    def _dismiss(self):
        if not self._dl.isFinished():
            self._dl.cancel()
        self.sig_done.emit(self)


# ── Download bar ───────────────────────────────────────────────────────────────
class DownloadBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setVisible(False)
        self.setStyleSheet(f"QFrame {{ background: {T('titlebar')}; }}")
        self._vbox = QVBoxLayout(self)
        self._vbox.setContentsMargins(0, 0, 0, 0)
        self._vbox.setSpacing(0)
        self._items: list[DownloadItem] = []

    def add(self, download: QWebEngineDownloadRequest):
        item = DownloadItem(download)
        item.sig_done.connect(self._remove)
        self._items.append(item)
        self._vbox.addWidget(item)
        self.setVisible(True)

    def _remove(self, item: DownloadItem):
        self._items.remove(item)
        self._vbox.removeWidget(item)
        item.setParent(None)
        if not self._items:
            self.setVisible(False)


# ── Suppress known-harmless browser warnings ───────────────────────────────────
_SUPPRESSED_CONSOLE = (
    "Unrecognized feature: 'payment'",
    "Permissions-Policy header",
)

class ExternoPage(QWebEnginePage):
    sig_externo_nav = pyqtSignal(str)

    def javaScriptConsoleMessage(self, level, message, line, source):
        if any(s in message for s in _SUPPRESSED_CONSOLE):
            return
        super().javaScriptConsoleMessage(level, message, line, source)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if url.scheme() == "externo" and url.toString() != "about:blank":
            url_str = url.toString()
            QTimer.singleShot(0, lambda: self.sig_externo_nav.emit(url_str))
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# ── Web view with custom context menu ─────────────────────────────────────────
class ExternoWebView(QWebEngineView):
    sig_new_tab     = pyqtSignal(str)
    sig_bookmark_me = pyqtSignal()
    sig_externo_nav = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        page = ExternoPage(self)
        page.sig_externo_nav.connect(self.sig_externo_nav)
        self.setPage(page)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {T('titlebar')}; color: {T('text')};
                border: 1px solid {T('border')}; border-radius: 8px; padding: 4px;
            }}
            QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 5px; font-size: 13px; }}
            QMenu::item:selected {{ background: {T('border')}; }}
            QMenu::separator {{ height: 1px; background: {T('border')}; margin: 4px 8px; }}
        """)

        si = lambda n: _si(n)

        h = self.history()
        back = menu.addAction("Back")
        back.setIcon(si("SP_ArrowBack"))
        back.setEnabled(h.canGoBack())
        back.triggered.connect(self.back)

        fwd = menu.addAction("Forward")
        fwd.setIcon(si("SP_ArrowForward"))
        fwd.setEnabled(h.canGoForward())
        fwd.triggered.connect(self.forward)

        reload_act = menu.addAction("Reload")
        reload_act.setIcon(si("SP_BrowserReload"))
        reload_act.triggered.connect(self.reload)
        menu.addSeparator()

        ctx = self.lastContextMenuRequest()
        if ctx:
            link = ctx.linkUrl()
            if link.isValid() and link.toString():
                lurl = link.toString()
                open_act = menu.addAction("Open Link in New Tab")
                open_act.setIcon(si("SP_ArrowForward"))
                open_act.triggered.connect(lambda: self.sig_new_tab.emit(lurl))
                copy_link = menu.addAction("Copy Link")
                copy_link.setIcon(si("SP_FileLinkIcon"))
                copy_link.triggered.connect(lambda: QApplication.clipboard().setText(lurl))
                menu.addSeparator()

            sel = ctx.selectedText()
            if sel:
                copy_act = menu.addAction("Copy")
                copy_act.setIcon(si("SP_FileIcon"))
                copy_act.triggered.connect(lambda: QApplication.clipboard().setText(sel))
                search_act = menu.addAction("Search Google")
                search_act.setIcon(si("SP_FileDialogContentsView"))
                search_act.triggered.connect(
                    lambda: self.sig_new_tab.emit(
                        "https://www.google.com/search?q=" + sel.replace(" ", "+")))
                menu.addSeparator()

        bm_act = menu.addAction("Bookmark This Page")
        bm_act.setIcon(si("SP_DialogSaveButton"))
        bm_act.triggered.connect(self.sig_bookmark_me.emit)
        copy_url = menu.addAction("Copy Page URL")
        copy_url.setIcon(si("SP_FileLinkIcon"))
        copy_url.triggered.connect(lambda: QApplication.clipboard().setText(self.url().toString()))
        menu.addSeparator()
        save_act = menu.addAction("Save Page As…")
        save_act.setIcon(si("SP_DialogSaveButton"))
        save_act.triggered.connect(lambda: self.page().triggerAction(QWebEnginePage.WebAction.SavePage))
        src_act = menu.addAction("View Page Source")
        src_act.setIcon(si("SP_FileDialogDetailedView"))
        src_act.triggered.connect(lambda: self.sig_new_tab.emit("view-source:" + self.url().toString()))

        menu.exec(event.globalPos())


# ── Find-in-page bar ───────────────────────────────────────────────────────────
class FindBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(42)
        self.setVisible(False)
        self.setStyleSheet(f"""
            QFrame {{ background: {T('titlebar')}; border-top: 1px solid {T('border')}; }}
            QLineEdit {{
                background: {T('field_bg')}; color: {T('text')};
                border: 1px solid {T('border')}; border-radius: 6px;
                padding: 4px 10px; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {T('accent')}; }}
            QPushButton {{
                background: transparent; color: {T('dim')};
                border: none; border-radius: 6px; padding: 4px 10px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {T('border')}; color: {T('text')}; }}
            QLabel {{ color: {T('dim')}; font-size: 12px; padding: 0 6px; }}
        """)
        self._page = None

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(4)

        lbl = QLabel("Find:")
        lbl.setStyleSheet(f"color: {T('text')}; font-size: 13px; font-weight: 600;")

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search on page…")
        self._input.setFixedWidth(260)
        self._input.textChanged.connect(self._find)
        self._input.returnPressed.connect(self._find_next)

        self._count_lbl = QLabel("")

        prev_btn = QPushButton("▲")
        prev_btn.setToolTip("Previous  Shift+Enter")
        prev_btn.clicked.connect(self._find_prev)

        next_btn = QPushButton("▼")
        next_btn.setToolTip("Next  Enter")
        next_btn.clicked.connect(self._find_next)

        close_btn = QPushButton("✕")
        close_btn.setToolTip("Close find bar  Escape")
        close_btn.clicked.connect(self.close_find)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        row.addWidget(lbl)
        row.addWidget(self._input)
        row.addWidget(self._count_lbl)
        row.addWidget(prev_btn)
        row.addWidget(next_btn)
        row.addWidget(spacer)
        row.addWidget(close_btn)

    def open_find(self, page):
        self._page = page
        self.setVisible(True)
        self._input.setFocus()
        self._input.selectAll()

    def _find(self):
        if self._page:
            self._page.findText(self._input.text())

    def _find_next(self):
        if self._page:
            self._page.findText(self._input.text())

    def _find_prev(self):
        if self._page:
            self._page.findText(
                self._input.text(),
                QWebEnginePage.FindFlag.FindBackward)

    def close_find(self):
        if self._page:
            self._page.findText("")
        self.setVisible(False)


# ── Main window ────────────────────────────────────────────────────────────────
class ExternoBrowser(QMainWindow):
    HOME = "externo://newtab"

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(f"QMainWindow, QWidget#root {{ background: {T('bg')}; }}")

        icon_path = asset("logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._views: list[ExternoWebView] = []
        self._active_idx = -1
        self._zoom = 1.0

        self.title_bar    = TitleBar(self)
        self.nav_bar      = NavBar()
        self.update_bar   = UpdateBanner()
        self.bookmark_bar = BookmarkBar()
        self.progress     = self._make_progress()
        self.stack        = QStackedWidget()
        self.find_bar     = FindBar()
        self.dl_bar       = DownloadBar()
        self._sb          = self._make_statusbar()

        root = QWidget()
        root.setObjectName("root")
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(self.title_bar)
        vbox.addWidget(self.nav_bar)
        vbox.addWidget(self.update_bar)
        vbox.addWidget(self.bookmark_bar)
        vbox.addWidget(self.progress)
        vbox.addWidget(self.stack, stretch=1)
        vbox.addWidget(self.find_bar)
        vbox.addWidget(self.dl_bar)
        self.setCentralWidget(root)

        self._wire_navbar()
        self._setup_shortcuts()
        self._setup_downloads()
        self.new_tab(self.HOME)
        QTimer.singleShot(4000, self._check_for_updates)

    # ── Downloads ──────────────────────────────────────────────────────────────

    def _setup_downloads(self):
        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            self._on_download_requested)

    def _on_download_requested(self, dl: QWebEngineDownloadRequest):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File",
            os.path.join(os.path.expanduser("~"), "Downloads", dl.downloadFileName()))
        if path:
            dl.setDownloadDirectory(os.path.dirname(path))
            dl.setDownloadFileName(os.path.basename(path))
            self.dl_bar.add(dl)
        else:
            dl.cancel()

    # ── Keyboard shortcuts ─────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        def sc(key, fn):
            QShortcut(QKeySequence(key), self).activated.connect(fn)

        sc("Ctrl+T",         lambda: self.new_tab())
        sc("Ctrl+H",         lambda: self.new_tab("externo://history"))
        sc("Ctrl+W",         self._close_current_tab)
        sc("Ctrl+R",         lambda: self._cur().reload())
        sc("F5",             lambda: self._cur().reload())
        sc("Ctrl+L",         self._focus_url_bar)
        sc("Ctrl+D",         self._toggle_bookmark)
        sc("Ctrl+B",         self._toggle_bookmark_bar)
        sc("Alt+Left",       lambda: self._cur().back())
        sc("Alt+Right",      lambda: self._cur().forward())
        sc("Ctrl+Tab",       self._next_tab)
        sc("Ctrl+Shift+Tab", self._prev_tab)
        sc("F11",            self._toggle_fullscreen)
        sc("Escape",         self._exit_fullscreen)
        sc("Ctrl+H",         self._go_home)
        sc("Ctrl+F",         self._show_find_bar)
        sc("Ctrl+Equal",     self._zoom_in)
        sc("Ctrl+Minus",     self._zoom_out)
        sc("Ctrl+0",         self._zoom_reset)

    def _close_current_tab(self):
        if self.title_bar.count() == 1:
            self.close()
        else:
            self._on_chip_close(self.title_bar.tab_at(self._active_idx))

    def _focus_url_bar(self):
        self.nav_bar.url_bar.setFocus()
        self.nav_bar.url_bar.selectAll()

    def _toggle_bookmark(self):
        url   = self._cur().url().toString()
        title = self._cur().title() or url
        added = BookmarkManager.get().toggle(title, url)
        self.nav_bar.set_bookmarked(added)
        self.bookmark_bar.refresh()

    def _toggle_bookmark_bar(self):
        self.bookmark_bar.setVisible(not self.bookmark_bar.isVisible())

    def _next_tab(self):
        if self.title_bar.count() > 1:
            self._switch((self._active_idx + 1) % self.title_bar.count())

    def _prev_tab(self):
        if self.title_bar.count() > 1:
            self._switch((self._active_idx - 1) % self.title_bar.count())

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.title_bar.setVisible(True)
            self.nav_bar.setVisible(True)
        else:
            self.title_bar.setVisible(False)
            self.nav_bar.setVisible(False)
            self.showFullScreen()

    def _exit_fullscreen(self):
        if self.isFullScreen():
            self._toggle_fullscreen()

    # ── Zoom ───────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        self._zoom = min(self._zoom + 0.1, 3.0)
        self._cur().setZoomFactor(self._zoom)

    def _zoom_out(self):
        self._zoom = max(self._zoom - 0.1, 0.25)
        self._cur().setZoomFactor(self._zoom)

    def _zoom_reset(self):
        self._zoom = 1.0
        self._cur().setZoomFactor(1.0)

    # ── Find in page ───────────────────────────────────────────────────────────

    def _show_find_bar(self):
        self.find_bar.open_find(self._cur().page())

    # ── Browser menu (⋯) ──────────────────────────────────────────────────────

    def _show_browser_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {T('titlebar')}; color: {T('text')};
                border: 1px solid {T('border')}; border-radius: 10px;
                padding: 6px 0px; font-size: 13px;
            }}
            QMenu::item {{ padding: 8px 40px 8px 16px; border-radius: 0px; }}
            QMenu::item:selected {{ background: {T('border')}; }}
            QMenu::item:disabled {{ color: {T('dim')}; }}
            QMenu::separator {{ height: 1px; background: {T('border')}; margin: 4px 0px; }}
        """)

        si = _si
        nt = menu.addAction("New Tab", lambda: self.new_tab())
        nt.setIcon(si("SP_FileDialogNewFolder"))
        nt.setShortcut(QKeySequence("Ctrl+T"))
        menu.addSeparator()

        bm_bar = menu.addAction("Show Bookmarks Bar")
        bm_bar.setIcon(si("SP_DirOpenIcon"))
        bm_bar.setCheckable(True)
        bm_bar.setChecked(self.bookmark_bar.isVisible())
        bm_bar.triggered.connect(self._toggle_bookmark_bar)
        bm_bar.setShortcut(QKeySequence("Ctrl+B"))

        bm_page = menu.addAction("Bookmark This Page", self._toggle_bookmark)
        bm_page.setIcon(si("SP_DialogSaveButton"))
        bm_page.setShortcut(QKeySequence("Ctrl+D"))
        menu.addSeparator()

        # Zoom row via custom widget
        zoom_w = QWidget()
        zoom_w.setStyleSheet("background: transparent;")
        zoom_l = QHBoxLayout(zoom_w)
        zoom_l.setContentsMargins(16, 4, 16, 4)
        zoom_l.setSpacing(4)

        zoom_label = QLabel(f"Zoom")
        zoom_label.setStyleSheet(f"color: {T('text')}; font-size: 13px;")

        zoom_spacer = QWidget()
        zoom_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        pct_lbl = QLabel(f"{int(self._zoom * 100)}%")
        pct_lbl.setStyleSheet(f"color: {T('dim')}; font-size: 12px; min-width: 40px; text-align: center;")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_ss = f"""
            QPushButton {{
                background: {T('border')}; color: {T('text')};
                border: none; border-radius: 6px;
                font-size: 16px; font-weight: bold;
                min-width: 30px; min-height: 26px; max-width: 30px; max-height: 26px;
            }}
            QPushButton:hover {{ background: {T('accent')}; color: #fff; }}
        """
        zm_out = QPushButton("−")
        zm_out.setStyleSheet(btn_ss)
        zm_out.clicked.connect(lambda: (self._zoom_out(), pct_lbl.setText(f"{int(self._zoom*100)}%")))

        zm_in = QPushButton("+")
        zm_in.setStyleSheet(btn_ss)
        zm_in.clicked.connect(lambda: (self._zoom_in(), pct_lbl.setText(f"{int(self._zoom*100)}%")))

        zm_reset = QPushButton("↺")
        zm_reset.setStyleSheet(btn_ss)
        zm_reset.setToolTip("Reset zoom")
        zm_reset.clicked.connect(lambda: (self._zoom_reset(), pct_lbl.setText("100%")))

        zoom_l.addWidget(zoom_label)
        zoom_l.addWidget(zoom_spacer)
        zoom_l.addWidget(zm_out)
        zoom_l.addWidget(pct_lbl)
        zoom_l.addWidget(zm_in)
        zoom_l.addWidget(zm_reset)

        zoom_act = QWidgetAction(menu)
        zoom_act.setDefaultWidget(zoom_w)
        menu.addAction(zoom_act)
        menu.addSeparator()

        hist_act = menu.addAction("History", lambda: self.new_tab("externo://history"))
        hist_act.setIcon(si("SP_FileDialogListView"))
        hist_act.setShortcut(QKeySequence("Ctrl+H"))
        menu.addSeparator()

        find_act = menu.addAction("Find in Page…", self._show_find_bar)
        find_act.setIcon(si("SP_FileDialogContentsView"))
        find_act.setShortcut(QKeySequence("Ctrl+F"))
        save_act = menu.addAction("Save Page As…",
                       lambda: self._cur().page().triggerAction(QWebEnginePage.WebAction.SavePage))
        save_act.setIcon(si("SP_DialogSaveButton"))
        print_act = menu.addAction("Print…",
                       lambda: self._cur().page().printToPdf(""))
        print_act.setIcon(si("SP_FileLinkIcon"))
        menu.addSeparator()

        src_act = menu.addAction("View Page Source",
                       lambda: self.new_tab("view-source:" + self._cur().url().toString()))
        src_act.setIcon(si("SP_FileDialogDetailedView"))
        menu.addSeparator()

        cfg_act = menu.addAction("Settings", self._show_settings)
        cfg_act.setIcon(si("SP_FileDialogInfoView"))
        about_act = menu.addAction("About Externo Browser", self._show_about)
        about_act.setIcon(si("SP_MessageBoxInformation"))

        pos = self.nav_bar.ext_btn.mapToGlobal(
            self.nav_bar.ext_btn.rect().bottomRight())
        pos.setX(pos.x() - menu.sizeHint().width())
        menu.exec(pos)

    # ── Settings dialog ────────────────────────────────────────────────────────

    def _show_settings(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Settings — Externo Browser")
        dlg.setMinimumWidth(520)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {T('bg')}; color: {T('text')}; }}
            QGroupBox {{
                color: {T('accent')}; font-weight: bold; font-size: 13px;
                border: 1px solid {T('border')}; border-radius: 8px; margin-top: 10px;
                padding: 12px 10px 8px 10px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
            QLabel {{ color: {T('text')}; font-size: 13px; }}
            QPushButton {{
                background: {T('border')}; color: {T('text')};
                border: none; border-radius: 8px;
                padding: 8px 18px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {T('accent')}; color: #fff; }}
            QPushButton#danger {{ background: #5a1a1a; color: #ff6b6b; }}
            QPushButton#danger:hover {{ background: #c0392b; color: #fff; }}
            QLineEdit {{
                background: {T('field_bg')}; color: {T('text')};
                border: 1px solid {T('border')}; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # On startup
        startup = QGroupBox("On Startup")
        s_lay = QVBoxLayout(startup)
        s_lay.addWidget(QLabel("Opens the Externo new tab page"))
        layout.addWidget(startup)

        # Appearance
        appear = QGroupBox("Appearance")
        a_lay = QFormLayout(appear)
        a_lay.setSpacing(10)
        a_lay.addRow("Theme:", QLabel("Externo Dark"))
        a_lay.addRow("Font size:", QLabel(f"{int(self._zoom * 100)}%  (use Ctrl + / Ctrl − to adjust)"))
        layout.addWidget(appear)

        # Privacy
        priv = QGroupBox("Privacy & Security")
        p_lay = QVBoxLayout(priv)
        clear_btn = QPushButton("  Clear Browsing Data…")
        clear_btn.setIcon(_si("SP_TrashIcon"))
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(lambda: self._clear_data(dlg))
        p_lay.addWidget(clear_btn)
        layout.addWidget(priv)

        # Features
        feat = QGroupBox("Features (Coming Soon)")
        f_lay = QVBoxLayout(feat)
        for info in FeatureRegistry._features.values():
            f_lay.addWidget(QLabel(f"  {info['icon']}  {info['label']} — {'Enabled' if info['enabled'] else 'Coming soon'}"))
        layout.addWidget(feat)

        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        dlg.exec()

    def _clear_data(self, parent):
        QWebEngineProfile.defaultProfile().clearAllVisitedLinks()
        QWebEngineProfile.defaultProfile().cookieStore().deleteAllCookies()
        lbl = QDialog(parent)
        lbl.setWindowTitle("Done")
        lbl.setStyleSheet(f"QDialog {{ background: {T('bg')}; }} QLabel {{ color: {T('text')}; padding: 16px; }}")
        v = QVBoxLayout(lbl)
        v.addWidget(QLabel("Browsing data cleared."))
        ok = QPushButton("OK")
        ok.setStyleSheet(f"QPushButton {{ background: {T('accent')}; color: #fff; border: none; border-radius: 6px; padding: 6px 16px; }}")
        ok.clicked.connect(lbl.accept)
        v.addWidget(ok, alignment=Qt.AlignmentFlag.AlignRight)
        lbl.exec()

    # ── About dialog ───────────────────────────────────────────────────────────

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("About Externo Browser")
        dlg.setFixedSize(380, 260)
        dlg.setStyleSheet(f"""
            QDialog {{ background: {T('bg')}; }}
            QLabel {{ color: {T('text')}; }}
        """)
        v = QVBoxLayout(dlg)
        v.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.setSpacing(10)
        v.setContentsMargins(30, 30, 30, 20)

        logo = LogoWidget(56)
        v.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)

        name = QLabel("EXTERNO BROWSER")
        name.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        name.setStyleSheet(f"color: {T('brand')}; letter-spacing: 4px;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(name)

        v.addWidget(QLabel("Version 1.0.0  •  Built with PyQt6 + Chromium"),
                    alignment=Qt.AlignmentFlag.AlignHCenter)

        v.addWidget(QLabel("Fast. Private. Yours."),
                    alignment=Qt.AlignmentFlag.AlignHCenter)

        made_by = QLabel("Made by Space")
        made_by.setAlignment(Qt.AlignmentFlag.AlignCenter)
        made_by.setStyleSheet(f"color: {T('dim')}; font-size: 11px;")
        v.addWidget(made_by)

        ok = QPushButton("Close")
        ok.setStyleSheet(f"""
            QPushButton {{
                background: {T('accent')}; color: #fff; border: none;
                border-radius: 8px; padding: 8px 24px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {T('accent_hv')}; }}
        """)
        ok.clicked.connect(dlg.accept)
        v.addWidget(ok, alignment=Qt.AlignmentFlag.AlignHCenter)
        dlg.exec()

    # ── Tab management ─────────────────────────────────────────────────────────

    # ── Externo internal navigation ────────────────────────────────────────────

    def _on_externo_nav(self, url_str: str):
        parsed = urlparse(url_str)
        if parsed.netloc == "add-shortcut":
            self._show_add_shortcut_dialog()
        elif parsed.netloc == "remove-shortcut":
            url = unquote(parse_qs(parsed.query).get("url", [""])[0])
            if url:
                ShortcutsManager.get().remove(url)
                self._go_home()
        elif parsed.netloc == "history":
            self._show_history_page()
        elif parsed.netloc == "clear-history":
            HistoryManager.get().clear()
            self._show_history_page()

    def _show_add_shortcut_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Shortcut")
        dlg.setFixedWidth(380)
        dlg.setStyleSheet(f"""
            QDialog   {{ background: {T('bg')}; color: {T('text')}; }}
            QLabel    {{ color: {T('text')}; font-size: 13px; }}
            QLineEdit {{
                background: {T('field_bg')}; color: {T('text')};
                border: 1.5px solid {T('border')}; border-radius: 8px;
                padding: 8px 12px; font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {T('accent')}; }}
            QPushButton {{
                background: {T('border')}; color: {T('text')};
                border: none; border-radius: 8px;
                padding: 8px 18px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {T('accent')}; color: #fff; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(22, 22, 22, 18)

        title_lbl = QLabel("Add Shortcut")
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {T('brand')};")
        layout.addWidget(title_lbl)
        layout.addSpacing(4)

        layout.addWidget(QLabel("Name  (optional)"))
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("My Website")
        layout.addWidget(name_edit)

        layout.addWidget(QLabel("URL"))
        url_edit = QLineEdit()
        url_edit.setPlaceholderText("https://example.com")
        layout.addWidget(url_edit)
        layout.addSpacing(6)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dlg.reject)
        add_btn = QPushButton("Add")
        add_btn.setDefault(True)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T('accent')}; color: #08121e; font-weight: bold;
                border: none; border-radius: 8px; padding: 8px 22px; font-size: 13px;
            }}
            QPushButton:hover {{ background: {T('accent_hv')}; }}
        """)
        add_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        url = url_edit.text().strip()
        if not url:
            return
        if not url.startswith("http"):
            url = "https://" + url
        name = name_edit.text().strip() or (urlparse(url).hostname or url).replace("www.", "")
        ShortcutsManager.get().add(name, url)
        self._go_home()

    # ── Auto-updater ───────────────────────────────────────────────────────────

    def _check_for_updates(self):
        import threading, urllib.request
        sig = _UpdateSignal(self)
        sig.found.connect(self._on_update_found)

        def _worker():
            try:
                with urllib.request.urlopen(UPDATE_CHECK_URL, timeout=8) as r:
                    data = json.loads(r.read())
                v   = data.get("version", "")
                url = data.get("download_url", "")
                notes = data.get("notes", "")
                if _version_gt(v, VERSION) and url:
                    sig.found.emit(v, url, notes)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _on_update_found(self, version: str, download_url: str, notes: str):
        self.update_bar.show_update(
            version, notes,
            lambda: self._download_update(download_url))

    def _download_update(self, download_url: str):
        import threading, tempfile, zipfile, urllib.request
        self.update_bar.set_status("Downloading update…")

        sig = _UpdateSignal(self)
        sig.download_done.connect(self._install_update)
        sig.download_failed.connect(
            lambda err: self.update_bar.set_status(
                f"Download failed: {err}", "Retry",
                lambda: self._download_update(download_url)))

        def _worker():
            try:
                tmp = tempfile.mkdtemp(prefix="externo_upd_")
                zip_path = os.path.join(tmp, "update.zip")
                urllib.request.urlretrieve(download_url, zip_path)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmp)
                os.unlink(zip_path)
                # write the swap batch
                if getattr(sys, "frozen", False):
                    install_dir = os.path.dirname(sys.executable)
                else:
                    install_dir = os.path.join(
                        os.environ.get("LOCALAPPDATA", ""),
                        "Externo Browser", "Externo Browser")
                bat = os.path.join(tmp, "update.bat")
                with open(bat, "w") as f:
                    f.write(
                        f"@echo off\n"
                        f"timeout /t 3 /nobreak >nul\n"
                        f'xcopy /E /Y /I "{tmp}\\Externo Browser\\*" "{install_dir}\\"\n'
                        f'start "" "{os.path.join(install_dir, "Externo Browser.exe")}"\n'
                        f'rd /s /q "{tmp}"\n'
                        f"del \"%~f0\"\n")
                sig.download_done.emit(bat)
            except Exception as exc:
                sig.download_failed.emit(str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _install_update(self, bat_path: str):
        import subprocess
        self.update_bar.set_status("Installing… browser will restart in a moment.")
        QTimer.singleShot(800, lambda: (
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW),
            self.close()
        ))

    def _on_auth_changed(self):
        HistoryManager.reset()
        self.bookmark_bar.refresh()
        self.nav_bar.set_bookmarked(False)
        for view in self._views:
            if view.url().toString() in ("about:blank", ""):
                view.setHtml(_build_landing_html(), QUrl("about:blank"))

    def _go_home(self, view=None):
        v = view or self._cur()
        v.setHtml(_build_landing_html(), QUrl("about:blank"))
        self.nav_bar.set_url("")

    def _show_history_page(self, view=None):
        v = view or self._cur()
        v.setHtml(_build_history_html(), QUrl("about:blank"))
        self.nav_bar.set_url("externo://history")

    def new_tab(self, url=None):
        if not url or not isinstance(url, str) or url == self.HOME:
            url = self.HOME
        view = ExternoWebView()
        if url == self.HOME:
            view.setHtml(_build_landing_html(), QUrl("about:blank"))
        elif url == "externo://history":
            view.setHtml(_build_history_html(), QUrl("about:blank"))
        else:
            view.load(QUrl(url))
        view.sig_new_tab.connect(self.new_tab)
        view.sig_bookmark_me.connect(self._toggle_bookmark)
        view.sig_externo_nav.connect(self._on_externo_nav)

        idx = len(self._views)
        self._views.append(view)
        self.stack.addWidget(view)

        initial_title = "History" if url == "externo://history" else "New Tab"
        chip = TabChip(initial_title)
        chip.sig_select.connect(self._on_chip_select)
        chip.sig_close.connect(self._on_chip_close)
        self.title_bar.add_tab(chip)

        view.titleChanged.connect(lambda t, c=chip: c.set_title(t))
        view.urlChanged.connect(lambda u, v=view: self._on_url_changed(u, v))
        view.titleChanged.connect(lambda t, v=view: self._on_title_changed(t, v))
        view.loadStarted.connect(lambda v=view: self._on_load_started(v))
        view.loadProgress.connect(lambda p, v=view: self._on_load_progress(p, v))
        view.loadFinished.connect(lambda ok, v=view: self._on_load_finished(ok, v))

        self._switch(idx)

    def _on_chip_select(self, chip):
        self._switch(self.title_bar.index_of(chip))

    def _on_chip_close(self, chip):
        if self.title_bar.count() == 1:
            self.close()
            return
        idx = self.title_bar.index_of(chip)
        self._active_idx = max(0, idx - 1) if idx > 0 else 0
        view = self._views.pop(idx)
        self.stack.removeWidget(view)
        view.stop()
        view.deleteLater()
        self.title_bar.remove_tab(chip)
        self._switch(min(idx, len(self._views) - 1))

    def _switch(self, idx: int):
        self._active_idx = idx
        self.stack.setCurrentIndex(idx)
        self.title_bar.set_active(self.title_bar.tab_at(idx))
        url = self._views[idx].url().toString()
        if url in ("about:blank", ""):
            self.nav_bar.set_url("")
            self.nav_bar.set_bookmarked(False)
        else:
            self.nav_bar.set_url(url)
            self.nav_bar.set_bookmarked(BookmarkManager.get().has(url))
        self._update_nav_btns()

    def _cur(self) -> ExternoWebView:
        return self._views[self._active_idx]

    # ── Navbar wiring ──────────────────────────────────────────────────────────

    def _wire_navbar(self):
        nb = self.nav_bar
        nb.back_btn.clicked.connect(lambda: self._cur().back())
        nb.forward_btn.clicked.connect(lambda: self._cur().forward())
        nb.reload_btn.clicked.connect(lambda: self._cur().reload())
        nb.home_btn.clicked.connect(lambda: self._go_home())
        nb.sig_navigate.connect(lambda url: self._cur().load(QUrl(url)))
        nb.sig_bookmark_toggle.connect(self._toggle_bookmark)
        nb.sig_open_menu.connect(self._show_browser_menu)
        self.bookmark_bar.sig_navigate.connect(lambda url: self._cur().load(QUrl(url)))

    # ── View signals ───────────────────────────────────────────────────────────

    def _on_url_changed(self, url, view):
        if view is self._cur():
            u = url.toString()
            if u in ("about:blank", ""):
                pass  # url bar managed by _go_home / _show_history_page
            else:
                self.nav_bar.set_url(u)
                self.nav_bar.set_bookmarked(BookmarkManager.get().has(u))

    def _on_title_changed(self, title, view):
        if view is self._cur():
            self.setWindowTitle(f"{title}  —  Externo Browser" if title else "Externo Browser")
        url = view.url().toString()
        if url and url not in ("about:blank", "") and not url.startswith("externo://"):
            HistoryManager.get().add(url, title)

    def _on_load_started(self, view):
        if view is self._cur():
            self.progress.setVisible(True)
            self._sb.showMessage("Loading…")

    def _on_load_progress(self, p, view):
        if view is self._cur():
            self.progress.setValue(p)

    def _on_load_finished(self, ok, view):
        if view is self._cur():
            self.progress.setVisible(False)
            self._sb.showMessage("Done" if ok else "Failed to load page")
        self._update_nav_btns()

    def _update_nav_btns(self):
        h = self._cur().history()
        self.nav_bar.back_btn.setEnabled(h.canGoBack())
        self.nav_bar.forward_btn.setEnabled(h.canGoForward())

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _make_progress(self):
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(3)
        bar.setVisible(False)
        bar.setStyleSheet(f"""
            QProgressBar {{ background: {T('border')}; border: none; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {T('accent')}, stop:1 {T('accent2')});
            }}
        """)
        return bar

    def _make_statusbar(self):
        sb = QStatusBar()
        sb.setStyleSheet(f"""
            QStatusBar {{
                background: {T('titlebar')}; color: {T('dim')};
                font-size: 11px; border-top: 1px solid {T('border')};
                padding-left: 8px;
            }}
        """)
        self.setStatusBar(sb)
        return sb


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Externo Browser")
    window = ExternoBrowser()
    window.show()
    sys.exit(app.exec())
