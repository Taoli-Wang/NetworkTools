# -*- coding: utf-8 -*-
"""
Network Tools v4.6 — PyQt5 Edition
—————————————————————————————————
Tkinter → PyQt5 全量迁移，包含全部菜单、快捷键、对话框
"""

import json, csv, os, re, sys, shutil, socket, platform, subprocess, threading, datetime, queue, urllib.request

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QProgressBar, QDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QMenuBar, QAction, QSplitter,
    QGroupBox, QFrame, QMenu, QSystemTrayIcon, QStyle, QShortcut, QInputDialog,
    QSizePolicy, QComboBox, QRadioButton,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import (
    QFont, QIcon, QPixmap, QColor, QTextCursor, QPalette, QTextCharFormat,
    QKeySequence,
)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ============================================================
# 工具函数
# ============================================================

def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

def validate_target(target):
    if not target or len(target) > 253:
        return False
    ip_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ip_pattern, target):
        parts = target.split(".")
        return all(0 <= int(p) <= 255 for p in parts)
    domain_pattern = r"^([a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?$"
    return bool(re.match(domain_pattern, target)) and len(target) >= 3

# ============================================================
# 全局版本号 —— 改这里一处，全项目同步
# ============================================================
APP_VERSION = "v4.6"
ABOUT_INFO = {"version": APP_VERSION}

# ============================================================
# 快捷键注册表 —— 所有菜单和快捷绑定的单一数据源
# ============================================================
# 格式: (action_id, display_label, default_keys, menu_key_display)
# menu_key_display 为 None 时不显示快捷键文字
DEFAULT_SHORTCUTS = {
    "test_gateway":    ("内网网关测试",       "Ctrl+G",       "Ctrl+G"),
    "test_server":     ("内网关键服务器",    "Ctrl+S",       "Ctrl+S"),
    "test_lan_only":   ("全部内网测试",      "Ctrl+Shift+L", "Ctrl+Shift+L"),
    "test_wan":        ("外网网络测试",      "Ctrl+W",       "Ctrl+W"),
    "long_ping":       ("长Ping",            "Ctrl+P",       "Ctrl+P"),
    "tracert":         ("tracert 路由",      "Ctrl+T",       "Ctrl+T"),
    "tcping":          ("tcping",            "Ctrl+C",       "Ctrl+C"),
    "test_all":        ("运行全部测试",      "F5",           "F5"),
    "stop_all":        ("停止测试",          "Esc",          "Esc"),
    "save_log":        ("保存测试日志",      "Ctrl+D",       "Ctrl+D"),
    "clear_log":       ("清空日志区",        "Ctrl+L",       "Ctrl+L"),
    "open_ip_manager": ("IP地址管理",        "Ctrl+I",       None),  # 菜单不显示快捷键
    "calculator":      ("网络计算器",        "Ctrl+N",       None),
    "lan_scanner":     ("局域网扫描",        "Ctrl+Shift+N", None),
    "show_about":      ("关于",              "F1",           "F1"),
}


# ============================================================
# ConfigManager
# ============================================================

class ConfigManager:
    CONFIG_FILE = "config.json"
    DEFAULT = {
        "gateway_targets": [["192.168.0.1", "主网关"], ["192.168.1.1", "备用网关"]],
        "server_targets": [["10.0.0.1", "域控"], ["10.0.0.2", "文件服务器"]],
        "wan_targets": [["baidu.com", "百度"], ["qq.com", "腾讯"], ["google.com", "Google"]],
    }

    def __init__(self):
        self.config = {}
        self.load()

    def _config_path(self):
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(appdata, "NetworkTools")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, self.CONFIG_FILE)

    def load(self):
        path = self._config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                self._ensure_keys()
                return
            except:
                pass
        self.config = {k: list(v) for k, v in self.DEFAULT.items()}
        self.save()

    def _ensure_keys(self):
        for k, v in self.DEFAULT.items():
            self.config.setdefault(k, list(v))
        self.config.setdefault("logo_path", "")
        self.config.setdefault("shortcuts", {})
        # 多套方案支持
        self.config.setdefault("profiles", {})
        self.config.setdefault("active_profile", "默认方案")
        self.config.setdefault("data_source", "local")  # "local" or "database"
        # 确保默认方案存在
        if "默认方案" not in self.config["profiles"]:
            self.config["profiles"]["默认方案"] = {
                k: list(v) for k, v in self.DEFAULT.items()
            }

    def save(self):
        with open(self._config_path(), "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    # ---- 目标存取（基于当前生效方案） ----

    def get_targets(self, key):
        """获取当前数据源/方案下的 targets"""
        ds = self.config.get("data_source", "local")
        if ds == "database":
            return self.config.get("_db_cache", {}).get(key, [])
        profile = self.config.get("active_profile", "默认方案")
        return self.config.get("profiles", {}).get(profile, {}).get(key, [])

    def set_targets(self, key, targets):
        ds = self.config.get("data_source", "local")
        if ds == "database":
            self.config.setdefault("_db_cache", {})
            self.config["_db_cache"][key] = targets
        else:
            profile = self.config.get("active_profile", "默认方案")
            self.config.setdefault("profiles", {})
            self.config["profiles"].setdefault(profile, {})
            self.config["profiles"][profile][key] = targets

    # ---- 多套方案管理 ----

    def get_profiles(self):
        """返回所有方案名列表"""
        return list(self.config.get("profiles", {}).keys())

    def get_active_profile(self):
        return self.config.get("active_profile", "默认方案")

    def set_active_profile(self, name):
        self.config["active_profile"] = name
        self.save()

    def add_profile(self, name):
        if name in self.config.get("profiles", {}):
            return False
        self.config["profiles"][name] = {
            k: list(v) for k, v in self.DEFAULT.items()
        }
        self.save()
        return True

    def rename_profile(self, old, new):
        profiles = self.config.get("profiles", {})
        if old not in profiles or new in profiles:
            return False
        profiles[new] = profiles.pop(old)
        if self.config.get("active_profile") == old:
            self.config["active_profile"] = new
        self.save()
        return True

    def delete_profile(self, name):
        profiles = self.config.get("profiles", {})
        if name == "默认方案" or name not in profiles or len(profiles) <= 1:
            return False
        profiles.pop(name)
        if self.config.get("active_profile") == name:
            self.config["active_profile"] = "默认方案"
        self.save()
        return True

    # ---- 数据源 ----

    def get_data_source(self):
        return self.config.get("data_source", "local")

    def set_data_source(self, ds):
        self.config["data_source"] = ds
        self.save()

    def set_db_cache(self, key, targets):
        self.config.setdefault("_db_cache", {})
        self.config["_db_cache"][key] = targets
        self.save()

    def get_logo_path(self):
        return self.config.get("logo_path", "")

    def set_logo_path(self, path):
        self.config["logo_path"] = path
        self.save()

    def get_shortcuts(self):
        """返回用户自定义快捷键映射 {action_id: keys}，未自定义的返回 {}"""
        return self.config.get("shortcuts", {})

    def set_shortcut(self, action_id, keys):
        """设置单个快捷键，keys 为空字符串则恢复默认"""
        self.config.setdefault("shortcuts", {})
        if not keys:
            self.config["shortcuts"].pop(action_id, None)
        else:
            self.config["shortcuts"][action_id] = keys
        self.save()

    def reset_shortcuts(self):
        """全部快捷键恢复默认"""
        self.config["shortcuts"] = {}
        self.save()

    def reset_to_default(self):
        """仅重置当前方案的配置为默认值"""
        profile = self.config.get("active_profile", "默认方案")
        self.config.setdefault("profiles", {})
        self.config["profiles"][profile] = {
            k: list(v) for k, v in self.DEFAULT.items()
        }
        self.config.setdefault("logo_path", "")
        self.save()

    # ---- 数据库配置 ----

    def get_db_config(self):
        return self.config.setdefault("db_config", {
            "odbc_driver": "SQL Server",
            "host": "192.168.1.49",
            "database": "ForIT",
            "username": "ITDBUser",
            "password": "",
            "auth": "sql",
            "table_name": "ServerData",
            "col_ip": "ip_addr",
            "col_name": "Server_name",
            "col_group": "",
        })

    def set_db_config(self, cfg_dict):
        self.config["db_config"] = cfg_dict
        self.save()


# ============================================================
# NetworkTester
# ============================================================

def ping_host(ip, timeout_ms=300):
    """快速 ping，LAN 内 200-300ms 足够"""
    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        wt = max(1, timeout_ms // 1000)
        cmd = ["ping", "-c", "1", "-W", str(wt), ip]
    try:
        ret = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)
        return ret.returncode == 0
    except:
        return False


def _get_hostname(ip):
    """带超时的反向 DNS 查询"""
    import threading
    result = [""]
    def _resolve():
        try:
            result[0] = socket.gethostbyaddr(ip)[0]
        except:
            pass
    t = threading.Thread(target=_resolve, daemon=True)
    t.start()
    t.join(timeout=0.8)
    return result[0]


# ============================================================
# Worker Threads
# ============================================================

class ScanWorker(QThread):
    progress = pyqtSignal(int, int)
    found = pyqtSignal(str, str)
    finished = pyqtSignal(int, int)

    def __init__(self, network_base, prefix):
        super().__init__()
        self.network_base = network_base
        self.prefix = prefix
        self._running = True

    def stop(self):
        self._running = False

    def _scan_one(self, ip):
        """扫描单个 IP，返回 (ip, hostname) 或 None"""
        if not self._running:
            return None
        if ping_host(ip, timeout_ms=250):
            hn = _get_hostname(ip)
            return (ip, hn)
        return None

    def run(self):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        net_int = (self.network_base[0] << 24) | (self.network_base[1] << 16) | \
                  (self.network_base[2] << 8) | self.network_base[3]
        mask = (0xFFFFFFFF << (32 - self.prefix)) & 0xFFFFFFFF
        network = net_int & mask
        total = 1 << (32 - self.prefix)
        start, end = network + 1, network + total - 1
        ip_list = []
        for ip_int in range(start, end):
            ip_list.append(f"{(ip_int >> 24) & 0xFF}.{(ip_int >> 16) & 0xFF}.{(ip_int >> 8) & 0xFF}.{ip_int & 0xFF}")

        online = 0
        scanned = 0
        # 并行扫描，最多 80 个并发线程
        with ThreadPoolExecutor(max_workers=80) as pool:
            futures = {pool.submit(self._scan_one, ip): ip for ip in ip_list}
            for future in as_completed(futures):
                if not self._running:
                    break
                scanned += 1
                result = future.result()
                if result:
                    self.found.emit(result[0], result[1])
                    online += 1
                if scanned % 10 == 0:
                    self.progress.emit(scanned, total - 2)
        self.finished.emit(scanned, online)


class TestWorker(QThread):
    log = pyqtSignal(str, str)
    progress = pyqtSignal(int)
    stats = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self, targets):
        super().__init__()
        self.targets = targets
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        passed = failed = 0
        for i, (ip, name) in enumerate(self.targets):
            if self._stop:
                break
            ok = ping_host(ip)
            status = "通" if ok else "不通"
            tag = "pass" if ok else "fail"
            self.log.emit(f"  {status}  {ip}  ({name})", tag)
            if ok:
                passed += 1
            else:
                failed += 1
            self.progress.emit(i + 1)
            self.stats.emit(passed, failed)
        self.finished.emit()


