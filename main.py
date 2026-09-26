#!/usr/bin/env python3

import sys
import os
import subprocess
import shlex
import time
from collections import deque

import psutil

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QCheckBox, QGroupBox, QStatusBar, QMenuBar, QMenu,
    QInputDialog, QMessageBox, QHeaderView, QAbstractItemView, QFrame,
    QTableWidgetSelectionRange, QSystemTrayIcon
)
from PyQt6.QtGui import QAction, QActionGroup, QPainter, QPen, QColor, QFont, QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF

APP_STYLESHEET = """
QMainWindow {
    background-color: #F0F0F0;
}
QWidget {
    background-color: #F0F0F0;
    font-family: "Noto Sans", "DejaVu Sans", "Segoe UI", sans-serif;
    font-size: 12px;
    color: #000000;
}
QMenuBar {
    background-color: #F0F0F0;
    border-bottom: 1px solid #C0C0C0;
}
QMenuBar::item {
    background-color: transparent;
    padding: 4px 10px;
}
QMenuBar::item:selected {
    background-color: #C4E0FA;
    border: 1px solid #7DA2CE;
}
QMenu {
    background-color: #FFFFFF;
    border: 1px solid #A0A0A0;
}
QMenu::item {
    padding: 4px 24px 4px 24px;
}
QMenu::item:selected {
    background-color: #C4E0FA;
    color: #000000;
}
QTabWidget::pane {
    border: 1px solid #A0A0A0;
    background-color: #F0F0F0;
    top: -1px;
}
QTabBar::tab {
    background-color: #E4E4E4;
    border: 1px solid #A0A0A0;
    border-bottom: none;
    padding: 5px 14px;
    margin-right: -1px;
}
QTabBar::tab:selected {
    background-color: #F0F0F0;
    font-weight: bold;
}
QTabBar::tab:!selected {
    margin-top: 2px;
}
QHeaderView::section {
    background-color: #F0F0F0;
    border: 1px solid #C0C0C0;
    padding: 3px;
    font-weight: normal;
}
QTableWidget, QTreeWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F5F9FC;
    gridline-color: #E0E0E0;
    border: 1px solid #A0A0A0;
}
QTableWidget::item:selected, QTreeWidget::item:selected {
    background-color: #3399FF;
    color: #FFFFFF;
}
QPushButton {
    background-color: #F0F0F0;
    border: 1px solid #A0A0A0;
    border-radius: 3px;
    padding: 5px 14px;
}
QPushButton:hover {
    background-color: #E5F1FB;
    border: 1px solid #7DA2CE;
}
QPushButton:pressed {
    background-color: #CCE4F7;
}
QStatusBar {
    background-color: #F0F0F0;
    border-top: 1px solid #C0C0C0;
}
QGroupBox {
    border: 1px solid #ACACAC;
    margin-top: 9px;
    padding-top: 4px;
    background-color: #F0F0F0;
    font-weight: normal;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 9px;
    top: -1px;
    padding: 0 4px;
    background-color: #F0F0F0;
}
"""


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, value):
        super().__init__(text)
        self.sort_value = value

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class GraphWidget(QWidget):
    def __init__(self, max_value=100.0, line_color=QColor(0, 255, 0), parent=None, points=60,
                 grid_cols=10, grid_rows=8):
        super().__init__(parent)
        self.max_value = max_value
        self.line_color = line_color
        self.data = deque([0.0] * points, maxlen=points)
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.setMinimumHeight(60)
        self.setMinimumWidth(60)

    def add_value(self, value):
        self.data.append(value)
        self.update()

    def set_max_value(self, value):
        self.max_value = max(value, 0.0001)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(0, 0, 0))

        grid_pen = QPen(QColor(0, 70, 0))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)

        for i in range(1, self.grid_cols):
            x = int(rect.width() * i / self.grid_cols)
            painter.drawLine(x, 0, x, rect.height())
        for i in range(1, self.grid_rows):
            y = int(rect.height() * i / self.grid_rows)
            painter.drawLine(0, y, rect.width(), y)

        painter.setPen(QPen(QColor(0, 100, 0)))
        painter.drawRect(0, 0, rect.width() - 1, rect.height() - 1)

        values = list(self.data)
        n = len(values)
        if n < 2:
            return

        w = rect.width()
        h = rect.height()
        step = w / (n - 1)
        points_list = []
        for i, v in enumerate(values):
            x = i * step
            ratio = min(max(v / self.max_value, 0.0), 1.0)
            y = h - ratio * (h - 4) - 2
            points_list.append(QPointF(x, y))

        line_pen = QPen(self.line_color)
        line_pen.setWidth(1)
        painter.setPen(line_pen)
        for i in range(len(points_list) - 1):
            painter.drawLine(points_list[i], points_list[i + 1])