# ============================================================
# 本机信息获取线程
# ============================================================

class InfoFetchWorker(QThread):
    """使用 QThread + pyqtSignal 可靠地将结果传递回主线程"""
    result_ready = pyqtSignal(str, str, str)

    def run(self):
        hn = "未知"
        try:
            hn = socket.gethostname()
        except Exception:
            pass

        lip = "获取中..."
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            lip = s.getsockname()[0]
            s.close()
        except Exception:
            try:
                lip = socket.gethostbyname(hn)
            except Exception:
                lip = "无法获取"

        wan = "获取中..."
        for url in ["https://checkip.amazonaws.com", "https://ipv4.icanhazip.com",
                    "https://ifconfig.me/ip"]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
                wan = urllib.request.urlopen(req, timeout=5).read().decode().strip()
                if wan:
                    break
            except Exception:
                continue
        else:
            wan = "无法获取"

        self.result_ready.emit(hn, lip, wan)


# ============================================================
# 数据库连接配置对话框
# ============================================================

class DBConfigDialog(QDialog):
    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("数据库连接设置")
        self.setFixedSize(480, 470)
        self.cfg = cfg
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        # 标题
        title = QLabel("SQL Server 数据源设置")
        title.setStyleSheet("font-size:14px; font-weight:bold; color:#1e293b;")
        layout.addWidget(title)
        sub = QLabel("保存后配置会使用当前 Windows 用户的 DPAPI 加密。")
        sub.setStyleSheet("font-size:10px; color:#8899aa;")
        layout.addWidget(sub)
        layout.addSpacing(8)

        self._fields = {}
        # ODBC 驱动
        form_top = [
            ("ODBC 驱动", "odbc_driver", "SQL Server"),
            ("服务器/实例", "host", None),
            ("数据库", "database", None),
            ("全部服务器表", "table_name", None),
            ("IP/域名列", "col_ip", None),
            ("名称/备注列", "col_name", None),
            ("分组列", "col_group", None),
        ]
        group_hint = QLabel("  分组列值示例：内网网关、内网服务器、外网地址（为空则全部归入内网网关）")
        group_hint.setStyleSheet("font-size:9px; color:#8899aa; padding-left:90px;")
        for label, key, default_text in form_top:
            row = QHBoxLayout()
            lb = QLabel(label)
            lb.setFixedWidth(90)
            lb.setStyleSheet("color:#556677; font-size:12px;")
            w = QLineEdit()
            if default_text and key == "odbc_driver":
                w.setText(default_text)
            w.setStyleSheet("padding:5px; font-size:12px; font-family:Consolas;")
            row.addWidget(lb)
            row.addWidget(w)
            layout.addLayout(row)
            self._fields[key] = w
        layout.addWidget(group_hint)
        layout.addSpacing(4)

        layout.addSpacing(6)
        # 认证方式
        auth_head = QLabel("认证方式")
        auth_head.setStyleSheet("font-size:11px; color:#8899aa; font-weight:bold;")
        layout.addWidget(auth_head)

        auth_row = QHBoxLayout()
        self._auth_windows = QRadioButton("Windows 身份验证")
        self._auth_sql = QRadioButton("SQL 身份验证")
        self._auth_sql.setChecked(True)
        auth_row.addWidget(self._auth_windows)
        auth_row.addWidget(self._auth_sql)
        auth_row.addStretch()
        layout.addLayout(auth_row)

        # 账号密码行（SQL 认证）
        self._sql_row = QWidget()
        sql_lay = QHBoxLayout(self._sql_row)
        sql_lay.setContentsMargins(0, 0, 0, 0)
        for label, key in [("账号", "username"), ("密码", "password")]:
            lb = QLabel(label)
            lb.setFixedWidth(40)
            lb.setStyleSheet("color:#556677; font-size:12px;")
            w = QLineEdit()
            if key == "password":
                w.setEchoMode(QLineEdit.Password)
            w.setStyleSheet("padding:5px; font-size:12px; font-family:Consolas;")
            sql_lay.addWidget(lb)
            sql_lay.addWidget(w)
            self._fields[key] = w
        layout.addWidget(self._sql_row)

        # 认证方式切换监听
        self._auth_sql.toggled.connect(self._on_auth_changed)
        self._auth_windows.toggled.connect(self._on_auth_changed)

        # 提示
        layout.addSpacing(2)
        tip = QLabel("表与列名只能含字母、数字和下划线；程序只读取配置的 IP/域名列与名称列。")
        tip.setStyleSheet("font-size:10px; color:#c0a020; background:#fffbe8; padding:4px 6px; border-radius:3px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # 按钮
        layout.addSpacing(4)
        btns = QHBoxLayout()
        btn_test = QPushButton("测试连接")
        btn_test.setStyleSheet("background:#5a8a5a; color:#fff; padding:6px 14px; border-radius:4px;")
        btn_test.clicked.connect(self._test)
        btn_cancel = QPushButton("取消")
        btn_cancel.setStyleSheet("padding:6px 14px;")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("保存")
        btn_save.setStyleSheet("background:#4a6fa5; color:#fff; padding:6px 14px; border-radius:4px;")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._save_and_close)
        btns.addWidget(btn_test)
        btns.addStretch()
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _on_auth_changed(self):
        """SQL 身份验证时显示账号密码，Windows 认证时隐藏"""
        self._sql_row.setVisible(self._auth_sql.isChecked())

    def _load(self):
        db = self.cfg.get_db_config()
        for key, w in self._fields.items():
            val = db.get(key, "")
            w.setText(str(val) if val else "")
        # 认证方式
        auth = db.get("auth", "sql")
        if auth == "windows":
            self._auth_windows.setChecked(True)
        else:
            self._auth_sql.setChecked(True)
        self._on_auth_changed()

    def _save_and_close(self):
        data = {}
        for key, w in self._fields.items():
            data[key] = w.text()
        data["auth"] = "windows" if self._auth_windows.isChecked() else "sql"
        data["type"] = "SQL Server"
        data["port"] = 1433
        self.cfg.set_db_config(data)
        self.accept()

    def _test(self):
        data = {}
        for key, w in self._fields.items():
            data[key] = w.text()
        data["auth"] = "windows" if self._auth_windows.isChecked() else "sql"
        try:
            self._fetch_from_db(data)
            QMessageBox.information(self, "测试成功", "连接成功，已能读取表结构。")
        except Exception as e:
            QMessageBox.critical(self, "测试失败", f"连接出错：\n{e}")

    def _fetch_from_db(self, db):
        """实际连接数据库并查询，返回 [(ip, name), ...]"""
        import pyodbc
        driver = db.get("odbc_driver") or "SQL Server"
        if db.get("auth") == "windows":
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={db['host']};"
                f"DATABASE={db['database']};Trusted_Connection=yes;"
            )
        else:
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={db['host']};"
                f"DATABASE={db['database']};UID={db['username']};PWD={db['password']}"
            )
        import re
        if not re.match(r"^[\w\d_]+$", db.get("table_name", "")):
            raise ValueError(f"表名不合法：{db.get('table_name', '')}")
        if not re.match(r"^[\w\d_]+$", db.get("col_ip", "")):
            raise ValueError(f"IP列名不合法：{db.get('col_ip', '')}")
        if not re.match(r"^[\w\d_]+$", db.get("col_name", "")):
            raise ValueError(f"名称列名不合法：{db.get('col_name', '')}")
        conn = pyodbc.connect(conn_str, timeout=5)
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT [{db['col_ip']}], [{db['col_name']}] FROM [{db['table_name']}]")
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()
        return [(str(r[0]) if r[0] is not None else "",
                 str(r[1]) if r[1] is not None else str(r[0]))
                for r in rows]
        QMessageBox.information(self, "测试结果",
            f"尝试连接 {data['type']}://{data['host']}:{data['port']}/{data['database']}\n"
            "（当前为模拟模式，实际对接数据库后可替换为真实连接测试）")


# ============================================================
# IP 地址管理对话框
# ============================================================