class BarWidget(QWidget):
    def __init__(self, max_value=100.0, bar_color=QColor(0, 255, 0), parent=None,
                 overlay_text=None, grid_cols=4, grid_rows=6):
        super().__init__(parent)
        self.max_value = max_value
        self.bar_color = bar_color
        self.value = 0.0
        self.overlay_text = overlay_text
        self.grid_cols = grid_cols
        self.grid_rows = grid_rows
        self.setMinimumHeight(60)
        self.setMinimumWidth(60)

    def set_value(self, value):
        self.value = value
        self.update()

    def set_overlay_text(self, text):
        self.overlay_text = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        painter.fillRect(rect, QColor(0, 0, 0))

        grid_pen = QPen(QColor(0, 70, 0))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)
        for i in range(1, self.grid_cols):
            x = int(rect.width() * i / self.grid_cols)
            painter.drawLine(x, 0, x, rect.height())
        for i in range(1, self.grid_rows):
            y = int(rect.height() * i / self.grid_rows)
            painter.drawLine(0, y, rect.width(), y)

        painter.setPen(QPen(QColor(0, 100, 0)))
        painter.drawRect(0, 0, rect.width() - 1, rect.height() - 1)

        ratio = min(max(self.value / self.max_value, 0.0), 1.0)
        bar_width = rect.width() * 0.6
        bar_x = (rect.width() - bar_width) / 2
        bar_height = ratio * (rect.height() - 4)
        bar_rect = QRectF(bar_x, rect.height() - bar_height - 2, bar_width, bar_height)
        painter.fillRect(bar_rect, self.bar_color)

        if self.overlay_text:
            painter.setPen(QPen(QColor(255, 255, 255)))
            font = QFont("Noto Sans", max(int(rect.height() / 5.5), 10))
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.overlay_text)


def get_open_windows():
    apps = []
    seen_titles = set()

    # 1. Query wmctrl (X11 / XWayland windows)
    try:
        out = subprocess.check_output(["wmctrl", "-l", "-p"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) >= 5:
                win_id = parts[0]
                pid = int(parts[2])
                title = parts[4]
                if title and title not in ("Desktop", "plasmashell", "Task Manager", "dock", "panel", "Kicker", "Yakuake"):
                    if title not in seen_titles:
                        seen_titles.add(title)
                        apps.append({"title": title, "status": "Running", "pid": pid, "win_id": win_id})
    except Exception:
        pass

    # 2. Query known GUI application processes if wmctrl missed them
    gui_app_names = {
        "spotify", "firefox", "chromium", "google-chrome", "code", "vlc",
        "discord", "telegram-desktop", "steam", "obsidian", "thunar", "dolphin",
        "org.kde.dolphin", "gedit", "kate", "libreoffice", "gnome-terminal",
        "konsole", "alacritty", "kitty", "pamac-manager", "blender", "gimp"
    }

    try:
        current_user = psutil.Process().username()
    except Exception:
        current_user = None

    my_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "name", "username", "cmdline"]):
        try:
            info = proc.info
            pid = info["pid"]
            if pid == my_pid:
                continue
            if current_user and info.get("username") != current_user:
                continue

            name = (info.get("name") or "").lower()
            cmdline = info.get("cmdline") or []
            cmd_str = " ".join(cmdline).lower()

            is_gui = name in gui_app_names or any(g in cmd_str for g in gui_app_names)
            if is_gui:
                display_title = info.get("name").capitalize()
                if display_title not in seen_titles and display_title != "Task manager":
                    seen_titles.add(display_title)
                    apps.append({"title": display_title, "status": "Running", "pid": pid, "win_id": None})
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return apps


def switch_to_window(win_id, pid, title=""):
    """
    Switches to / focuses a window on Wayland (KDE Plasma) via KWin D-Bus interface.
    """
    # 1. Native KDE Plasma KWin D-Bus Scripting activation (Most reliable on Wayland)
    if pid:
        script = f"""
        var clients = workspace.clientList();
        for (var i = 0; i < clients.length; i++) {{
            if (clients[i].pid === {pid}) {{
                workspace.activeClient = clients[i];
                break;
            }}
        }}
        """
        try:
            res = subprocess.run([
                "qdbus", "org.kde.KWin", "/Scripting",
                "org.kde.kwin.Scripting.loadScript", "/dev/stdin"
            ], input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and res.stdout.strip():
                script_id = res.stdout.strip()
                subprocess.run(["qdbus", "org.kde.KWin", f"/Scripting/Script{script_id}", "run"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
        except Exception:
            pass

    # 2. Try kdotool
    if pid:
        try:
            res = subprocess.run(["kdotool", "search", "--pid", str(pid), "windowactivate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    if title:
        try:
            res = subprocess.run(["kdotool", "search", "--name", title, "windowactivate"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 3. Fallback to wmctrl (XWayland)
    if win_id:
        try:
            res = subprocess.run(["wmctrl", "-i", "-a", str(win_id)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    if pid:
        try:
            res = subprocess.run(["wmctrl", "-p", "-a", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


def terminate_task(win_id, pid):
    success = False
    if win_id:
        try:
            subprocess.run(["wmctrl", "-i", "-c", str(win_id)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            success = True
        except Exception:
            pass

    if pid:
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()

            _, alive = psutil.wait_procs(children + [parent], timeout=0.3)
            for p in alive:
                p.kill()
            success = True
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            success = True
        except psutil.AccessDenied:
            pass

    return success


def get_services():
    services = []
    try:
        output = subprocess.check_output(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
            text=True, timeout=3, stderr=subprocess.DEVNULL
        )
        for line in output.splitlines():
            parts = line.strip().split(None, 4)
            if len(parts) >= 4:
                services.append({
                    "name": parts[0],
                    "pid": 0,
                    "description": parts[4] if len(parts) > 4 else "",
                    "status": parts[2] + "/" + parts[3],
                    "group": parts[1],
                })
    except Exception:
        pass
    return services


def get_users():
    result = []
    try:
        for u in psutil.users():
            try:
                started = time.strftime("%Y-%m-%d %H:%M", time.localtime(u.started))
            except Exception:
                started = ""
            result.append({
                "name": u.name,
                "session": getattr(u, "terminal", "") or "tty",
                "status": "Active",
                "client": getattr(u, "host", "") or "local",
                "started": started,
            })
    except Exception:
        pass
    return result


def get_network_adapters():
    adapters = []
    try:
        stats = psutil.net_if_stats()
        for name, st in stats.items():
            adapters.append({
                "name": name,
                "isup": st.isup,
                "speed": st.speed,
            })
    except Exception:
        pass
    return adapters


class ApplicationsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Task", "Status"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.tree)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.end_task_btn = QPushButton("End Task")
        self.switch_to_btn = QPushButton("Switch To")
        self.new_task_btn = QPushButton("New Task...")
        button_row.addWidget(self.end_task_btn)
        button_row.addWidget(self.switch_to_btn)
        button_row.addWidget(self.new_task_btn)
        layout.addLayout(button_row)

        self.end_task_btn.clicked.connect(self.end_task)
        self.switch_to_btn.clicked.connect(self.switch_to)
        self.new_task_btn.clicked.connect(self.new_task)

    def refresh(self):
        selected_pid = None
        selected_items = self.tree.selectedItems()
        if selected_items:
            data = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
            if data:
                selected_pid = data[0]
        scroll_value = self.tree.verticalScrollBar().value()

        self.tree.clear()
        apps = get_open_windows()
        matched_item = None
        for app in apps:
            item = QTreeWidgetItem([app["title"], app["status"]])
            item.setData(0, Qt.ItemDataRole.UserRole, (app["pid"], app.get("win_id"), app["title"]))
            self.tree.addTopLevelItem(item)
            if selected_pid is not None and selected_pid == app["pid"]:
                matched_item = item

        if matched_item is not None:
            matched_item.setSelected(True)

        self.tree.verticalScrollBar().setValue(scroll_value)

    def check_minimize_on_use(self):
        win = self.window()
        if hasattr(win, "minimize_on_use") and win.minimize_on_use:
            if getattr(win, "hide_when_minimized", False):
                win.hide()
            else:
                win.showMinimized()

    def end_task(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        pid, win_id = data[0], data[1]
        
        if not terminate_task(win_id, pid):
            QMessageBox.warning(self, "Task Manager", "Unable to end the selected task.")
        
        self.refresh()
        self.check_minimize_on_use()

    def switch_to(self):
        items = self.tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        pid, win_id, title = data[0], data[1], data[2]
        
        success = switch_to_window(win_id, pid, title)
        if not success:
            QMessageBox.information(self, "Task Manager", "Unable to switch to window.")
        
        self.check_minimize_on_use()

    def new_task(self):
        text, ok = QInputDialog.getText(self, "Create New Task", "Type the command name to open:")
        if ok and text.strip():
            try:
                args = shlex.split(text)
                subprocess.Popen(args)
                self.check_minimize_on_use()
            except Exception as exc:
                QMessageBox.critical(self, "Task Manager", "Unable to launch process.\n\n" + str(exc))


class ProcessesTab(QWidget):
    COLUMNS = ["Image Name", "PID", "User Name", "CPU", "Memory (RSS)", "Command"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process_cache = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        bottom_row = QHBoxLayout()
        self.show_all_users_cb = QCheckBox("Show processes from all users")
        self.show_all_users_cb.setChecked(True)
        bottom_row.addWidget(self.show_all_users_cb)
        bottom_row.addStretch()
        self.end_process_btn = QPushButton("End Process")
        bottom_row.addWidget(self.end_process_btn)
        layout.addLayout(bottom_row)

        self.end_process_btn.clicked.connect(self.end_process)
        self.show_all_users_cb.stateChanged.connect(self.refresh)

    def refresh(self):
        try:
            current_user = psutil.Process().username()
        except Exception:
            current_user = None

        show_all = self.show_all_users_cb.isChecked()
        live_pids = set()
        rows = []

        for proc in psutil.process_iter(["pid", "name", "username"]):
            pid = proc.info.get("pid")
            live_pids.add(pid)
            if pid not in self.process_cache:
                try:
                    self.process_cache[pid] = psutil.Process(pid)
                    self.process_cache[pid].cpu_percent(interval=None)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        for pid in list(self.process_cache.keys()):
            if pid not in live_pids:
                del self.process_cache[pid]

        for pid, proc in self.process_cache.items():
            try:
                name = proc.name()
                username = proc.username()
                if not show_all and current_user and username != current_user:
                    continue
                cpu = proc.cpu_percent(interval=None)
                try:
                    mem_info = proc.memory_info()
                    mem_bytes = mem_info.rss
                except Exception:
                    mem_bytes = 0
                try:
                    cmd = " ".join(proc.cmdline()) or name
                except Exception:
                    cmd = name
                rows.append((name, pid, username, cpu, mem_bytes, cmd))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        selected_pid = None
        sel_items = self.table.selectedItems()
        if sel_items:
            selected_pid = self.table.item(sel_items[0].row(), 1).data(Qt.ItemDataRole.UserRole)
        scroll_value = self.table.verticalScrollBar().value()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        matched_row = None
        for row_idx, (name, pid, username, cpu, mem_bytes, cmd) in enumerate(rows):
            name_item = QTableWidgetItem(name)
            pid_item = NumericTableWidgetItem(str(pid), pid)
            pid_item.setData(Qt.ItemDataRole.UserRole, pid)
            user_item = QTableWidgetItem(username or "")
            cpu_item = NumericTableWidgetItem("{:02d}".format(int(cpu)), cpu)
            mem_kb = mem_bytes // 1024
            mem_item = NumericTableWidgetItem("{:,} K".format(mem_kb), mem_bytes)
            desc_item = QTableWidgetItem(cmd)

            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, pid_item)
            self.table.setItem(row_idx, 2, user_item)
            self.table.setItem(row_idx, 3, cpu_item)
            self.table.setItem(row_idx, 4, mem_item)
            self.table.setItem(row_idx, 5, desc_item)

            if selected_pid is not None and pid == selected_pid:
                matched_row = row_idx

        if matched_row is not None:
            self.table.setRangeSelected(
                QTableWidgetSelectionRange(matched_row, 0, matched_row, self.table.columnCount() - 1),
                True
            )

        self.table.setSortingEnabled(True)
        self.table.verticalScrollBar().setValue(scroll_value)

    def end_process(self):
        sel_items = self.table.selectedItems()
        if not sel_items:
            return
        row = sel_items[0].row()
        pid = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        terminate_task(None, pid)
        self.refresh()


class ServicesTab(QWidget):
    COLUMNS = ["Unit Name", "Load State", "Description", "Active State", "Sub State"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def refresh(self):
        selected_name = None
        sel_items = self.table.selectedItems()
        if sel_items:
            selected_name = self.table.item(sel_items[0].row(), 0).text()
        scroll_value = self.table.verticalScrollBar().value()

        services = get_services()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(services))
        matched_row = None
        for row_idx, svc in enumerate(services):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(svc["name"])))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(svc["group"])))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(svc["description"])))
            parts = str(svc["status"]).split("/", 1)
            active = parts[0] if parts else ""
            sub = parts[1] if len(parts) > 1 else ""
            self.table.setItem(row_idx, 3, QTableWidgetItem(active))
            self.table.setItem(row_idx, 4, QTableWidgetItem(sub))
            if selected_name is not None and str(svc["name"]) == selected_name:
                matched_row = row_idx

        if matched_row is not None:
            self.table.setRangeSelected(
                QTableWidgetSelectionRange(matched_row, 0, matched_row, self.table.columnCount() - 1),
                True
            )

        self.table.setSortingEnabled(True)
        self.table.verticalScrollBar().setValue(scroll_value)


class InfoBox(QGroupBox):
    def __init__(self, title, rows, parent=None):
        super().__init__(title, parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(10, 14, 14, 10)
        layout.setHorizontalSpacing(18)
        layout.setVerticalSpacing(6)

        self.value_labels = {}
        for row_idx, (key, label_text) in enumerate(rows):
            name_label = QLabel(label_text)
            value_label = QLabel("0")
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(name_label, row_idx, 0)
            layout.addWidget(value_label, row_idx, 1)
            self.value_labels[key] = value_label

        layout.setColumnStretch(1, 1)

    def set_value(self, key, text):
        if key in self.value_labels:
            self.value_labels[key].setText(text)


class PerformanceTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        cpu_row = QHBoxLayout()
        cpu_row.setSpacing(8)

        cpu_mini_box = QGroupBox("CPU Usage")
        cpu_mini_layout = QVBoxLayout(cpu_mini_box)
        cpu_mini_layout.setContentsMargins(6, 10, 6, 6)
        cpu_mini_layout.setSpacing(4)
        self.cpu_mini_bar = BarWidget(max_value=100.0, bar_color=QColor(0, 200, 0))
        cpu_mini_layout.addWidget(self.cpu_mini_bar, 1)
        self.cpu_percent_label = QLabel("0%")
        self.cpu_percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cpu_percent_label.setFont(QFont("Noto Sans", 11))
        cpu_mini_layout.addWidget(self.cpu_percent_label, 0)
        cpu_mini_box.setFixedWidth(150)
        cpu_row.addWidget(cpu_mini_box)

        cpu_hist_box = QGroupBox("CPU Usage History")
        cpu_hist_layout = QVBoxLayout(cpu_hist_box)
        cpu_hist_layout.setContentsMargins(6, 10, 6, 6)
        self.cpu_graph = GraphWidget(max_value=100.0, line_color=QColor(0, 255, 0))
        cpu_hist_layout.addWidget(self.cpu_graph)
        cpu_row.addWidget(cpu_hist_box, 1)

        outer.addLayout(cpu_row, 1)

        mem_row = QHBoxLayout()
        mem_row.setSpacing(8)

        mem_mini_box = QGroupBox("Memory")
        mem_mini_layout = QVBoxLayout(mem_mini_box)
        mem_mini_layout.setContentsMargins(6, 10, 6, 6)
        mem_mini_layout.setSpacing(4)
        self.mem_mini_bar = BarWidget(max_value=100.0, bar_color=QColor(70, 145, 230))
        mem_mini_layout.addWidget(self.mem_mini_bar, 1)
        self.mem_percent_label = QLabel("0.00 GB")
        self.mem_percent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mem_percent_label.setFont(QFont("Noto Sans", 11))
        mem_mini_layout.addWidget(self.mem_percent_label, 0)
        mem_mini_box.setFixedWidth(150)
        mem_row.addWidget(mem_mini_box)

        mem_hist_box = QGroupBox("Physical Memory Usage History")
        mem_hist_layout = QVBoxLayout(mem_hist_box)
        mem_hist_layout.setContentsMargins(6, 10, 6, 6)
        self.mem_graph = GraphWidget(max_value=100.0, line_color=QColor(70, 145, 230))
        mem_hist_layout.addWidget(self.mem_graph)
        mem_row.addWidget(mem_hist_box, 1)

        outer.addLayout(mem_row, 1)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self.phys_box = InfoBox("Physical Memory (MB)", [
            ("total", "Total"),
            ("cached", "Cached"),
            ("available", "Available"),
            ("free", "Free"),
        ])
        info_row.addWidget(self.phys_box, 1)

        self.kernel_box = InfoBox("Swap / Virtual (MB)", [
            ("used", "Used Swap"),
            ("total", "Total Swap"),
        ])
        info_row.addWidget(self.kernel_box, 1)

        self.system_box = InfoBox("System", [
            ("handles", "File Descriptors"),
            ("threads", "Threads"),
            ("processes", "Processes"),
            ("uptime", "Up Time"),
        ])
        info_row.addWidget(self.system_box, 1)

        outer.addLayout(info_row, 0)

    def refresh(self):
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_graph.add_value(cpu_percent)
        self.cpu_mini_bar.set_value(cpu_percent)
        self.cpu_percent_label.setText("{}%".format(int(cpu_percent)))

        vm = psutil.virtual_memory()
        mem_percent = vm.percent
        self.mem_graph.add_value(mem_percent)
        self.mem_mini_bar.set_value(mem_percent)

        mem_used_gb = (vm.total - vm.available) / (1024 ** 3)
        self.mem_percent_label.setText("{:.2f} GB".format(mem_used_gb))

        mb = 1024 * 1024
        self.phys_box.set_value("total", "{:,}".format(vm.total // mb))
        cached = getattr(vm, "cached", 0)
        self.phys_box.set_value("cached", "{:,}".format(cached // mb))
        self.phys_box.set_value("available", "{:,}".format(vm.available // mb))
        self.phys_box.set_value("free", "{:,}".format(vm.free // mb))

        total_fds = 0
        total_threads = 0
        total_processes = 0
        for proc in psutil.process_iter():
            total_processes += 1
            try:
                total_threads += proc.num_threads()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            try:
                if hasattr(proc, "num_fds"):
                    total_fds += proc.num_fds()
            except Exception:
                continue

        self.system_box.set_value("handles", "{:,}".format(total_fds))
        self.system_box.set_value("threads", "{:,}".format(total_threads))
        self.system_box.set_value("processes", "{:,}".format(total_processes))

        try:
            boot_time = psutil.boot_time()
            uptime_seconds = int(time.time() - boot_time)
            days, rem = divmod(uptime_seconds, 86400)
            hours, rem = divmod(rem, 3600)
            minutes, seconds = divmod(rem, 60)
            self.system_box.set_value("uptime", "{}:{:02d}:{:02d}:{:02d}".format(days, hours, minutes, seconds))
        except Exception:
            pass

        try:
            swap = psutil.swap_memory()
            self.kernel_box.set_value("used", "{:,}".format(swap.used // mb))
            self.kernel_box.set_value("total", "{:,}".format(swap.total // mb))
        except Exception:
            pass

        return cpu_percent, mem_percent


class NetworkingTab(QWidget):
    COLUMNS = ["Adapter Name", "Network Utilization", "Link Speed", "State"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prev_io = psutil.net_io_counters()
        self.prev_time = time.time()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        graph_box = QGroupBox("Network Utilization")
        graph_layout = QVBoxLayout(graph_box)
        self.graph = GraphWidget(max_value=100.0, line_color=QColor(255, 255, 0))
        graph_layout.addWidget(self.graph)
        layout.addWidget(graph_box, 2)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

    def refresh(self):
        now = time.time()
        elapsed = max(now - self.prev_time, 0.001)
        io_now = psutil.net_io_counters()

        bytes_delta = (io_now.bytes_sent - self.prev_io.bytes_sent) + (io_now.bytes_recv - self.prev_io.bytes_recv)
        throughput_bps = bytes_delta / elapsed

        adapters = get_network_adapters()
        max_speed_mbps = max([a["speed"] for a in adapters if a["speed"] and a["speed"] > 0], default=1000)
        max_bytes_per_sec = max_speed_mbps * 1000000 / 8
        utilization_percent = min((throughput_bps / max_bytes_per_sec) * 100 if max_bytes_per_sec else 0, 100)

        self.graph.add_value(utilization_percent)

        self.table.setRowCount(len(adapters))
        for row_idx, adapter in enumerate(adapters):
            self.table.setItem(row_idx, 0, QTableWidgetItem(adapter["name"]))
            util_text = "{:.2f} %".format(utilization_percent) if row_idx == 0 else "0.00 %"
            self.table.setItem(row_idx, 1, QTableWidgetItem(util_text))
            speed_text = "{} Mbps".format(adapter["speed"]) if adapter["speed"] else "N/A"
            self.table.setItem(row_idx, 2, QTableWidgetItem(speed_text))
            state_text = "Connected" if adapter["isup"] else "Disconnected"
            self.table.setItem(row_idx, 3, QTableWidgetItem(state_text))

        self.prev_io = io_now
        self.prev_time = now


class UsersTab(QWidget):
    COLUMNS = ["User", "ID", "Status", "Client Name", "Session"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self.disconnect_btn = QPushButton("Disconnect")
        self.logoff_btn = QPushButton("Logoff")
        bottom_row.addWidget(self.disconnect_btn)
        bottom_row.addWidget(self.logoff_btn)
        layout.addLayout(bottom_row)

        self.disconnect_btn.clicked.connect(self.disconnect_user)
        self.logoff_btn.clicked.connect(self.logoff_user)

    def refresh(self):
        users = get_users()
        self.table.setRowCount(len(users))
        for row_idx, user in enumerate(users):
            self.table.setItem(row_idx, 0, QTableWidgetItem(user["name"]))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(row_idx + 1)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(user["status"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem(user["client"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(user["session"]))

    def disconnect_user(self):
        if not self.table.selectedItems():
            return
        row = self.table.selectedItems()[0].row()
        username = self.table.item(row, 0).text()
        try:
            subprocess.Popen(["loginctl", "terminate-user", username])
        except Exception:
            QMessageBox.information(self, "Task Manager", "Unable to disconnect user session.")

    def logoff_user(self):
        if not self.table.selectedItems():
            return
        row = self.table.selectedItems()[0].row()
        username = self.table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Task Manager",
            f"Terminate session for user '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                subprocess.Popen(["pkill", "-u", username])
            except Exception:
                QMessageBox.information(self, "Task Manager", "Unable to log off user.")


class TaskManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Manager")
        self.resize(760, 560)
        self.setStyleSheet(APP_STYLESHEET)

        self.update_interval_ms = 1000
        self.minimize_on_use = False
        self.hide_when_minimized = False
        self._is_exiting = False

        self.build_menu_bar()
        self.build_central_widget()
        self.build_status_bar()
        self.build_tray_icon()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all)
        self.timer.start(self.update_interval_ms)

        psutil.cpu_percent(interval=None)
        self.refresh_all()

    def build_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        new_task_action = QAction("New Task (Run...)", self)
        new_task_action.triggered.connect(self.file_new_task)
        file_menu.addAction(new_task_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit Task Manager", self)
        exit_action.triggered.connect(self.exit_app)
        file_menu.addAction(exit_action)

        options_menu = menu_bar.addMenu("Options")
        self.always_on_top_action = QAction("Always on Top", self, checkable=True)
        self.always_on_top_action.toggled.connect(self.toggle_always_on_top)
        options_menu.addAction(self.always_on_top_action)

        self.minimize_on_use_action = QAction("Minimize On Use", self, checkable=True)
        self.minimize_on_use_action.toggled.connect(self.toggle_minimize_on_use)
        options_menu.addAction(self.minimize_on_use_action)

        self.hide_when_minimized_action = QAction("Hide When Minimized", self, checkable=True)
        self.hide_when_minimized_action.toggled.connect(self.toggle_hide_when_minimized)
        options_menu.addAction(self.hide_when_minimized_action)

        view_menu = menu_bar.addMenu("View")
        refresh_action = QAction("Refresh Now", self)
        refresh_action.triggered.connect(self.refresh_all)
        view_menu.addAction(refresh_action)

        update_speed_menu = view_menu.addMenu("Update Speed")
        speed_group = QActionGroup(self)
        speed_group.setExclusive(True)

        self.speed_high_action = QAction("High", self, checkable=True)
        self.speed_normal_action = QAction("Normal", self, checkable=True)
        self.speed_low_action = QAction("Low", self, checkable=True)
        self.speed_paused_action = QAction("Paused", self, checkable=True)

        self.speed_normal_action.setChecked(True)

        for action, interval in (
            (self.speed_high_action, 500),
            (self.speed_normal_action, 1000),
            (self.speed_low_action, 2000),
            (self.speed_paused_action, None),
        ):
            speed_group.addAction(action)
            update_speed_menu.addAction(action)
            action.triggered.connect(lambda checked, i=interval: self.set_update_speed(i))

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About Task Manager", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def build_central_widget(self):
        self.tabs = QTabWidget()

        self.applications_tab = ApplicationsTab()
        self.processes_tab = ProcessesTab()
        self.services_tab = ServicesTab()
        self.performance_tab = PerformanceTab()
        self.networking_tab = NetworkingTab()
        self.users_tab = UsersTab()

        self.tabs.addTab(self.applications_tab, "Applications")
        self.tabs.addTab(self.processes_tab, "Processes")
        self.tabs.addTab(self.services_tab, "Services")
        self.tabs.addTab(self.performance_tab, "Performance")
        self.tabs.addTab(self.networking_tab, "Networking")
        self.tabs.addTab(self.users_tab, "Users")

        self.setCentralWidget(self.tabs)

    def build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.processes_label = QLabel("Processes: 0")
        self.cpu_label = QLabel("CPU Usage: 0%")
        self.memory_label = QLabel("Physical Memory: 0%")

        for label in (self.processes_label, self.cpu_label, self.memory_label):
            label.setFrameShape(QFrame.Shape.Panel)
            label.setFrameShadow(QFrame.Shadow.Sunken)
            label.setContentsMargins(6, 2, 6, 2)
            self.status_bar.addPermanentWidget(label)

    def build_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_menu = QMenu(self)

        self.restore_action = QAction("Restore Task Manager", self)
        self.restore_action.triggered.connect(self.restore_from_tray)

        self.tray_always_on_top_action = QAction("Always on Top", self, checkable=True)
        self.tray_always_on_top_action.triggered.connect(self.toggle_always_on_top)

        self.tray_exit_action = QAction("Exit Task Manager", self)
        self.tray_exit_action.triggered.connect(self.exit_app)

        self.tray_menu.addAction(self.restore_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_always_on_top_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.tray_exit_action)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.update_tray_icon(0)
        self.tray_icon.show()

    def update_tray_icon(self, cpu_percent):
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(0, 0, 0))
        painter = QPainter(pixmap)
        painter.fillRect(1, 1, 14, 14, QColor(0, 50, 0))
        h = int(14 * (min(max(cpu_percent, 0.0), 100.0) / 100.0))
        if h > 0:
            painter.fillRect(1, 15 - h, 14, h, QColor(0, 255, 0))
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("CPU Usage: {}%".format(int(cpu_percent)))

    def apply_always_on_top_linux(self, checked):
        wh = self.windowHandle()
        if wh:
            wh.setFlag(Qt.WindowType.WindowStaysOnTopHint, checked)

        try:
            win_id = hex(int(self.winId()))
            action = "add" if checked else "remove"
            subprocess.Popen(
                ["wmctrl", "-i", "-r", win_id, "-b", f"{action},above"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    def restore_from_tray(self):
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

        if hasattr(self, "always_on_top_action") and self.always_on_top_action.isChecked():
            self.apply_always_on_top_linux(True)

    def on_tray_icon_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.isVisible() and not self.isMinimized():
                if self.hide_when_minimized:
                    self.hide()
                else:
                    self.showMinimized()
            else:
                self.restore_from_tray()

    def refresh_all(self):
        try:
            self.applications_tab.refresh()
        except Exception:
            pass
        try:
            self.processes_tab.refresh()
        except Exception:
            pass
        try:
            self.services_tab.refresh()
        except Exception:
            pass
        try:
            cpu_percent, mem_percent = self.performance_tab.refresh()
        except Exception:
            cpu_percent, mem_percent = 0.0, 0.0
        try:
            self.networking_tab.refresh()
        except Exception:
            pass
        try:
            self.users_tab.refresh()
        except Exception:
            pass

        try:
            process_count = len(psutil.pids())
        except Exception:
            process_count = 0

        self.processes_label.setText("Processes: {}".format(process_count))
        self.cpu_label.setText("CPU Usage: {}%".format(int(cpu_percent)))
        self.memory_label.setText("Physical Memory: {}%".format(int(mem_percent)))
        self.update_tray_icon(cpu_percent)

    def file_new_task(self):
        self.applications_tab.new_task()

    def toggle_always_on_top(self, checked):
        if hasattr(self, "always_on_top_action"):
            self.always_on_top_action.blockSignals(True)
            self.always_on_top_action.setChecked(checked)
            self.always_on_top_action.blockSignals(False)
        if hasattr(self, "tray_always_on_top_action"):
            self.tray_always_on_top_action.blockSignals(True)
            self.tray_always_on_top_action.setChecked(checked)
            self.tray_always_on_top_action.blockSignals(False)

        self.apply_always_on_top_linux(checked)

    def toggle_minimize_on_use(self, checked):
        self.minimize_on_use = checked

    def toggle_hide_when_minimized(self, checked):
        self.hide_when_minimized = checked

    def set_update_speed(self, interval_ms):
        if interval_ms is None:
            self.timer.stop()
        else:
            self.update_interval_ms = interval_ms
            self.timer.start(interval_ms)

    def show_about(self):
        QMessageBox.information(
            self, "About Task Manager",
            "Task Manager for Arch Linux\nBuilt with PyQt6 and psutil."
        )

    def exit_app(self):
        self._is_exiting = True
        self.close()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if self.isMinimized() and self.hide_when_minimized:
                QTimer.singleShot(0, self.hide)

    def closeEvent(self, event):
        if getattr(self, "_is_exiting", False):
            self.timer.stop()
            if hasattr(self, "tray_icon"):
                self.tray_icon.hide()
            event.accept()
        elif self.hide_when_minimized:
            event.ignore()
            self.hide()
        else:
            self.timer.stop()
            if hasattr(self, "tray_icon"):
                self.tray_icon.hide()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TaskManagerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()