class IPManagerDialog(QDialog):
    TAB_KEYS = [("内网网关", "gateway_targets"), ("内网服务器", "server_targets"), ("外网地址", "wan_targets")]

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.setWindowTitle("IP 地址管理")
        self.resize(880, 680)
        self.setMinimumSize(620, 500)
        self.cfg = cfg
        self._db_locked = False  # 数据库模式下禁用编辑按钮
        self._build_ui()
        self._refresh_all()

    # ================================================================
    #  UI 构建
    # ================================================================

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)

        # ---- 顶部：数据源切换 + 方案管理 ----
        top_bar = QHBoxLayout()

        # Segmented Control 风格切换
        src_grp = QHBoxLayout()
        src_grp.setSpacing(0)
        self._btn_local = QPushButton("本地内置")
        self._btn_local.setCheckable(True)
        self._btn_db = QPushButton("数据库连接")
        self._btn_db.setCheckable(True)
        for b in (self._btn_local, self._btn_db):
            b.setFixedHeight(30)
            b.clicked.connect(self._on_switch_source)
        src_grp.addWidget(self._btn_local)
        src_grp.addWidget(self._btn_db)
        top_bar.addLayout(src_grp)

        # 状态徽章
        self._badge = QPushButton()
        self._badge.setFlat(True)
        self._badge.setEnabled(False)
        self._badge.setStyleSheet("font-size:10px; font-weight:bold; padding:2px 10px; border-radius:10px;")
        top_bar.addWidget(self._badge)
        top_bar.addStretch()

        # 方案选择器（仅本地模式可见）
        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(100)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        self._btn_add_profile = QPushButton("+")
        self._btn_add_profile.setFixedSize(28, 28)
        self._btn_add_profile.setToolTip("新增方案")
        self._btn_add_profile.clicked.connect(self._on_add_profile)
        self._btn_profile_menu = QPushButton("...")
        self._btn_profile_menu.setFixedSize(28, 28)
        self._btn_profile_menu.setToolTip("方案操作")
        self._btn_profile_menu.clicked.connect(self._on_profile_menu)
        top_bar.addWidget(self._profile_combo)
        top_bar.addWidget(self._btn_add_profile)
        top_bar.addWidget(self._btn_profile_menu)
        top_bar.addStretch()

        # 数据库模式按钮（仅数据库模式可见）
        self._btn_db_config = QPushButton("⚙ 配置")
        self._btn_db_config.clicked.connect(self._on_db_config)
        self._btn_db_config.setVisible(False)
        self._btn_db_sync = QPushButton("🔄 同步")
        self._btn_db_sync.clicked.connect(self._on_db_sync)
        self._btn_db_sync.setVisible(False)
        self._btn_db_import = QPushButton("📥 导入到本地")
        self._btn_db_import.clicked.connect(self._on_db_import)
        self._btn_db_import.setVisible(False)
        self._btn_db_import.setToolTip("将数据库数据复制到当前本地方案，以便编辑")
        self._btn_db_clear = QPushButton("🗑 清除数据")
        self._btn_db_clear.clicked.connect(self._on_db_clear)
        self._btn_db_clear.setVisible(False)
        self._btn_db_clear.setToolTip("清除从数据库同步过来的缓存数据，避免残留")
        self._btn_db_clear.setStyleSheet("color:#b8585b;")
        top_bar.addWidget(self._btn_db_config)
        top_bar.addWidget(self._btn_db_sync)
        top_bar.addWidget(self._btn_db_import)
        top_bar.addWidget(self._btn_db_clear)

        layout.addLayout(top_bar)

        # ---- 标签页 ----
        self.tabs = QTabWidget()
        self._tables = {}
        self._btn_rows = {}  # 每页的按钮容器，用于禁用/启用
        self._ip_inputs = {}
        self._name_inputs = {}

        for title, key in self.TAB_KEYS:
            tab = QWidget()
            tl = QVBoxLayout(tab)
            tl.setContentsMargins(4, 4, 4, 4)

            tw = QTableWidget(0, 2)
            tw.setHorizontalHeaderLabels(["IP/域名", "名称/备注"])
            tw.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            tw.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            tw.setSelectionBehavior(QTableWidget.SelectRows)
            tw.setSelectionMode(QTableWidget.ExtendedSelection)
            tw.setEditTriggers(QTableWidget.NoEditTriggers)
            tw.currentCellChanged.connect(lambda r, c, pr, pc, k=key: self._on_select(k, r))
            self._tables[key] = tw

            ie = QLineEdit()
            ie.setPlaceholderText("IP/域名")
            ne = QLineEdit()
            ne.setPlaceholderText("名称/备注")
            self._ip_inputs[key] = ie
            self._name_inputs[key] = ne
            input_row = QHBoxLayout()
            input_row.addWidget(ie)
            input_row.addWidget(ne)
            tl.addLayout(input_row)

            btn_container = QWidget()
            btn_row = QHBoxLayout(btn_container)
            btn_row.setContentsMargins(0, 0, 0, 0)
            for label, func in [("添加", self._on_add), ("删除", self._on_delete),
                                ("编辑", self._on_edit), ("上移", self._on_move_up),
                                ("下移", self._on_move_down)]:
                btn = QPushButton(label)
                btn.setMinimumWidth(52)
                btn.clicked.connect(lambda _, k=key, f=func: f(k))
                btn_row.addWidget(btn)
            btn_row.addStretch()
            self._btn_rows[key] = btn_container
            tl.addWidget(btn_container)

            tl.addWidget(tw)

            hint = QLabel("支持 IP 地址和域名输入，均可 Ping 测试")
            hint.setStyleSheet("color:#aab2bd; font-size:9pt;")
            tl.addWidget(hint)

            self.tabs.addTab(tab, title)
        layout.addWidget(self.tabs)

        # ---- 底部 ----
        btns = QHBoxLayout()
        for label, func in [("保存配置", self._save_all), ("恢复默认", self._reset),
                            ("导出CSV", self._export_csv), ("导入CSV", self._import_csv)]:
            b = QPushButton(label)
            b.clicked.connect(func)
            btns.addWidget(b)
        btns.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.close)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

        # 初始状态
        self._apply_source_style()

    # ================================================================
    #  样式刷新
    # ================================================================

    def _apply_source_style(self):
        is_local = self.cfg.get_data_source() == "local"
        self._btn_local.setChecked(is_local)
        self._btn_db.setChecked(not is_local)
        for b, active in [(self._btn_local, is_local), (self._btn_db, not is_local)]:
            if active:
                b.setStyleSheet("background:#4a6fa5; color:#fff; font-weight:bold; "
                                "border:1px solid #3a5f95; padding:4px 16px; font-size:11px;")
            else:
                b.setStyleSheet("background:#eef3f8; color:#5a6877; "
                                "border:1px solid #d0dce8; padding:4px 16px; font-size:11px;")

        self._db_locked = not is_local
        self._profile_combo.setVisible(is_local)
        self._btn_add_profile.setVisible(is_local)
        self._btn_profile_menu.setVisible(is_local)
        self._btn_db_config.setVisible(not is_local)
        self._btn_db_sync.setVisible(not is_local)
        self._btn_db_import.setVisible(not is_local)
        self._btn_db_clear.setVisible(not is_local)
        for key in dict(self._btn_rows):
            self._btn_rows[key].setVisible(is_local)

        if is_local:
            profile = self.cfg.get_active_profile()
            self._badge.setText(f"✓ 本地模式 · {profile}")
            self._badge.setStyleSheet(
                "font-size:10px; font-weight:bold; padding:2px 10px; border-radius:10px; "
                "background:#e0edff; color:#4a6fa5; border:1px solid #bdd4f0;")
        else:
            self._badge.setText("🔒 数据库只读")
            self._badge.setStyleSheet(
                "font-size:10px; font-weight:bold; padding:2px 10px; border-radius:10px; "
                "background:#e6f4e6; color:#5a8a5a; border:1px solid #b8dbb8;")

    # ================================================================
    #  数据刷新
    # ================================================================

    def _refresh_all(self):
        self._refresh_profiles()
        self._load_all()

    def _refresh_profiles(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        profiles = self.cfg.get_profiles()
        active = self.cfg.get_active_profile()
        self._profile_combo.addItems(profiles)
        if active in profiles:
            self._profile_combo.setCurrentText(active)
        self._profile_combo.blockSignals(False)

    def _load_all(self):
        for key, tw in self._tables.items():
            tw.setRowCount(0)
            for ip, name in self.cfg.get_targets(key):
                r = tw.rowCount()
                tw.insertRow(r)
                tw.setItem(r, 0, QTableWidgetItem(ip))
                tw.setItem(r, 1, QTableWidgetItem(name))

    # ================================================================
    #  数据源切换
    # ================================================================

    def _on_switch_source(self):
        sender = self.sender()
        current = self.cfg.get_data_source()
        if sender == self._btn_local and current == "local":
            return
        if sender == self._btn_db and current == "database":
            return
        new_ds = "local" if sender == self._btn_local else "database"
        self.cfg.set_data_source(new_ds)
        self._apply_source_style()
        self._load_all()

    def _on_db_config(self):
        dlg = DBConfigDialog(self, self.cfg)
        if dlg.exec_() == QDialog.Accepted:
            self._apply_source_style()

    def _on_db_sync(self):
        db = self.cfg.get_db_config()
        try:
            rows_by_group = self._fetch_from_db(db)
        except Exception as e:
            QMessageBox.critical(self, "同步失败", f"连接或查询出错：\n{e}")
            return
        total = sum(len(v) for v in rows_by_group.values())
        if total == 0:
            QMessageBox.warning(self, "同步结果", "数据库中无数据或查询为空")
            return
        self.cfg.config["_db_cache"] = rows_by_group
        self._load_all()
        parts = []
        for k, v in rows_by_group.items():
            if v:
                parts.append(f"{k}={len(v)}条")
        QMessageBox.information(self, "同步完成",
            f"已从 {db['host']} / {db['database']}.{db['table_name']}\n"
            f"读取 {total} 条记录（{', '.join(parts)}）")

    def _fetch_from_db(self, db):
        """ODBC 连接数据库并返回 {gateway_targets: [(ip,name),...], ...} 字典"""
        import pyodbc
        driver = db.get("odbc_driver") or "SQL Server"
        if db.get("auth") == "windows":
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={db['host']};"
                f"DATABASE={db['database']};Trusted_Connection=yes;"
            )
        else:
            conn_str = (
                f"DRIVER={{{driver}}};SERVER={db['host']};"
                f"DATABASE={db['database']};UID={db['username']};PWD={db['password']}"
            )
        import re
        for k in ("table_name", "col_ip", "col_name"):
            if not re.match(r"^[\w\d_]+$", db.get(k, "")):
                raise ValueError(f"名称不合法：{k}={db.get(k, '')}")
        # col_group 可选
        col_grp = db.get("col_group", "").strip()

        conn = pyodbc.connect(conn_str, timeout=5)
        try:
            cur = conn.cursor()
            if col_grp and re.match(r"^[\w\d_]+$", col_grp):
                cur.execute(f"SELECT [{db['col_ip']}], [{db['col_name']}], [{col_grp}] FROM [{db['table_name']}]")
            else:
                cur.execute(f"SELECT [{db['col_ip']}], [{db['col_name']}] FROM [{db['table_name']}]")
            rows = cur.fetchall()
            cur.close()
        finally:
            conn.close()

        group_map = {"内网网关": "gateway_targets", "内网服务器": "server_targets", "外网地址": "wan_targets"}
        result = {k: [] for k in group_map.values()}
        for r in rows:
            ip = str(r[0]) if r[0] is not None else ""
            name = str(r[1]) if r[1] is not None else ip
            if not ip or not validate_target(ip):
                continue
            if len(r) >= 3 and col_grp:
                grp = str(r[2]) if r[2] is not None else ""
                key = group_map.get(grp, "gateway_targets")
            else:
                key = "gateway_targets"
            result[key].append((ip, name))
        return result

    def _on_db_import(self):
        """将数据库缓存的数据导入到当前本地方案"""
        cache = self.cfg.config.get("_db_cache", {})
        total = sum(len(v) for v in cache.values())
        if total == 0:
            QMessageBox.warning(self, "无数据", "请先点击「同步」从数据库获取数据")
            return
        # 合并到当前本地方案
        for key in ["gateway_targets", "server_targets", "wan_targets"]:
            db_rows = cache.get(key, [])
            if not db_rows:
                continue
            local = self.cfg.get_targets(key)
            local_ips = {e[0] for e in local}
            added = 0
            for ip, name in db_rows:
                if ip not in local_ips:
                    local.append((ip, name))
                    local_ips.add(ip)
                    added += 1
            if added:
                self.cfg.set_targets(key, local)
        self.cfg.save()
        # 可选：自动切换到本地模式
        if self.cfg.get_data_source() == "database":
            self.cfg.set_data_source("local")
            self._apply_source_style()
            self._load_all()
        QMessageBox.information(self, "导入完成",
            f"已将 {total} 条数据库记录合并到当前本地方案\n（自动去重，已切换到本地模式）")

    def _on_db_clear(self):
        """清除数据库缓存数据"""
        cache = self.cfg.config.get("_db_cache", {})
        total = sum(len(v) for v in cache.values())
        if total == 0:
            QMessageBox.information(self, "无数据", "当前没有缓存的数据库数据")
            return
        if QMessageBox.question(self, "确认清除",
            f"确定清除全部 {total} 条数据库缓存记录吗？\n（清除后不可恢复，除非重新同步数据库）") != QMessageBox.Yes:
            return
        self.cfg.config["_db_cache"] = {}
        self.cfg.save()
        self._load_all()
        QMessageBox.information(self, "已清除", "数据库缓存数据已全部清除")

    # ================================================================
    #  方案管理
    # ================================================================

    def _on_profile_changed(self):
        name = self._profile_combo.currentText()
        if name and name != self.cfg.get_active_profile():
            self.cfg.set_active_profile(name)
            self._apply_source_style()
            self._load_all()

    def _on_add_profile(self):
        name, ok = QInputDialog.getText(self, "新增方案", "方案名称:")
        if ok and name.strip():
            name = name.strip()
            if not self.cfg.add_profile(name):
                QMessageBox.warning(self, "提示", f"方案「{name}」已存在")
                return
            self._refresh_profiles()
            self._profile_combo.setCurrentText(name)
            self.cfg.set_active_profile(name)
            self._apply_source_style()
            self._load_all()

    def _on_profile_menu(self):
        menu = QMenu(self)
        rename_act = menu.addAction("重命名当前方案")
        del_act = menu.addAction("删除当前方案")
        del_act.setEnabled(self.cfg.get_active_profile() != "默认方案")
        action = menu.exec_(self._btn_profile_menu.mapToGlobal(self._btn_profile_menu.rect().bottomLeft()))
        if action == rename_act:
            self._on_rename_profile()
        elif action == del_act:
            self._on_delete_profile()

    def _on_rename_profile(self):
        old = self.cfg.get_active_profile()
        new, ok = QInputDialog.getText(self, "重命名方案", "新名称:", text=old)
        if ok and new.strip() and new.strip() != old:
            new = new.strip()
            if not self.cfg.rename_profile(old, new):
                QMessageBox.warning(self, "提示", f"方案「{new}」已存在或操作失败")
                return
            self._refresh_profiles()
            self._apply_source_style()

    def _on_delete_profile(self):
        name = self.cfg.get_active_profile()
        if name == "默认方案":
            return
        if QMessageBox.question(self, "确认删除", f"确定删除方案「{name}」吗？\n该方案下的所有数据将丢失。") == QMessageBox.Yes:
            if not self.cfg.delete_profile(name):
                QMessageBox.warning(self, "提示", "删除失败，至少保留一个方案")
                return
            self._refresh_profiles()
            self._apply_source_style()
            self._load_all()

    # ================================================================
    #  表格行操作（数据库模式自动拦截）
    # ================================================================

    def _check_editable(self, key):
        if self._db_locked:
            QMessageBox.warning(self, "只读提示",
                "当前为数据库只读模式，请切换至「本地内置」进行编辑")
            return False
        return True

    def _on_select(self, key, row):
        tw = self._tables[key]
        if row >= 0 and row < tw.rowCount():
            self._ip_inputs[key].setText(tw.item(row, 0).text())
            self._name_inputs[key].setText(tw.item(row, 1).text())

    def _on_add(self, key):
        if not self._check_editable(key):
            return
        ip = self._ip_inputs[key].text().strip()
        name = self._name_inputs[key].text().strip() or ip
        if not ip:
            QMessageBox.warning(self, "提示", "IP/域名不能为空")
            return
        if not validate_target(ip):
            QMessageBox.warning(self, "提示", f"格式错误: {ip}")
            return
        targets = self.cfg.get_targets(key)
        if any(ip == t[0] for t in targets):
            QMessageBox.warning(self, "提示", f"目标 {ip} 已存在")
            return
        targets.append((ip, name))
        self.cfg.set_targets(key, targets)
        self._load_all()
        self._ip_inputs[key].clear()
        self._name_inputs[key].clear()

    def _on_delete(self, key):
        if not self._check_editable(key):
            return
        tw = self._tables[key]
        rows = set(idx.row() for idx in tw.selectedIndexes())
        if not rows:
            QMessageBox.warning(self, "提示", "请先选中要删除的行")
            return
        count = len(rows)
        if count == 1:
            row = rows.pop()
            ip = tw.item(row, 0).text()
            if QMessageBox.question(self, "确认删除", f"确定删除 {ip} 吗？") != QMessageBox.Yes:
                return
        else:
            if QMessageBox.question(self, "确认删除", f"确定删除选中的 {count} 条记录吗？") != QMessageBox.Yes:
                return
        ips = {tw.item(r, 0).text() for r in rows}
        targets = [(i, n) for i, n in self.cfg.get_targets(key) if i not in ips]
        self.cfg.set_targets(key, targets)
        self._load_all()

    def _on_edit(self, key):
        if not self._check_editable(key):
            return
        tw = self._tables[key]
        row = tw.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先选中一行")
            return
        ip = tw.item(row, 0).text()
        name = tw.item(row, 1).text()
        self._ip_inputs[key].setText(ip)
        self._name_inputs[key].setText(name)
        self._on_delete(key)

    def _on_move_up(self, key):
        if not self._check_editable(key):
            return
        tw = self._tables[key]
        row = tw.currentRow()
        if row <= 0:
            return
        targets = self.cfg.get_targets(key)
        targets[row], targets[row - 1] = targets[row - 1], targets[row]
        self.cfg.set_targets(key, targets)
        self._load_all()
        tw.setCurrentCell(row - 1, 0)

    def _on_move_down(self, key):
        if not self._check_editable(key):
            return
        tw = self._tables[key]
        row = tw.currentRow()
        targets = self.cfg.get_targets(key)
        if row < 0 or row >= len(targets) - 1:
            return
        targets[row], targets[row + 1] = targets[row + 1], targets[row]
        self.cfg.set_targets(key, targets)
        self._load_all()
        tw.setCurrentCell(row + 1, 0)

    # ================================================================
    #  保存 / 重置 / 导入导出
    # ================================================================

    def _save_all(self):
        self.cfg.save()
        QMessageBox.information(self, "成功", "当前配置已保存")

    def _reset(self):
        profile = self.cfg.get_active_profile()
        if QMessageBox.question(self, "确认",
            f"确定恢复「{profile}」为默认配置吗？\n该方案下所有自定义修改将丢失。") == QMessageBox.Yes:
            self.cfg.reset_to_default()
            self._load_all()
            QMessageBox.information(self, "成功", f"「{profile}」已恢复默认")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 CSV", "ip_addresses.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        labels = {k: lb for lb, k in self.TAB_KEYS}
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["分组", "IP/域名", "名称/备注"])
                for lb, k in self.TAB_KEYS:
                    for ip, name in self.cfg.get_targets(k):
                        w.writerow([lb, ip, name])
            QMessageBox.information(self, "成功", f"已导出到:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入 CSV", "", "CSV 文件 (*.csv)")
        if not path:
            return
        if self._db_locked:
            QMessageBox.warning(self, "只读提示", "数据库模式下不支持导入，请切换至本地内置")
            return
        labels = {lb: k for lb, k in self.TAB_KEYS}
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                hdr = next(reader, None)
                if not hdr or len(hdr) < 3:
                    raise ValueError("表头需: 分组,IP/域名,名称/备注")
                imported = {}
                for row in reader:
                    if len(row) < 3:
                        continue
                    cat, ip, name = row[0].strip(), row[1].strip(), row[2].strip() or ip
                    if not ip or not validate_target(ip):
                        continue
                    k = labels.get(cat)
                    if not k:
                        continue
                    imported.setdefault(k, [])
                    if any(ip == e[0] for e in imported[k]):
                        continue
                    imported[k].append((ip, name))
            added = 0
            for k, entries in imported.items():
                existing = self.cfg.get_targets(k)
                ex_ips = {e[0] for e in existing}
                for ip, name in entries:
                    if ip not in ex_ips:
                        existing.append((ip, name))
                        ex_ips.add(ip)
                        added += 1
                self.cfg.set_targets(k, existing)
            self._load_all()
            QMessageBox.information(self, "导入完成",
                f"成功导入 {added} 条记录\n（已自动跳过重复项和无效行）")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))


# ============================================================
# 网络计算器
# ============================================================

class CalculatorDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("网络计算器")
        self.setFixedSize(480, 490)
        self._build_ui()

    @staticmethod
    def _ip_int(ip):
        p = [int(x) for x in ip.split(".")]
        if any(n < 0 or n > 255 for n in p):
            raise ValueError("每段 0~255")
        return (p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]

    @staticmethod
    def _int_ip(n):
        return f"{(n>>24)&0xFF}.{(n>>16)&0xFF}.{(n>>8)&0xFF}.{n&0xFF}"

    @staticmethod
    def _mask_from_prefix(p):
        return (0xFFFFFFFF << (32 - p)) & 0xFFFFFFFF

    def _parse_mask(self, raw):
        raw = raw.strip()
        if raw.startswith("/") or (raw.isdigit() and 0 <= int(raw) <= 32):
            p = int(raw.lstrip("/"))
            return self._mask_from_prefix(p), p
        mask_int = self._ip_int(raw)
        inv = (~mask_int) & 0xFFFFFFFF
        if inv and (inv + 1) & inv:
            raise ValueError("非法掩码")
        return mask_int, bin(mask_int).count("1")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("网络计算器")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#1e293b;")
        layout.addWidget(title)

        layout.addWidget(QLabel("IP 地址"))
        self.ip_entry = QLineEdit("192.168.1.0")
        self.ip_entry.setStyleSheet("padding:6px; font-family:Consolas; font-size:13px;")
        self.ip_entry.returnPressed.connect(self._calc)
        layout.addWidget(self.ip_entry)

        layout.addSpacing(8)
        layout.addWidget(QLabel("子网掩码 / CIDR"))
        self.mask_entry = QLineEdit("255.255.255.0")
        self.mask_entry.setStyleSheet("padding:6px; font-family:Consolas; font-size:13px;")
        self.mask_entry.returnPressed.connect(self._calc)
        layout.addWidget(self.mask_entry)

        self.err_lbl = QLabel("")
        self.err_lbl.setStyleSheet("color:#ef4444; font-size:10px;")
        layout.addWidget(self.err_lbl)

        btns = QHBoxLayout()
        btn_calc = QPushButton("计算")
        btn_calc.setStyleSheet("background:#2563eb; color:#fff; padding:8px 20px; border-radius:4px; font-weight:bold;")
        btn_calc.clicked.connect(self._calc)
        self.btn_copy = QPushButton("一键复制结果")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self._copy)
        btns.addWidget(btn_calc)
        btns.addWidget(self.btn_copy)
        btns.addStretch()
        layout.addLayout(btns)

        layout.addSpacing(8)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#e2e8f0;")
        layout.addWidget(line)
        layout.addSpacing(8)

        self.result_labels = {}
        items = [
            ("网络地址", "network"), ("广播地址", "broadcast"), ("可用 IP 范围", "range"),
            ("子网掩码（点分）", "mask_dot"), ("子网掩码（CIDR）", "mask_cidr"),
            ("可用主机数量", "hosts"),
        ]
        for title_txt, key in items:
            row = QHBoxLayout()
            lb = QLabel(title_txt)
            lb.setStyleSheet("color:#64748b; font-size:12px; min-width:130px;")
            val = QLabel("—")
            val.setStyleSheet("color:#1e293b; font-size:15px; font-family:Consolas; font-weight:bold;")
            row.addWidget(lb)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)
            self.result_labels[key] = val

        self._result_text = ""

    def _calc(self):
        self.err_lbl.setText("")
        self.err_lbl.setStyleSheet("color:#ef4444; font-size:10px;")
        try:
            ip_int = self._ip_int(self.ip_entry.text())
            mask_int, prefix = self._parse_mask(self.mask_entry.text())
            net = ip_int & mask_int
            bcast = net | ((~mask_int) & 0xFFFFFFFF)
            if prefix <= 30:
                first, last, hosts = net + 1, bcast - 1, (1 << (32 - prefix)) - 2
            elif prefix == 31:
                first, last, hosts = net, bcast, 2
            else:
                first, last, hosts = net, net, 1
            r = {
                "network": self._int_ip(net), "broadcast": self._int_ip(bcast),
                "range": f"{self._int_ip(first)}  —  {self._int_ip(last)}",
                "mask_dot": self._int_ip(mask_int), "mask_cidr": f"/{prefix}",
                "hosts": f"{hosts:,}",
            }
            for k, v in r.items():
                if k in self.result_labels:
                    self.result_labels[k].setText(v)
            self._result_text = (
                f"网络地址:        {r['network']}\n广播地址:        {r['broadcast']}\n"
                f"可用 IP 范围:    {r['range']}\n子网掩码(点分):  {r['mask_dot']}\n"
                f"子网掩码(CIDR):  {r['mask_cidr']}\n可用主机数量:    {r['hosts']}\n"
            )
            self.btn_copy.setEnabled(True)
        except Exception as e:
            self.err_lbl.setText(f"⚠ {e}")
            for v in self.result_labels.values():
                v.setText("—")
            self.btn_copy.setEnabled(False)

    def _copy(self):
        if self._result_text:
            QApplication.clipboard().setText(self._result_text)
            self.err_lbl.setText("✓ 已复制到剪贴板")
            self.err_lbl.setStyleSheet("color:#10b981; font-size:10px;")


# ============================================================
# 局域网扫描
# ============================================================

class LANScannerDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("局域网扫描")
        self.resize(640, 720)
        self.setMinimumSize(500, 500)
        self._worker = None
        self._online = 0
        self._build_ui()
        self._detect_network()

    def _detect_network(self):
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except:
            local_ip = "127.0.0.1"
        p = local_ip.split(".")
        if len(p) == 4 and p[0] not in ("127", "169"):
            self.ip_entry.setText(f"{p[0]}.{p[1]}.{p[2]}.0")
            self.mask_entry.setText("255.255.255.0")
        else:
            self.ip_entry.setText(local_ip)
            self.mask_entry.setText("24")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        title = QLabel("局域网扫描")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#1e293b;")
        layout.addWidget(title)

        layout.addWidget(QLabel("网络地址 / CIDR"))
        r = QHBoxLayout()
        self.ip_entry = QLineEdit()
        self.ip_entry.setStyleSheet("font-family:Consolas; font-size:13px; padding:6px;")
        self.mask_entry = QLineEdit()
        self.mask_entry.setStyleSheet("font-family:Consolas; font-size:13px; padding:6px; max-width:70px;")
        r.addWidget(self.ip_entry)
        r.addWidget(QLabel(" / "))
        r.addWidget(self.mask_entry)
        self.btn_scan = QPushButton("开始扫描")
        self.btn_scan.setStyleSheet("background:#2563eb; color:#fff; padding:8px 16px; border-radius:4px; font-weight:bold;")
        self.btn_scan.clicked.connect(self._start)
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop)
        r.addWidget(self.btn_scan)
        r.addWidget(self.btn_stop)
        layout.addLayout(r)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color:#2563eb; font-size:10px;")
        layout.addWidget(self.status_lbl)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["IP 地址", "主机名"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        self.count_lbl = QLabel("就绪")
        self.count_lbl.setStyleSheet("color:#64748b; font-size:10px;")
        layout.addWidget(self.count_lbl)

        self.btn_export = QPushButton("📥 导出扫描结果到 CSV")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        layout.addWidget(self.btn_export)

    def _start(self):
        self.tree.clear()
        self._online = 0
        ip_raw = self.ip_entry.text().strip()
        mask_raw = self.mask_entry.text().strip()
        try:
            p = self._parse_prefix(mask_raw)
            base = [int(x) for x in ip_raw.split(".")]
            if len(base) != 4:
                raise ValueError
        except:
            QMessageBox.warning(self, "提示", "请输入有效的 IP 地址和掩码")
            return
        total = 1 << (32 - p)
        self.progress.setMaximum(total - 2)
        self.progress.setValue(0)
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_lbl.setText("正在扫描...")
        self._worker = ScanWorker(base, p)
        self._worker.progress.connect(self._on_progress)
        self._worker.found.connect(self._on_found)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _parse_prefix(self, raw):
        raw = raw.strip()
        if raw.startswith("/"):
            p = int(raw[1:])
        elif raw.isdigit():
            p = int(raw)
        else:
            pp = [int(x) for x in raw.split(".")]
            p = bin((pp[0]<<24)|(pp[1]<<16)|(pp[2]<<8)|pp[3]).count("1")
        if p < 16 or p > 30:
            raise ValueError
        return p

    def _stop(self):
        if self._worker:
            self._worker.stop()
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_lbl.setText("已停止")

    def _on_progress(self, scanned, total):
        self.progress.setValue(scanned)
        self.count_lbl.setText(f"已扫描 {scanned} / {total}  |  活跃 {self._online}")
        self.status_lbl.setText(f"正在扫描... ({scanned}/{total})")

    def _on_found(self, ip, hostname):
        self._online += 1
        item = QTreeWidgetItem([ip, hostname])
        item.setForeground(0, QColor("#10b981"))
        self.tree.addTopLevelItem(item)

    def _on_finished(self, scanned, online):
        self.progress.setValue(self.progress.maximum())
        self.count_lbl.setText(f"扫描完成  |  共 {scanned} 个 IP  |  活跃 {online}")
        self.status_lbl.setText("✓ 扫描完成")
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_export.setEnabled(online > 0)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出", "lan_scan.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["IP 地址", "主机名"])
                for i in range(self.tree.topLevelItemCount()):
                    item = self.tree.topLevelItem(i)
                    w.writerow([item.text(0), item.text(1)])
            QMessageBox.information(self, "成功", f"已导出 {self.tree.topLevelItemCount()} 条记录")
        except Exception as e:
            QMessageBox.critical(self, "失败", str(e))


# ============================================================
# 命令编辑对话框（长Ping / Tracert / TCPing）
# ============================================================

class CmdDialog(QDialog):
    def __init__(self, parent, title, cmd_parts):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(560, 150)
        self.result = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        layout.addWidget(QLabel("编辑命令（可直接修改参数）"))
        self.cmd_edit = QLineEdit(" ".join(cmd_parts))
        self.cmd_edit.setStyleSheet("font-family:Consolas; font-size:12px; padding:6px;")
        self.cmd_edit.selectAll()
        self.cmd_edit.returnPressed.connect(self._accept)
        layout.addWidget(self.cmd_edit)

        layout.addSpacing(8)
        btns = QHBoxLayout()
        btn_ok = QPushButton("执行")
        btn_ok.setStyleSheet("background:#2563eb; color:#fff; padding:8px 20px;")
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        btns.addStretch()
        layout.addLayout(btns)

    def _accept(self):
        self.result = self.cmd_edit.text()
        self.accept()


# ============================================================
# 快捷键自定义对话框
# ============================================================

class ShortcutCaptureDialog(QDialog):
    """弹出小窗，捕获用户按下的快捷键组合"""

    def __init__(self, parent, action_label):
        super().__init__(parent)
        self.setWindowTitle("按下快捷键")
        self.setFixedSize(380, 170)
        self._keys = ""
        self._mods = 0
        layout = QVBoxLayout(self)
        hint = QLabel(f"「{action_label}」\n请按下新的快捷键组合（如 Ctrl+N）\n按 Esc 取消")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size:11pt; color:#334155;")
        layout.addWidget(hint)
        self._key_lbl = QLabel("等待按键...")
        self._key_lbl.setAlignment(Qt.AlignCenter)
        self._key_lbl.setStyleSheet("font-weight:bold; font-size:14pt; color:#4a6fa5;")
        layout.addWidget(self._key_lbl)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        # Esc → 取消
        if key == Qt.Key_Escape:
            self.reject()
            return

        # 忽略纯修饰键
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
                    Qt.Key_AltGr, Qt.Key_Super_L, Qt.Key_Super_R):
            return

        # 构建快捷键字符串
        parts = []
        if mods & Qt.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.AltModifier:
            parts.append("Alt")
        if mods & Qt.MetaModifier:
            parts.append("Meta")

        # 解析按键名
        key_name = ""
        if key in (Qt.Key_F1,):  key_name = "F1"
        elif key == Qt.Key_F2:   key_name = "F2"
        elif key == Qt.Key_F3:   key_name = "F3"
        elif key == Qt.Key_F4:   key_name = "F4"
        elif key == Qt.Key_F5:   key_name = "F5"
        elif key == Qt.Key_F6:   key_name = "F6"
        elif key == Qt.Key_F7:   key_name = "F7"
        elif key == Qt.Key_F8:   key_name = "F8"
        elif key == Qt.Key_F9:   key_name = "F9"
        elif key == Qt.Key_F10:  key_name = "F10"
        elif key == Qt.Key_F11:  key_name = "F11"
        elif key == Qt.Key_F12:  key_name = "F12"
        elif key == Qt.Key_Escape: key_name = "Esc"
        elif Qt.Key_A <= key <= Qt.Key_Z:
            key_name = chr(key)
        elif Qt.Key_0 <= key <= Qt.Key_9:
            key_name = chr(key)
        elif key == Qt.Key_Space: key_name = "Space"
        elif key == Qt.Key_Tab:   key_name = "Tab"
        elif key == Qt.Key_Backspace: key_name = "Backspace"
        elif key == Qt.Key_Return: key_name = "Enter"
        elif key == Qt.Key_Delete: key_name = "Del"
        elif key == Qt.Key_Insert: key_name = "Ins"
        elif key == Qt.Key_Home:   key_name = "Home"
        elif key == Qt.Key_End:    key_name = "End"
        elif key == Qt.Key_PageUp: key_name = "PgUp"
        elif key == Qt.Key_PageDown: key_name = "PgDn"
        elif key == Qt.Key_Up:     key_name = "Up"
        elif key == Qt.Key_Down:   key_name = "Down"
        elif key == Qt.Key_Left:   key_name = "Left"
        elif key == Qt.Key_Right:  key_name = "Right"
        else:
            key_name = f"Key({key})"

        if not key_name:
            return

        if parts:
            self._keys = "+".join(parts) + "+" + key_name
        else:
            self._keys = key_name

        self._key_lbl.setText(self._keys)
        # 0.5 秒后关闭
        QTimer.singleShot(400, self.accept)

    @property
    def result_keys(self):
        return self._keys


class ShortcutDialog(QDialog):
    """快捷键自定义主对话框"""

    def __init__(self, parent, cfg, refresh_callback):
        super().__init__(parent)
        self.setWindowTitle("快捷键自定义")
        self.resize(620, 620)
        self.setMinimumSize(480, 400)
        self.cfg = cfg
        self._refresh = refresh_callback
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        hint = QLabel("双击某行或点击「修改」按钮来更改快捷键。空白则恢复默认。")
        hint.setStyleSheet("color:#8899aa; font-size:9pt;")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["功能", "当前快捷键", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 70)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        btn_reset = QPushButton("恢复全部默认")
        btn_reset.setStyleSheet("color:#b8585b; padding:6px 14px;")
        btn_reset.clicked.connect(self._reset_all)
        btns.addWidget(btn_reset)
        btns.addStretch()
        btn_close = QPushButton("完成")
        btn_close.setStyleSheet("background:#4a6fa5; color:#fff; padding:6px 20px; border-radius:4px;")
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _load_data(self):
        custom = self.cfg.get_shortcuts()
        self.table.setRowCount(0)
        self._row_map = {}
        for aid, (label, default_keys, _menu_display) in DEFAULT_SHORTCUTS.items():
            current = custom.get(aid, default_keys)
            row = self.table.rowCount()
            self.table.insertRow(row)

            label_item = QTableWidgetItem(label)
            label_item.setData(Qt.UserRole, aid)
            self.table.setItem(row, 0, label_item)

            key_item = QTableWidgetItem(current if current else "(无)")
            self.table.setItem(row, 1, key_item)

            btn = QPushButton("修改")
            btn.setStyleSheet("padding:3px 12px; font-size:9pt;")
            btn.clicked.connect(lambda checked, r=row: self._capture_row(r))
            self.table.setCellWidget(row, 2, btn)

        self.table.resizeRowsToContents()

    def _on_double_click(self, row, col):
        self._capture_row(row)

    def _capture_row(self, row):
        aid = self.table.item(row, 0).data(Qt.UserRole)
        label = DEFAULT_SHORTCUTS[aid][0]
        dlg = ShortcutCaptureDialog(self, label)
        if dlg.exec_() == QDialog.Accepted and dlg.result_keys:
            self._set_row(row, dlg.result_keys)
        elif dlg.result_keys == "":
            # 取消修改
            pass

    def _set_row(self, row, keys):
        aid = self.table.item(row, 0).data(Qt.UserRole)
        default_keys = DEFAULT_SHORTCUTS[aid][1]
        if keys == default_keys:
            self.cfg.set_shortcut(aid, "")
            self.table.item(row, 1).setText(default_keys)
        else:
            self.cfg.set_shortcut(aid, keys)
            self.table.item(row, 1).setText(keys)

    def _reset_all(self):
        reply = QMessageBox.question(self, "确认", "恢复全部快捷键为默认值？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cfg.reset_shortcuts()
            self._load_data()
            if self._refresh:
                self._refresh()


# ============================================================
# 主窗口
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = ConfigManager()
        # DPI 自适应窗口尺寸
        dpr = self.devicePixelRatio()
        base_w, base_h = 1060, 800
        min_w, min_h = 890, 620
        self.setWindowTitle(f"Network Tools {APP_VERSION}")
        self.resize(int(base_w * (dpr / 1.5) if dpr > 1.5 else base_w),
                    int(base_h * (dpr / 1.5) if dpr > 1.5 else base_h))
        self.setMinimumSize(int(min_w * (dpr / 1.5) if dpr > 1.5 else min_w),
                            int(min_h * (dpr / 1.5) if dpr > 1.5 else min_h))

        self._set_icon()
        self._setup_tray()
        self._apply_style()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()

        self._worker = None
        self._passed = self._failed = 0
        self._fetch_local_info()
        self._show_welcome()

    def _set_icon(self):
        for name in ["app_icon.ico", "tray_icon.png"]:
            ico = get_resource_path(name)
            if not os.path.exists(ico):
                ico = os.path.join(get_app_dir(), name)
            if os.path.exists(ico):
                self.setWindowIcon(QIcon(ico))
                break

    def _setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            ico_path = get_resource_path("tray_icon.png")
            if not os.path.exists(ico_path):
                ico_path = os.path.join(get_app_dir(), "tray_icon.png")
            if os.path.exists(ico_path):
                icon = QIcon(ico_path)
            else:
                icon = QApplication.style().standardIcon(QStyle.SP_ComputerIcon)
            self.tray = QSystemTrayIcon(icon)
            self.tray.setToolTip(f"Network Tools {APP_VERSION}")
            menu = QMenu()
            show_action = menu.addAction("显示窗口")
            show_action.triggered.connect(self._show_from_tray)
            menu.addSeparator()
            quit_action = menu.addAction("退出程序")
            quit_action.triggered.connect(self._real_quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()
        else:
            self.tray = None

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _real_quit(self):
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            if QMessageBox.question(self, "确认退出", "测试正在运行中，确定要退出吗？") != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.stop()
        if self.tray:
            self.tray.hide()
        event.accept()

    def _apply_style(self):
        # 淡雅配色 + 全局字体设置
        app_font = QFont("Microsoft YaHei UI", 10)
        app_font.setStyleStrategy(QFont.PreferAntialias)
        QApplication.setFont(app_font)

        self.setStyleSheet("""
            /* 淡雅主题 — 浅色调、低饱和、宽留白 */
            QMainWindow, QDialog { background:#fafbfc; }
            QWidget { color:#2c3e50; }

            /* 菜单栏 — 沉静深灰 */
            QMenuBar { background:#2c3e50; color:#e8eef3; font-size:10pt; padding:3px; }
            QMenuBar::item:selected { background:#3d5468; }
            QMenu { background:#ffffff; border:1px solid #e8eef3; border-radius:4px; }
            QMenu::item { padding:6px 24px; color:#2c3e50; }
            QMenu::item:selected { background:#eef3f8; color:#1a1a2e; }
            QMenu::separator { height:1px; background:#e8eef3; margin:4px 8px; }

            /* 按钮 — 扁平、柔和 */
            QPushButton {
                background:#ffffff; color:#2c3e50;
                border:1px solid #d6dde4; border-radius:6px;
                padding:7px 16px; font-size:10pt;
            }
            QPushButton:hover { background:#f5f7fa; border-color:#b8c2cc; }
            QPushButton:pressed { background:#e8eef3; }
            QPushButton:disabled { background:#fafbfc; color:#aab2bd; border-color:#e8eef3; }

            /* 输入框 */
            QLineEdit {
                border:1px solid #d6dde4; border-radius:6px;
                padding:6px 8px; background:#ffffff; color:#2c3e50;
                selection-background-color:#c5d4e3; selection-color:#1a1a2e;
            }
            QLineEdit:focus { border-color:#6b8caf; background:#ffffff; }

            /* 文本域 */
            QTextEdit {
                border:1px solid #e8eef3; border-radius:6px;
                background:#ffffff; color:#2c3e50;
                font-family:Consolas, "Microsoft YaHei UI"; font-size:10pt;
                padding:6px;
            }

            /* 列表/树/表格 */
            QTreeWidget, QTableWidget, QTreeView, QTableView {
                border:1px solid #e8eef3; border-radius:6px;
                background:#ffffff; gridline-color:#f0f3f6;
                selection-background-color:#eef3f8; selection-color:#1a1a2e;
            }
            QTreeWidget::item, QTableWidget::item { padding:4px; }
            QTreeWidget::item:selected, QTableWidget::item:selected { background:#eef3f8; }
            QHeaderView::section {
                background:#f5f7fa; padding:8px; border:none;
                border-bottom:1px solid #e8eef3; color:#5a6877;
                font-weight:600; font-size:10pt;
            }

            /* 进度条 */
            QProgressBar {
                border:none; border-radius:5px; text-align:center;
                background:#eef3f8; height:8px; color:#5a6877; font-size:9pt;
            }
            QProgressBar::chunk {
                background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #6b8caf, stop:1 #8fa8c4);
                border-radius:5px;
            }

            /* 选项卡 */
            QTabWidget::pane {
                border:1px solid #e8eef3; border-radius:6px;
                background:#ffffff; margin-top:-1px;
            }
            QTabBar::tab {
                background:#f5f7fa; color:#5a6877;
                padding:8px 18px; border:1px solid #e8eef3;
                border-bottom:none; border-top-left-radius:6px;
                border-top-right-radius:6px; margin-right:1px;
            }
            QTabBar::tab:hover { background:#eef3f8; }
            QTabBar::tab:selected {
                background:#ffffff; color:#2c3e50; font-weight:600;
                border-bottom:1px solid #ffffff;
            }

            /* 分组框 */
            QGroupBox {
                font-weight:600; color:#3d5468;
                border:1px solid #e8eef3; border-radius:8px;
                margin-top:14px; padding:18px 12px 12px 12px;
                background:#ffffff;
            }
            QGroupBox::title {
                subcontrol-origin:margin; left:14px; padding:0 6px;
                background:#fafbfc; color:#5a6877;
            }

            /* 分割器 */
            QSplitter::handle { background:#e8eef3; width:1px; }
            QSplitter::handle:hover { background:#b8c2cc; }

            /* 滚动条 */
            QScrollBar:vertical {
                background:transparent; width:10px; margin:0;
            }
            QScrollBar::handle:vertical {
                background:#d6dde4; border-radius:5px; min-height:30px;
            }
            QScrollBar::handle:vertical:hover { background:#b8c2cc; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
            QScrollBar:horizontal {
                background:transparent; height:10px; margin:0;
            }
            QScrollBar::handle:horizontal {
                background:#d6dde4; border-radius:5px; min-width:30px;
            }
            QScrollBar::handle:horizontal:hover { background:#b8c2cc; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }

            /* 状态栏/消息框 */
            QStatusBar { background:#f5f7fa; color:#5a6877; }
        """)

    def _menu_label(self, action_id):
        """根据快捷键注册表生成菜单显示文字"""
        label, default_keys, menu_display = DEFAULT_SHORTCUTS[action_id]
        # 用用户自定义或默认的快捷键
        custom = self.cfg.get_shortcuts()
        actual_keys = custom.get(action_id, default_keys)
        if menu_display is None:
            return label  # 不显示快捷键
        return f"{label}    {actual_keys}"

    def _build_menu(self):
        bar = self.menuBar()

        # 文件
        file_menu = bar.addMenu("文件")
        file_menu.addAction("上传 Logo", self._upload_logo)
        file_menu.addAction("去除 Logo", self._remove_logo)
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)

        # 内网测试
        lan_menu = bar.addMenu("内网测试")
        lan_menu.addAction(self._menu_label("test_gateway"), self._test_gateway)
        lan_menu.addAction(self._menu_label("test_server"), self._test_server)
        lan_menu.addSeparator()
        lan_menu.addAction(self._menu_label("test_lan_only"), self._test_lan_only)

        # 外网测试
        wan_menu = bar.addMenu("外网测试")
        wan_menu.addAction(self._menu_label("test_wan"), self._test_wan)

        # 更多测试
        more_menu = bar.addMenu("更多测试")
        more_menu.addAction(self._menu_label("long_ping"), self._long_ping)
        more_menu.addAction(self._menu_label("tracert"), self._tracert)
        more_menu.addAction(self._menu_label("tcping"), self._tcping)

        # 操作控制
        ctrl_menu = bar.addMenu("操作控制")
        ctrl_menu.addAction(self._menu_label("test_all"), self._test_all)
        ctrl_menu.addAction(self._menu_label("stop_all"), self._stop_all)
        ctrl_menu.addSeparator()
        ctrl_menu.addAction(self._menu_label("save_log"), self._save_log)
        ctrl_menu.addAction(self._menu_label("clear_log"), self._clear_log)

        # IP地址管理 — 直接打开（不显示快捷键）
        bar.addAction(self._menu_label("open_ip_manager"), self._open_ip_manager)

        # 顶级
        bar.addAction(self._menu_label("calculator"), lambda: CalculatorDialog(self).exec_())
        bar.addAction(self._menu_label("lan_scanner"), lambda: LANScannerDialog(self).exec_())

        # 帮助
        help_menu = bar.addMenu("帮助")
        help_menu.addAction(self._menu_label("show_about"), self._show_about)
        help_menu.addAction("快捷键...", self._open_shortcut_dialog)

    def _bind_shortcuts(self):
        """根据注册表 + 用户自定义绑定全局快捷键"""
        # action_id → callback 映射
        cb = {
            "test_gateway": self._test_gateway, "test_server": self._test_server,
            "test_wan": self._test_wan, "test_lan_only": self._test_lan_only,
            "long_ping": self._long_ping, "tracert": self._tracert, "tcping": self._tcping,
            "open_ip_manager": self._open_ip_manager,
            "calculator": lambda: CalculatorDialog(self).exec_(),
            "lan_scanner": lambda: LANScannerDialog(self).exec_(),
            "save_log": self._save_log, "clear_log": self._clear_log,
            "test_all": self._test_all, "stop_all": self._stop_all,
            "show_about": self._show_about,
        }

        custom = self.cfg.get_shortcuts()
        self._shortcut_objects = {}  # 保存以供后续更新

        for aid, (label, default_keys, _menu_display) in DEFAULT_SHORTCUTS.items():
            keys = custom.get(aid, default_keys)
            if keys and aid in cb:
                try:
                    qsc = QShortcut(QKeySequence(keys), self, cb[aid])
                    self._shortcut_objects[aid] = qsc
                except Exception:
                    # 无效快捷键，忽略
                    pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(14, 10, 14, 8)

        # 标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet("background:#ffffff; border-bottom:1px solid #e8eef3;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(20, 0, 20, 0)
        self.logo_lbl = QLabel()
        self.logo_lbl.setMinimumHeight(36)
        self.logo_lbl.setMaximumHeight(56)
        self.logo_lbl.setMinimumWidth(80)
        self.logo_lbl.setMaximumWidth(220)
        self.logo_lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.logo_lbl.setStyleSheet("border-radius:8px; background:transparent;")
        self.logo_lbl.setAlignment(Qt.AlignCenter)
        self._load_logo()
        tl.addWidget(self.logo_lbl)
        tl.addSpacing(14)
        title_lbl = QLabel(f"Network Tools {APP_VERSION}")
        title_lbl.setStyleSheet("font-size:14pt; font-weight:600; color:#2c3e50;")
        tl.addWidget(title_lbl)
        tl.addSpacing(8)
        sub_lbl = QLabel("· IP管理 · 内外网测试 · 本机信息 · 更多工具")
        sub_lbl.setStyleSheet("color:#aab2bd; font-size:9pt;")
        tl.addWidget(sub_lbl)
        tl.addStretch()
        ver = QLabel(ABOUT_INFO['version'])
        ver.setStyleSheet("color:#aab2bd; font-size:9pt;")
        tl.addWidget(ver)
        main_layout.addWidget(title_bar)

        # 主内容
        splitter = QSplitter(Qt.Horizontal)

        # ===== 左面板 =====
        left = QWidget()
        left.setFixedWidth(270)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 4, 8, 0)

        # 本机信息
        info_group = QGroupBox("本机信息")
        il = QVBoxLayout(info_group)
        self.info_labels = {}
        for key, title in [("hostname", "计算机名"), ("local_ip", "本机IP地址"), ("wan_ip", "公网出口IP地址")]:
            row = QHBoxLayout()
            lt = QLabel(title)
            lt.setStyleSheet("color:#64748b; font-size:12px; min-width:75px;")
            lv = QLabel("获取中...")
            lv.setStyleSheet("color:#1e293b; font-size:13px; font-family:Consolas; font-weight:bold;")
            lv.setWordWrap(True)
            row.addWidget(lt)
            row.addWidget(lv)
            row.addStretch()
            il.addLayout(row)
            self.info_labels[key] = lv
        # 复制按钮
        btn_copy = QPushButton("复制本机信息")
        btn_copy.setStyleSheet(
            "padding:6px 10px; font-size:12px; color:#4a6fa5; background:#eef3f8; "
            "border:1px solid #d0dce8; border-radius:4px; font-weight:bold;")
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_local_info)
        il.addWidget(btn_copy)
        ll.addWidget(info_group)
        ll.addSpacing(6)

        # 网络测试
        test_group = QGroupBox("网络测试")
        tg = QVBoxLayout(test_group)
        self._test_btns = {}
        self._target_counts = {}
        for label, callback, style, kkey in [
            ("🔗 内网网关测试", self._test_gateway,
             "background:#f5f9fc; color:#4a6fa5; font-weight:600; padding:10px; border-radius:6px; text-align:left; border:1px solid #dde7f0;",
             "gateway_targets"),
            ("🖥 内网关键服务器", self._test_server,
             "background:#f6faf6; color:#5a8a5a; font-weight:600; padding:10px; border-radius:6px; text-align:left; border:1px solid #dfe8df;",
             "server_targets"),
            ("🌍 外网网络测试", self._test_wan,
             "background:#fcfaf5; color:#a08840; font-weight:600; padding:10px; border-radius:6px; text-align:left; border:1px solid #ece4cf;",
             "wan_targets"),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(style)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            tg.addWidget(btn)
            count_lbl = QLabel()
            count_lbl.setStyleSheet("color:#aab2bd; font-size:9pt; margin:2px 0 6px 4px;")
            tg.addWidget(count_lbl)
            self._target_counts[kkey] = count_lbl
        self._update_target_counts()
        ll.addWidget(test_group)
        ll.addSpacing(6)

        # 操作控制
        ctrl_group = QGroupBox("操作控制")
        cl = QVBoxLayout(ctrl_group)
        self.btn_all = QPushButton("▶ 运行全部")
        self.btn_all.setStyleSheet("background:#4a6fa5; color:#ffffff; font-weight:600; padding:10px; border-radius:6px; border:none;")
        self.btn_all.setCursor(Qt.PointingHandCursor)
        self.btn_all.clicked.connect(self._test_all)
        self.btn_stop = QPushButton("■ 停止测试")
        self.btn_stop.setStyleSheet("background:#ffffff; color:#b8585b; font-weight:600; padding:10px; border-radius:6px; border:1px solid #e8c8c9;")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop_all)
        self.btn_save = QPushButton("💾 保存日志")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_log)
        self.btn_clear = QPushButton("🗑 清空")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_log)
        cl.addWidget(self.btn_all)
        cl.addWidget(self.btn_stop)
        cl.addWidget(self.btn_save)
        cl.addWidget(self.btn_clear)
        ll.addWidget(ctrl_group)
        ll.addStretch()

        splitter.addWidget(left)

        # ===== 右面板 =====
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 4, 0, 0)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setFormat("● 就绪")
        self.progress_label = QLabel("就绪")
        self.progress_label.setStyleSheet("color:#aab2bd; font-size:9pt;")
        rl.addWidget(self.progress_bar)
        rl.addWidget(self.progress_label)

        # 统计
        stats_row = QHBoxLayout()
        self.stats_pass = QLabel("● 通: 0")
        self.stats_pass.setStyleSheet("color:#5a8a5a; font-size:10pt; font-weight:600;")
        self.stats_fail = QLabel("● 不通: 0")
        self.stats_fail.setStyleSheet("color:#b8585b; font-size:10pt; font-weight:600;")
        self.stats_total = QLabel("全部: 0 个目标")
        self.stats_total.setStyleSheet("color:#aab2bd; font-size:9pt;")
        stats_row.addWidget(self.stats_pass)
        stats_row.addSpacing(14)
        stats_row.addWidget(self.stats_fail)
        stats_row.addSpacing(14)
        stats_row.addWidget(self.stats_total)
        stats_row.addStretch()
        rl.addLayout(stats_row)

        # 日志区
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        rl.addWidget(self.log_area)

        # 状态栏
        self.status_lbl = QLabel("● 就绪 | 请选择测试项目开始")
        self.status_lbl.setStyleSheet("color:#aab2bd; font-size:9pt; padding:4px;")
        rl.addWidget(self.status_lbl)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

    def _load_logo(self):
        """加载 logo，按容器宽度自适应缩放，保持原始宽高比"""
        # 如果用户主动移除了 logo，跳过回退加载
        if self.cfg.config.get("logo_removed"):
            self.logo_lbl.setText("NT")
            self.logo_lbl.setStyleSheet(
                "border-radius:8px; background:#e8eef3; color:#7a8b9a; "
                "font-size:14px; font-weight:bold; font-family:Microsoft YaHei UI;")
            self.logo_lbl.setFixedSize(40, 40)
            return

        target_h = int(40 * self.devicePixelRatio())
        max_w = int(200 * self.devicePixelRatio())

        logo_path = self.cfg.get_logo_path()
        candidates = [logo_path] if logo_path else []
        for name in ["logo.png", "logo.jpg", "logo.jpeg"]:
            candidates.append(os.path.join(get_app_dir(), name))

        for path in candidates:
            if path and os.path.exists(path) and HAS_PIL:
                try:
                    img = Image.open(path)
                    # 按目标高度等比缩放（保持原始比例，不形变）
                    w, h = img.size
                    if h > 0:
                        new_w = min(int(w * target_h / h), max_w)
                        new_h = int(new_w * h / w) if w > 0 else target_h
                    else:
                        new_w, new_h = target_h, target_h
                    new_w = max(1, new_w)
                    new_h = max(1, new_h)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

                    # 缩略图缓存放到 AppData，不污染 exe 目录
                    cache_dir = os.path.join(
                        os.environ.get("APPDATA", os.path.expanduser("~")), "NetworkTools")
                    os.makedirs(cache_dir, exist_ok=True)
                    tmp = os.path.join(cache_dir, "_logo_resized.png")
                    img.save(tmp, "PNG")
                    pix = QPixmap(tmp)
                    # 让 QLabel 自动根据 pixmap 尺寸调整
                    self.logo_lbl.setPixmap(pix)
                    self.logo_lbl.setFixedSize(int(new_w / self.devicePixelRatio()),
                                                int(new_h / self.devicePixelRatio()))
                    return
                except Exception:
                    continue

        # 没有 logo 时显示默认
        self.logo_lbl.setText("NT")
        self.logo_lbl.setStyleSheet(
            "border-radius:8px; background:#e8eef3; color:#7a8b9a; "
            "font-size:14px; font-weight:bold; font-family:Microsoft YaHei UI;"
        )
        self.logo_lbl.setFixedSize(40, 40)

    def _upload_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 Logo", "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            try:
                ext = os.path.splitext(path)[1] or ".png"
                # Logo 文件和缩略图都存到 AppData，不污染 exe 目录
                cache_dir = os.path.join(
                    os.environ.get("APPDATA", os.path.expanduser("~")), "NetworkTools")
                os.makedirs(cache_dir, exist_ok=True)
                target = os.path.join(cache_dir, f"logo{ext}")
                shutil.copy2(path, target)
                self.cfg.set_logo_path(target)
                self.cfg.config["logo_removed"] = False
                self.cfg.save()
                self._load_logo()
                QMessageBox.information(self, "成功", "Logo 已更新")
            except Exception as e:
                QMessageBox.critical(self, "失败", str(e))

    def _remove_logo(self):
        """清除已上传的 logo，恢复默认显示"""
        old = self.cfg.get_logo_path()
        if old and os.path.exists(old):
            try:
                os.remove(old)
            except Exception:
                pass
        self.cfg.set_logo_path("")
        self.cfg.config["logo_removed"] = True
        self.cfg.save()
        self._load_logo()
        QMessageBox.information(self, "已清除", "Logo 已恢复默认")

    def _update_target_counts(self):
        for key, lbl in self._target_counts.items():
            cnt = len(self.cfg.get_targets(key))
            lbl.setText(f"    已配置 {cnt} 个目标")

    def _log(self, text, tag="info"):
        fmt = QTextCharFormat()
        colors = {
            "pass": QColor("#5a8a5a"), "fail": QColor("#b8585b"),
            "warn": QColor("#c08a40"), "info": QColor("#5a6877"),
            "header": QColor("#4a6fa5"), "summary": QColor("#2c3e50"),
        }
        c = colors.get(tag, QColor("#5a6877"))
        fmt.setForeground(c)
        if tag in ("fail", "warn", "header", "summary"):
            fmt.setFontWeight(75)
        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text, fmt)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _show_welcome(self):
        self._log("=" * 60 + "\n", "header")
        self._log(f"  Network Tools {APP_VERSION}\n", "summary")
        self._log("  PyQt5 桌面版 | 快捷键支持 | 系统托盘 | 彩色日志\n", "info")
        self._log("=" * 60 + "\n\n", "header")
        self._log("  请从左侧面板或菜单栏选择测试项目\n\n", "info")

    def _fetch_local_info(self):
        """使用 InfoFetchWorker(QThread) 获取本机信息，避免 raw thread + QTimer 不可靠"""
        self._info_worker = InfoFetchWorker()
        self._info_worker.result_ready.connect(self._update_info)
        self._info_worker.start()
        # 兜底：8 秒后如果还是 "获取中..." 则标为 "无法获取"
        QTimer.singleShot(8000, self._check_info_timeout)

    def _check_info_timeout(self):
        for key in ["hostname", "local_ip", "wan_ip"]:
            if self.info_labels.get(key) and self.info_labels[key].text() == "获取中...":
                self.info_labels[key].setText("无法获取")

    def _update_info(self, hn, lip, wan):
        if self.info_labels.get("hostname"):
            self.info_labels["hostname"].setText(hn)
        if self.info_labels.get("local_ip"):
            self.info_labels["local_ip"].setText(lip)
        if self.info_labels.get("wan_ip"):
            self.info_labels["wan_ip"].setText(wan)

    def _copy_local_info(self):
        """复制本机信息到剪贴板"""
        lines = []
        for key, title in [("hostname", "计算机名"), ("local_ip", "本机IP地址"), ("wan_ip", "公网出口IP地址")]:
            val = self.info_labels.get(key, QLabel()).text()
            lines.append(f"{title}: {val}")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "已复制", "本机信息已复制到剪贴板")

    # ---- 测试 ----

    def _run_tests(self, key, title):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "提示", "当前有测试正在运行")
            return
        targets = self.cfg.get_targets(key)
        if not targets:
            QMessageBox.warning(self, "提示", f"{title}列表为空，请先在 IP 地址管理中添加")
            return
        self._start_testing(targets, title)

    def _test_gateway(self):
        self._run_tests("gateway_targets", "内网网关测试")

    def _test_server(self):
        self._run_tests("server_targets", "内网关键服务器测试")

    def _test_wan(self):
        self._run_tests("wan_targets", "外网网络测试")

    def _test_lan_only(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "提示", "当前有测试正在运行")
            return
        all_t = [(ip, name) for ip, name in self.cfg.get_targets("gateway_targets")]
        all_t += [(ip, name) for ip, name in self.cfg.get_targets("server_targets")]
        if not all_t:
            QMessageBox.warning(self, "提示", "内网测试列表为空")
            return
        self._start_testing(all_t, "全部内网测试")

    def _test_all(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "提示", "当前有测试正在运行")
            return
        all_t = []
        for k in ["gateway_targets", "server_targets", "wan_targets"]:
            for ip, name in self.cfg.get_targets(k):
                all_t.append((ip, name))
        if not all_t:
            QMessageBox.warning(self, "提示", "测试列表为空")
            return
        self._start_testing(all_t, "全部测试")

    def _start_testing(self, targets, title):
        self._log(f"\n{'='*40}\n  {title}\n{'='*40}\n", "header")
        self._passed = self._failed = 0
        self.progress_bar.setMaximum(len(targets))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"{title} ...")
        self.progress_label.setText(f"0 / {len(targets)}")
        self._update_stats(0, 0)
        self._worker = TestWorker(targets)
        self._worker.log.connect(self._log)
        self._worker.progress.connect(lambda v: (
            self.progress_bar.setValue(v),
            self.progress_label.setText(f"{v} / {len(targets)}")
        ))
        self._worker.stats.connect(self._update_stats)
        self._worker.finished.connect(self._on_test_done)
        self._worker.start()

    def _update_stats(self, passed, failed):
        self._passed = passed
        self._failed = failed
        self.stats_pass.setText(f"● 通: {passed}")
        self.stats_fail.setText(f"● 不通: {failed}")
        self.stats_total.setText(f"全部: {passed + failed} 个目标")

    def _on_test_done(self):
        self.progress_bar.setFormat("● 就绪")
        self.progress_label.setText("完成")
        self._log(f"\n  完成 — {self._passed} 通 / {self._failed} 不通\n\n", "summary")

    def _stop_all(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._log("\n[用户停止]\n\n", "warn")
            self.progress_bar.setFormat("● 就绪")
            self.progress_label.setText("已停止")

    # ---- 日志 ----

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存日志", f"network_log_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt", "文本 (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_area.toPlainText())
            QMessageBox.information(self, "成功", f"日志已保存:\n{path}")

    def _clear_log(self):
        self.log_area.clear()
        self.stats_pass.setText("● 通: 0")
        self.stats_fail.setText("● 不通: 0")
        self.stats_total.setText("全部: 0 个目标")
        self._show_welcome()

    # ---- 工具 ----

    def _open_ip_manager(self):
        dlg = IPManagerDialog(self, self.cfg)
        dlg.exec_()
        self._update_target_counts()

    def _open_shortcut_dialog(self):
        dlg = ShortcutDialog(self, self.cfg, self._refresh_shortcuts)
        dlg.exec_()

    def _refresh_shortcuts(self):
        """快捷键变更后重建菜单和快捷键绑定"""
        # 移除旧快捷键
        if hasattr(self, '_shortcut_objects'):
            for qsc in self._shortcut_objects.values():
                qsc.setEnabled(False)
                qsc.deleteLater()
        # 重建菜单
        self.menuBar().clear()
        self._build_menu()
        # 重新绑定
        self._bind_shortcuts()

    def _long_ping(self):
        target, ok = QInputDialog.getText(self, "长Ping", "输入目标 IP 或域名:")
        if ok and target:
            dlg = CmdDialog(self, "长Ping", ["ping", "-t", target])
            if dlg.exec_() == QDialog.Accepted and dlg.result:
                parts = dlg.result.split()
                self._run_cmd(parts)

    def _tracert(self):
        target, ok = QInputDialog.getText(self, "路由追踪", "输入目标 IP 或域名:")
        if ok and target:
            dlg = CmdDialog(self, "路由追踪", ["tracert", target])
            if dlg.exec_() == QDialog.Accepted and dlg.result:
                parts = dlg.result.split()
                self._run_cmd(parts)

    def _tcping(self):
        target, ok = QInputDialog.getText(self, "TCPing", "输入 IP:端口 (如 192.168.1.1:80):")
        if ok and target:
            tcping_exe = get_resource_path("tcping.exe")
            if not os.path.exists(tcping_exe):
                tcping_exe = os.path.join(get_app_dir(), "tcping.exe")
            if not os.path.exists(tcping_exe):
                QMessageBox.warning(self, "提示", "tcping.exe 未找到")
                return
            parts = target.rsplit(":", 1) if ":" in target else [target, "80"]
            dlg = CmdDialog(self, "TCPing", [tcping_exe, "-t", parts[0], parts[1]])
            if dlg.exec_() == QDialog.Accepted and dlg.result:
                self._run_cmd(dlg.result.split())

    def _run_cmd(self, cmd):
        try:
            subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
        except:
            subprocess.Popen(cmd)

    # ---- 关于 ----

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("关于")
        dlg.setFixedSize(520, 720)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 22, 24, 12)

        title = QLabel("致每一位使用者")
        title.setStyleSheet("font-size:17px; font-weight:bold; color:#1e293b;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(8)

        letter = QTextEdit()
        letter.setReadOnly(True)
        letter.setPlainText(
            "这个包是我穿越依赖与报错为您免费预制好的工具——技术是分享，而非围栏。\n\n"
            "编译耗电，维护占时——那些夜晚和周末，本该属于生活。\n\n"
            "若它帮到您，您的赞助不是买软件，而是为下一版本充能，赎回我的时间。\n\n"
            "金额随喜。每一笔到账，都是咖啡或新功能的种子。\n\n"
            "免费，随缘，感恩驻足。"
        )
        letter.setStyleSheet("font-size:11px; color:#334155; background:#ffffff; border:1px solid #e2e8f0; border-radius:6px; padding:12px;")
        letter.setFixedHeight(130)
        layout.addWidget(letter)

        layout.addSpacing(8)
        support = QLabel("如果您愿意支持：")
        support.setStyleSheet("color:#64748b; font-size:10px;")
        support.setAlignment(Qt.AlignCenter)
        layout.addWidget(support)

        qr_path = get_resource_path("qrcode.jpg")
        if not os.path.exists(qr_path):
            qr_path = os.path.join(get_app_dir(), "qrcode.jpg")
        if os.path.exists(qr_path):
            pix = QPixmap(qr_path).scaled(260, 260, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr_lbl = QLabel()
            qr_lbl.setPixmap(pix)
            qr_lbl.setAlignment(Qt.AlignCenter)
            qr_lbl.setStyleSheet("border:1px solid #e2e8f0;")
            layout.addWidget(qr_lbl, alignment=Qt.AlignCenter)

        wx = QLabel("微信支付收款码")
        wx.setStyleSheet("color:#10b981; font-size:11px; font-weight:bold;")
        wx.setAlignment(Qt.AlignCenter)
        layout.addWidget(wx)

        layout.addSpacing(10)
        footer = QLabel(f"Network Tools {ABOUT_INFO['version']}  ·  © 2026")
        footer.setStyleSheet("color:#94a3b8; font-size:9px;")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        dlg.exec_()


# ============================================================
# 入口
# ============================================================

def main():
    # 高 DPI 适配：所有控件、字体、图标自动随屏幕缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setApplicationName("NetworkTools")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
