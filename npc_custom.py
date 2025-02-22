import sys
import os
import zipfile
import random
import subprocess  # Для открытия файлов в проводнике
import json
import uuid  # Для генерации уникальных имен файлов
import asyncio
import time

from PIL import Image, ImageQt, ImageEnhance, ImageOps, ImageChops
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QScrollArea, QComboBox, QSplitter, QColorDialog, QInputDialog,
    QSizePolicy, QFrame, QToolButton, QMenu, QAction, QMessageBox, QProgressBar, QDialog, QSpinBox
)
from PyQt5.QtGui import QPixmap, QIcon, QImage, QFont, QColor
from PyQt5.QtCore import Qt, QSettings, QSize, QTimer, QThread, pyqtSignal

from qasync import QEventLoop, asyncSlot

# Определение базовой директории: если собрано в EXE – рядом с EXE, иначе рядом со скриптом.
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

def find_default_archive():
    """Ищет в BASE_DIR архив с именем Construct с поддерживаемым расширением."""
    allowed_ext = [".zip", ".tar", ".tgz", ".tar.gz", ".rar", ".7z"]
    for ext in allowed_ext:
        candidate = os.path.join(BASE_DIR, "Construct" + ext)
        if os.path.exists(candidate):
            return candidate
    return ""  # Если не найден

# ------------------------- Асинхронные диалоги -------------------------
async def async_get_open_file_name(parent, caption, directory, filter):
    dialog = QFileDialog(parent, caption, directory, filter)
    dialog.setFileMode(QFileDialog.ExistingFile)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.show()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    dialog.fileSelected.connect(lambda file: future.set_result(file))
    file = await future
    return file, None

async def async_get_text(parent, title, label):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setModal(False)
    dialog.show()
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    def accepted():
        future.set_result((dialog.textValue(), True))
        dialog.close()
    def rejected():
        future.set_result(("", False))
        dialog.close()
    dialog.accepted.connect(accepted)
    dialog.rejected.connect(rejected)
    return await future

# -------------------- Рабочие классы --------------------
from PyQt5.QtCore import QObject
class ExtractionWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, archive_path, extract_path):
        super().__init__()
        self.archive_path = archive_path
        self.extract_path = extract_path

    def run(self):
        try:
            if not os.path.exists(self.extract_path):
                os.makedirs(self.extract_path, exist_ok=True)
            ext = os.path.splitext(self.archive_path)[1].lower()
            if ext == ".zip":
                with zipfile.ZipFile(self.archive_path, 'r') as archive:
                    archive.extractall(self.extract_path)
            elif ext in [".tar", ".tgz", ".tar.gz"]:
                import tarfile
                with tarfile.open(self.archive_path, 'r:*') as archive:
                    archive.extractall(self.extract_path)
            elif ext == ".rar":
                try:
                    import rarfile
                    with rarfile.RarFile(self.archive_path) as archive:
                        archive.extractall(self.extract_path)
                except ImportError:
                    self.error.emit("Модуль rarfile не установлен. Установите его (pip install rarfile).")
                    return
                except Exception as e:
                    self.error.emit(f"Не удалось открыть RAR архив: {e}")
                    return
            elif ext == ".7z":
                try:
                    import py7zr
                    with py7zr.SevenZipFile(self.archive_path, mode='r') as archive:
                        archive.extractall(path=self.extract_path)
                except ImportError:
                    self.error.emit("Модуль py7zr не установлен. Установите его (pip install py7zr).")
                    return
                except Exception as e:
                    self.error.emit(f"Ошибка при открытии 7z архива: {e}")
                    return
            else:
                self.error.emit(f"Формат архива '{ext}' не поддерживается.")
                return

            # Создаём папки modified_accessories и presets в BASE_DIR
            modified_path = os.path.join(BASE_DIR, "modified_accessories")
            presets_path = os.path.join(BASE_DIR, "presets")
            os.makedirs(modified_path, exist_ok=True)
            os.makedirs(presets_path, exist_ok=True)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class GenerationWorker(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    
    def __init__(self, skins, accessories, gender, number):
        super().__init__()
        self.skins = skins
        self.accessories = accessories
        self.gender = gender
        self.number = number

    def run(self):
        datasets_dir = os.path.join(BASE_DIR, "datasets")
        os.makedirs(datasets_dir, exist_ok=True)
        layers_order = [
            "Back Layers",
            "Skin",
            "Clothing",
            "Hair",
            "Hat",
            "Mask",
            "Arm Layers",
            "Ears",
            "Hand",
            "Hostage Layers"
        ]
        for i in range(self.number):
            if not self.skins:
                continue
            final_image = random.choice(self.skins).copy()
            selected_accessories = {}
            for category, acc_list in self.accessories.items():
                if acc_list and random.random() < 0.5:
                    accessory = random.choice(acc_list)
                    if category not in selected_accessories:
                        selected_accessories[category] = []
                    selected_accessories[category].append(accessory)
            for layer in layers_order:
                if layer == "Skin":
                    continue
                if layer in selected_accessories:
                    for name, image in selected_accessories[layer]:
                        if layer == "Back Layers":
                            bg = Image.new("RGBA", final_image.size)
                            bg.paste(image, (0, 0), image)
                            bg.paste(final_image, (0, 0), final_image)
                            final_image = bg
                        else:
                            final_image.paste(image, (0, 0), image)
            file_path = os.path.join(datasets_dir, f"random_sprite_{i+1}_{self.gender}.png")
            final_image.save(file_path, "PNG")
            self.progress.emit(int((i+1) * 100 / self.number))
        self.finished.emit()

# ------------- Кнопка для пресета -------------
class PresetButton(QPushButton):
    def __init__(self, preset_name, icon_file, main_window, parent=None):
        super().__init__(parent)
        self.preset_name = preset_name
        self.main_window = main_window
        self.setFixedSize(64, 64)
        self.setToolTip(preset_name)
        if os.path.exists(icon_file):
            self.setIcon(QIcon(icon_file))
            self.setIconSize(QSize(64, 64))
        else:
            self.setText(preset_name)
        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self.main_window.delete_preset(self.preset_name)
        else:
            super().keyPressEvent(event)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        resave_action = QAction("Пересохранить пресет", self)
        resave_action.triggered.connect(lambda: self.main_window.resave_preset(self.preset_name))
        menu.addAction(resave_action)
        menu.exec_(event.globalPos())

# ------------- Окно истории изменений -------------
class HistoryWindow(QDialog):
    def __init__(self, history_list, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История изменений")
        self.resize(400, 300)
        self.history_list = history_list
        self.main_window = main_window
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        for idx, state in enumerate(self.history_list):
            summary = f"Этап {idx+1}: Skin {state['current_skin_index']}, " \
                      f"Аксессуары: {state['selected_accessories']}"
            item = QListWidgetItem(summary)
            item.setData(Qt.UserRole, state)
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self.item_double_clicked)
    
    def item_double_clicked(self, item):
        state = item.data(Qt.UserRole)
        self.main_window.restore_history_state(state)
        self.history_list.remove(state)
        self.history_list.append(state)
        self.accept()

# ----------- Окно уведомления о временных пресетах -----------
class TempBackupNotificationWindow(QDialog):
    def __init__(self, temp_files, main_window, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Уведомление об удалении временных пресетов")
        self.resize(500, 400)
        self.temp_files = temp_files
        self.main_window = main_window
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)
        for file in self.temp_files:
            preset_name = os.path.splitext(os.path.basename(file))[0]
            item = QListWidgetItem(preset_name)
            item.setData(Qt.UserRole, file)
            item.setBackground(QColor("red"))
            self.list_widget.addItem(item)
        self.list_widget.itemClicked.connect(self.toggle_item_color)
        buttons_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Подтвердить")
        self.cancel_button = QPushButton("Отмена")
        self.confirm_button.clicked.connect(self.confirm)
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.confirm_button)
        buttons_layout.addWidget(self.cancel_button)
        layout.addLayout(buttons_layout)
    
    def toggle_item_color(self, item):
        current_color = item.background().color().name()
        if current_color == QColor("red").name():
            item.setBackground(QColor("green"))
        else:
            item.setBackground(QColor("red"))
    
    def confirm(self):
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            file = item.data(Qt.UserRole)
            if item.background().color().name() == QColor("red").name():
                if os.path.exists(file):
                    os.remove(file)
                icon_file = file.replace(".json", ".png")
                if os.path.exists(icon_file):
                    os.remove(icon_file)
            else:
                dir_path = os.path.dirname(file)
                backup_name = "backup_" + os.path.basename(file).replace("tempbackup_", "")
                new_file = os.path.join(dir_path, backup_name)
                os.rename(file, new_file)
                icon_file = file.replace(".json", ".png")
                new_icon_file = new_file.replace(".json", ".png")
                if os.path.exists(icon_file):
                    os.rename(icon_file, new_icon_file)
        self.accept()

# ------------------ Основной класс приложения ------------------
class SpriteCustomizer(QWidget):
    def __init__(self, archive_path):
        super().__init__()
        self.base_dir = BASE_DIR
        self.archive_path = archive_path

        # Пути для работы – все внутри base_dir
        self.extract_path = os.path.join(self.base_dir, "extracted_sprites")
        self.modified_path = os.path.join(self.base_dir, "modified_accessories")
        self.presets_path = os.path.join(self.base_dir, "presets")

        self.gender = "Man"
        self.accessory_file_paths = {}

        # Распаковку запускаем позже, если архив задан
        if self.archive_path and os.path.exists(self.archive_path):
            self.extract_archive()

        self.current_skin_index = 0
        self.skins = []
        self.current_skin = None
        self.accessories = {}
        self.selected_accessories = {}
        self.layers_order = [
            "Back Layers",
            "Skin",
            "Clothing",
            "Hair",
            "Hat",
            "Mask",
            "Arm Layers",
            "Ears",
            "Hand",
            "Hostage Layers"
        ]
        self.colors = {}
        self.accessory_file_paths = {}

        # История изменений
        self.history = []
        self.history_index = -1

        self.load_sprites()
        self.scale_factor = 1.0
        self.preview_scale_factor = 1.0
        self.character_pixmap = None

        self.init_ui()
        QTimer.singleShot(0, self.update_character_display)

        # Если архив не задан или не найден, сразу открываем проводник для выбора архива
        if not self.archive_path or not os.path.exists(self.archive_path):
            QTimer.singleShot(100, lambda: asyncio.ensure_future(self.open_archive()))

    def extract_archive(self):
        if os.path.exists(self.extract_path):
            return
        self.extraction_thread = QThread()
        self.extraction_worker = ExtractionWorker(self.archive_path, self.extract_path)
        self.extraction_worker.moveToThread(self.extraction_thread)
        self.extraction_thread.started.connect(self.extraction_worker.run)
        self.extraction_worker.finished.connect(self.on_extraction_finished)
        self.extraction_worker.error.connect(lambda msg: QMessageBox.warning(self, "Ошибка", msg))
        self.extraction_worker.finished.connect(self.extraction_thread.quit)
        self.extraction_worker.finished.connect(self.extraction_worker.deleteLater)
        self.extraction_thread.finished.connect(self.extraction_thread.deleteLater)
        self.extraction_thread.start()

    def on_extraction_finished(self):
        self.load_sprites()
        self.current_skin_index = 0
        self.current_skin = self.skins[self.current_skin_index] if self.skins else None
        self.update_character_display()
        if hasattr(self, 'category_list') and self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()

    def load_sprites(self):
        base_path = os.path.join(self.extract_path, "Construct", self.gender)
        self.accessories = {layer: [] for layer in self.layers_order if layer != "Skin"}
        self.selected_accessories = {key: [] for key in self.accessories.keys()}
        self.skins = []
        self.current_skin = None
        self.colors = {}
        self.accessory_file_paths = {}

        if os.path.exists(base_path):
            for root, dirs, files in os.walk(base_path):
                category = os.path.basename(root)
                for file in files:
                    if file.endswith(".png"):
                        image_path = os.path.join(root, file)
                        image = Image.open(image_path).convert("RGBA")
                        if category == "Skin":
                            self.skins.append(image)
                            if self.current_skin is None:
                                self.current_skin = image
                        elif category in self.accessories:
                            self.accessories[category].append((file, image))
                            self.accessory_file_paths[(category, file)] = image_path

        modified_base_path = os.path.join(self.modified_path, self.gender)
        if os.path.exists(modified_base_path):
            for root, dirs, files in os.walk(modified_base_path):
                category = os.path.basename(root)
                for file in files:
                    if file.endswith(".png"):
                        image_path = os.path.join(root, file)
                        image = Image.open(image_path).convert("RGBA")
                        if category in self.accessories:
                            self.accessories[category].append((file, image))
                            self.accessory_file_paths[(category, file)] = image_path
                        else:
                            self.accessories[category] = [(file, image)]
                            self.accessory_file_paths[(category, file)] = image_path

    @asyncSlot()
    async def init_ui(self):
        self.setWindowTitle("Sprite Customizer")
        self.resize(1200, 800)
        self.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                text-align: center;
                font-size: 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QListWidget {
                background-color: #3E3E3E;
            }
            QComboBox {
                background-color: #3E3E3E;
                padding: 5px;
                font-size: 16px;
            }
            QLabel {
                font-size: 16px;
            }
        """)

        self.accessory_list = QListWidget()
        self.accessory_list.itemClicked.connect(self.toggle_accessory)
        self.accessory_list.setIconSize(QSize(128, 128))
        self.accessory_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.accessory_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.accessory_list.customContextMenuRequested.connect(self.show_accessory_context_menu)

        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Левая панель
        left_panel = QVBoxLayout()
        open_archive_button = QPushButton("Открыть архив")
        open_archive_button.clicked.connect(self.open_archive)
        left_panel.addWidget(open_archive_button)

        about_button = QPushButton("О программе")
        about_button.clicked.connect(self.show_about)
        left_panel.addWidget(about_button)

        self.gender_selector = QComboBox()
        self.gender_selector.addItems(["Man", "Woman"])
        self.gender_selector.currentTextChanged.connect(self.change_gender)
        left_panel.addWidget(self.gender_selector)

        self.category_list = QListWidget()
        for category in self.accessories.keys():
            item = QListWidgetItem(category)
            self.category_list.addItem(item)
        self.category_list.currentItemChanged.connect(self.display_accessories)
        left_panel.addWidget(self.category_list)

        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_panel.addWidget(self.preview_label)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        self.splitter.addWidget(left_widget)

        # Центральная панель
        character_layout = QVBoxLayout()
        self.character_label = QLabel()
        self.character_label.setAlignment(Qt.AlignCenter)
        self.character_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        character_layout.addWidget(self.character_label)

        skin_controls = QHBoxLayout()
        prev_skin_button = QPushButton("Предыдущий скин")
        prev_skin_button.clicked.connect(self.prev_skin)
        next_skin_button = QPushButton("Следующий скин")
        next_skin_button.clicked.connect(self.next_skin)
        skin_controls.addWidget(prev_skin_button)
        skin_controls.addWidget(next_skin_button)
        character_layout.addLayout(skin_controls)

        save_button = QPushButton("Сохранить изображение")
        save_button.clicked.connect(self.save_combined_image)
        character_layout.addWidget(save_button)

        animation_button = QPushButton("Показать анимацию")
        animation_button.clicked.connect(self.show_animation_window)
        character_layout.addWidget(animation_button)

        save_config_button = QPushButton("Сохранить пресет")
        save_config_button.clicked.connect(self.save_character_config)
        character_layout.addWidget(save_config_button)

        clear_button = QPushButton("Очистить пресет")
        clear_button.clicked.connect(self.clear_preset)
        character_layout.addWidget(clear_button)

        nav_layout = QHBoxLayout()
        undo_button = QPushButton("↩")
        undo_button.clicked.connect(self.undo_history)
        redo_button = QPushButton("↪")
        redo_button.clicked.connect(self.redo_history)
        random_button = QPushButton("↻")
        random_button.clicked.connect(self.generate_random_character)
        nav_layout.addWidget(undo_button)
        nav_layout.addWidget(redo_button)
        nav_layout.addWidget(random_button)
        character_layout.addLayout(nav_layout)

        history_button = QPushButton("История изменений")
        history_button.clicked.connect(self.show_history)
        character_layout.addWidget(history_button)

        generate_button = QPushButton("Генерация спрайтов")
        generate_button.clicked.connect(self.open_generation_window)
        character_layout.addWidget(generate_button)

        self.presets_scroll_area = QScrollArea()
        self.presets_scroll_area.setWidgetResizable(True)
        self.presets_widget = QWidget()
        self.presets_layout = QHBoxLayout(self.presets_widget)
        self.presets_layout.setAlignment(Qt.AlignLeft)
        self.presets_scroll_area.setWidget(self.presets_widget)
        character_layout.addWidget(QLabel("Сохраненные пресеты:"))
        character_layout.addWidget(self.presets_scroll_area)

        self.load_presets_list()
        left_widget_for_presets = QWidget()
        left_widget_for_presets.setLayout(character_layout)
        self.splitter.addWidget(left_widget_for_presets)

        # Правая панель
        accessory_layout = QVBoxLayout()
        accessory_layout.addWidget(self.accessory_list)
        color_button = QPushButton("Изменить цвет аксессуара")
        color_button.clicked.connect(self.change_accessory_color)
        accessory_layout.addWidget(color_button)
        accessory_widget = QWidget()
        accessory_widget.setLayout(accessory_layout)
        self.splitter.addWidget(accessory_widget)

        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview_animation)
        self.preview_frame_index = 0
        self.preview_animation_frames = []
        self.preview_timer.start(100)

        self.load_settings()
        self.scale_factor = 1.0
        self.preview_scale_factor = 1.0
        self.character_pixmap = None

        self.check_temp_backups()

    @asyncSlot()
    async def open_archive(self):
        # Автоматически открываем проводник для выбора архива
        file_name, _ = await async_get_open_file_name(
            self,
            "Выберите архив (ZIP, TAR, TGZ, TAR.GZ, RAR, 7Z)",
            self.base_dir,
            "Archive Files (*.zip *.tar *.tar.gz *.tgz *.rar *.7z)"
        )
        if not file_name:
            return

        file_name = os.path.abspath(file_name)
        if not os.path.exists(file_name):
            QMessageBox.warning(self, "Ошибка", "Указанный архив не найден!")
            return

        # Если архив не в base_dir — копируем его туда
        if os.path.dirname(file_name) != self.base_dir:
            try:
                import shutil
                dest_file = os.path.join(self.base_dir, os.path.basename(file_name))
                shutil.copy2(file_name, dest_file)
                file_name = dest_file
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось скопировать архив: {e}")
                return

        self.archive_path = file_name

        # Удаляем старую распаковку, если она существует
        if os.path.exists(self.extract_path):
            try:
                import shutil
                shutil.rmtree(self.extract_path)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось удалить старую распаковку: {e}")
                return

        self.extract_archive()

    def show_about(self):
        about_text = (
            "Это программа для кастомизации спрайтов персонажей.\n\n"
            "Поддерживаемые форматы архивов: ZIP, TAR/TGZ, RAR, 7Z.\n\n"
            "При выборе нового архива приложение НЕ закрывается, а перезагружается.\n"
            "Маршрут (директория для распаковки и сохранения) задаётся через настройки BASE_DIR."
        )
        QMessageBox.information(self, "О программе", about_text)

    def show_accessory_context_menu(self, pos):
        item = self.accessory_list.itemAt(pos)
        if item:
            menu = QMenu()
            open_action = QAction("Открыть расположение файла", self)
            open_action.triggered.connect(lambda: self.open_file_location(item))
            menu.addAction(open_action)
            menu.exec_(self.accessory_list.mapToGlobal(pos))

    def open_file_location(self, item):
        category = self.category_list.currentItem().text() if self.category_list.currentItem() else ""
        accessory_name = item.text()
        file_path = self.accessory_file_paths.get((category, accessory_name))
        if file_path and os.path.exists(file_path):
            try:
                if sys.platform.startswith('win'):
                    os.startfile(os.path.dirname(file_path))
                elif sys.platform.startswith('darwin'):
                    subprocess.call(['open', os.path.dirname(file_path)])
                else:
                    subprocess.call(['xdg-open', os.path.dirname(file_path)])
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку: {e}")
        else:
            QMessageBox.warning(self, "Ошибка", "Файл не найден или не сохранен на диске.")

    def change_gender(self, gender):
        self.gender = gender
        self.load_sprites()
        self.current_skin_index = 0
        self.current_skin = self.skins[self.current_skin_index] if self.skins else None
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()
        self.record_history()

    def display_accessories(self, current, previous):
        if current is None:
            return
        category = current.text()
        self.accessory_list.clear()
        if category in self.accessories:
            for name, image in self.accessories[category]:
                item = QListWidgetItem(name)
                icon_pixmap = self.get_icon_from_sprite(image)
                item.setIcon(QIcon(icon_pixmap))
                item.setCheckState(Qt.Unchecked)
                self.accessory_list.addItem(item)
                if name in [name for name, _ in self.selected_accessories[category]]:
                    item.setCheckState(Qt.Checked)
        else:
            QMessageBox.warning(self, "Ошибка", f"Категория '{category}' не найдена.")

    def toggle_accessory(self, item):
        category = self.category_list.currentItem().text() if self.category_list.currentItem() else ""
        name = item.text()
        if category in self.accessories:
            accessory_image = None
            for acc_name, image in self.accessories[category]:
                if acc_name == name:
                    accessory_image = image
                    break
            if item.checkState() == Qt.Checked:
                self.selected_accessories[category].append((name, accessory_image))
            else:
                self.selected_accessories[category] = [
                    (acc_name, img) for acc_name, img in self.selected_accessories[category] if acc_name != name
                ]
            self.update_character_display()
            self.record_history()
        else:
            QMessageBox.warning(self, "Ошибка", f"Категория '{category}' не найдена.")

    def change_accessory_color(self):
        selected_items = self.accessory_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите аксессуар для изменения цвета.")
            return

        item = selected_items[0]
        accessory_name = item.text()
        category = self.category_list.currentItem().text() if self.category_list.currentItem() else ""
        color = QColorDialog.getColor()
        if not color.isValid():
            return

        original_image = None
        for name, image in self.accessories[category]:
            if name == accessory_name and not name.startswith("modified_"):
                original_image = image
                break
        if original_image is None:
            QMessageBox.warning(self, "Ошибка", "Оригинальное изображение не найдено.")
            return

        colored_image = self.tint_image(original_image, color)
        unique_id = str(uuid.uuid4())[:8]
        new_accessory_name = f"modified_{accessory_name}_{unique_id}.png"

        modified_category_path = os.path.join(self.modified_path, self.gender, category)
        os.makedirs(modified_category_path, exist_ok=True)
        save_path = os.path.join(modified_category_path, new_accessory_name)
        colored_image.save(save_path, "PNG")
        self.accessory_file_paths[(category, new_accessory_name)] = save_path
        self.accessories[category].append((new_accessory_name, colored_image))
        self.selected_accessories[category] = [
            (name, img) for name, img in self.selected_accessories[category] if name != accessory_name
        ]
        self.display_accessories(self.category_list.currentItem(), None)
        items = self.accessory_list.findItems(new_accessory_name, Qt.MatchExactly)
        if items:
            new_item = items[0]
            new_item.setCheckState(Qt.Checked)
            self.selected_accessories[category].append((new_accessory_name, colored_image))
        prev_items = self.accessory_list.findItems(accessory_name, Qt.MatchExactly)
        if prev_items:
            prev_item = prev_items[0]
            prev_item.setCheckState(Qt.Unchecked)
        self.colors[new_accessory_name] = color
        self.update_character_display()
        self.record_history()

    def tint_image(self, image, tint_color):
        image = image.convert("RGBA")
        tint_image = Image.new("RGBA", image.size, tint_color.getRgb())
        blended = ImageChops.multiply(image, tint_image)
        return blended

    def prev_skin(self):
        if self.skins:
            self.current_skin_index = (self.current_skin_index - 1) % len(self.skins)
            self.current_skin = self.skins[self.current_skin_index]
            self.update_character_display()
            self.record_history()

    def next_skin(self):
        if self.skins:
            self.current_skin_index = (self.current_skin_index + 1) % len(self.skins)
            self.current_skin = self.skins[self.current_skin_index]
            self.update_character_display()
            self.record_history()

    def update_character_display(self):
        if not self.current_skin:
            return

        final_image = self.current_skin.copy()
        for layer in self.layers_order:
            if layer == "Skin":
                continue
            for name, image in self.selected_accessories.get(layer, []):
                if layer == "Back Layers":
                    bg = Image.new("RGBA", final_image.size)
                    bg.paste(image, (0, 0), image)
                    bg.paste(final_image, (0, 0), final_image)
                    final_image = bg
                else:
                    final_image.paste(image, (0, 0), image)

        full_pixmap = self.pil2pixmap(final_image)
        self.character_pixmap = full_pixmap
        scaled_pixmap = full_pixmap.scaled(full_pixmap.size() * self.scale_factor, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.character_label.setPixmap(scaled_pixmap)
        self.final_image = final_image
        self.preview_animation_frames = self.auto_slice_sprite_sheet(final_image)
        self.preview_frame_index = 0

    def auto_slice_sprite_sheet(self, sprite_sheet):
        slices = []
        gray_image = sprite_sheet.convert("L")
        pixels = gray_image.load()
        width, height = gray_image.size
        y_slices = []
        in_sprite = False
        for y in range(height):
            is_transparent_row = all(pixels[x, y] == 0 for x in range(width))
            if not is_transparent_row and not in_sprite:
                start_y = y
                in_sprite = True
            elif is_transparent_row and in_sprite:
                end_y = y
                in_sprite = False
                y_slices.append((start_y, end_y))
        if in_sprite:
            y_slices.append((start_y, height))
        if y_slices:
            start_y, end_y = y_slices[0]
            animation_frames = []
            x_slices = []
            in_frame = False
            for x in range(width):
                is_transparent_column = all(pixels[x, yy] == 0 for yy in range(start_y, end_y))
                if not is_transparent_column and not in_frame:
                    start_x = x
                    in_frame = True
                elif is_transparent_column and in_frame:
                    end_x = x
                    in_frame = False
                    x_slices.append((start_x, end_x))
            if in_frame:
                x_slices.append((start_x, width))
            for start_x, end_x in x_slices:
                frame = sprite_sheet.crop((start_x, start_y, end_x, end_y))
                centered_frame = self.center_frame(frame)
                animation_frames.append(centered_frame)
            slices = animation_frames
        return slices

    def center_frame(self, frame):
        bbox = frame.getbbox()
        if bbox:
            frame = frame.crop(bbox)
        else:
            return frame
        max_width = frame.width
        max_height = frame.height
        canvas = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 0))
        x_offset = (max_width - frame.width) // 2
        y_offset = (max_height - frame.height) // 2
        canvas.paste(frame, (x_offset, y_offset), frame)
        return canvas

    def update_preview_animation(self):
        if not self.preview_animation_frames:
            return
        frame = self.preview_animation_frames[self.preview_frame_index % len(self.preview_animation_frames)]
        scale_factor = self.preview_scale_factor * 3
        frame = frame.resize((int(frame.width * scale_factor), int(frame.height * scale_factor)), Image.NEAREST)
        pixmap = self.pil2pixmap(frame)
        self.preview_label.setPixmap(pixmap)
        self.preview_frame_index = (self.preview_frame_index + 1) % len(self.preview_animation_frames)

    def get_icon_from_sprite(self, image, size=128):
        sprite_width, sprite_height = 64, 64
        single_sprite = image.crop((0, 0, sprite_width, sprite_height))
        single_sprite = single_sprite.resize((size, size), Image.LANCZOS)
        return self.pil2pixmap(single_sprite)

    @asyncSlot()
    async def save_combined_image(self):
        image_name, ok = await async_get_text(self, "Сохранить изображение", "Введите название изображения:")
        if ok and image_name:
            exports_dir = os.path.join(self.base_dir, "exports")
            os.makedirs(exports_dir, exist_ok=True)
            file_path = os.path.join(exports_dir, f"{image_name}.png")
            self.final_image.save(file_path, "PNG")

    def pil2pixmap(self, image):
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        qim = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qim)

    def save_settings(self):
        settings = QSettings('MyCompany', 'SpriteCustomizer')
        settings.setValue('splitterState', self.splitter.saveState())

    def load_settings(self):
        settings = QSettings('MyCompany', 'SpriteCustomizer')
        splitter_state = settings.value('splitterState')
        if splitter_state:
            self.splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        self.save_settings()
        self.auto_save_temp_backup()
        super().closeEvent(event)

    def show_animation_window(self):
        self.animation_window = AnimationWindow(self.final_image)
        self.animation_window.show()

    @asyncSlot()
    async def save_character_config(self):
        preset_name, ok = await async_get_text(self, "Сохранить пресет", "Введите название пресета:")
        if ok and preset_name:
            config = {
                'gender': self.gender,
                'current_skin_index': self.current_skin_index,
                'selected_accessories': {k: [name for name, _ in v] for k, v in self.selected_accessories.items()},
                'colors': {name: self.colors[name].name() for name in self.colors}
            }
            preset_dir = self.presets_path
            os.makedirs(preset_dir, exist_ok=True)
            preset_file = os.path.join(preset_dir, f"{preset_name}.json")
            with open(preset_file, 'w') as f:
                json.dump(config, f)
            icon_file = os.path.join(preset_dir, f"{preset_name}.png")
            if self.preview_animation_frames:
                self.preview_animation_frames[0].save(icon_file, "PNG")
            self.load_presets_list()
            self.record_history()

    def load_character_config(self, preset_file):
        with open(preset_file, 'r') as f:
            config = json.load(f)
        self.gender = config.get('gender', 'Man')
        self.gender_selector.setCurrentText(self.gender)
        self.load_sprites()
        self.current_skin_index = config.get('current_skin_index', 0)
        self.current_skin = self.skins[self.current_skin_index] if self.skins else None
        self.selected_accessories = {k: [] for k in self.accessories.keys()}
        for category, names in config.get('selected_accessories', {}).items():
            for name in names:
                for acc_name, image in self.accessories.get(category, []):
                    if acc_name == name:
                        self.selected_accessories[category].append((acc_name, image))
                        break
        self.colors = {}
        for name, color_name in config.get('colors', {}).items():
            self.colors[name] = QColor(color_name)
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()
        self.record_history()

    def clear_preset(self):
        self.selected_accessories = {k: [] for k in self.accessories.keys()}
        self.colors = {}
        self.current_skin_index = 0
        self.current_skin = self.skins[self.current_skin_index] if self.skins else None
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()
        self.record_history()

    def load_presets_list(self):
        for i in reversed(range(self.presets_layout.count())):
            widget = self.presets_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        preset_dir = self.presets_path
        if os.path.exists(preset_dir):
            for file_name in os.listdir(preset_dir):
                if file_name.endswith('.json'):
                    preset_name = os.path.splitext(file_name)[0]
                    icon_file = os.path.join(preset_dir, f"{preset_name}.png")
                    button = PresetButton(preset_name, icon_file, self)
                    button.clicked.connect(lambda checked, name=preset_name: self.load_preset_by_name(name))
                    self.presets_layout.addWidget(button)

    def load_preset_by_name(self, preset_name):
        preset_file = os.path.join(self.presets_path, f"{preset_name}.json")
        if os.path.exists(preset_file):
            self.load_character_config(preset_file)
        else:
            QMessageBox.warning(self, "Ошибка", f"Файл пресета '{preset_file}' не найден.")

    @asyncSlot()
    async def open_generation_window(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Генерация спрайтов")
        layout = QVBoxLayout(dialog)
        label = QLabel("Введите количество генераций:")
        layout.addWidget(label)
        spin_box = QSpinBox()
        spin_box.setRange(1, 10000)
        layout.addWidget(spin_box)
        progress_bar = QProgressBar()
        layout.addWidget(progress_bar)
        generate_button = QPushButton("Сгенерировать")
        layout.addWidget(generate_button)

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def on_generate():
            dialog.close()
            skins_copy = self.skins[:]
            accessories_copy = {}
            for cat, lst in self.accessories.items():
                accessories_copy[cat] = lst[:]
            gender = self.gender
            self.generation_thread = QThread()
            self.generation_worker = GenerationWorker(skins_copy, accessories_copy, gender, spin_box.value())
            self.generation_worker.moveToThread(self.generation_thread)
            self.generation_thread.started.connect(self.generation_worker.run)
            self.generation_worker.progress.connect(progress_bar.setValue)
            self.generation_worker.finished.connect(lambda: QMessageBox.information(self, "Генерация завершена", f"Сгенерировано {spin_box.value()} спрайтов."))
            self.generation_worker.finished.connect(lambda: future.set_result(True))
            self.generation_worker.finished.connect(self.generation_thread.quit)
            self.generation_worker.finished.connect(self.generation_worker.deleteLater)
            self.generation_thread.finished.connect(self.generation_thread.deleteLater)
            self.generation_thread.start()

        generate_button.clicked.connect(on_generate)
        dialog.show()
        await future

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if self.character_label.underMouse():
            self.zoom_label(self.character_label, delta)
        elif self.preview_label.underMouse():
            self.zoom_label(self.preview_label, delta)

    def zoom_label(self, label, delta):
        factor = 1.1 if delta > 0 else 0.9
        if label == self.character_label:
            self.scale_factor *= factor
            if self.character_pixmap:
                scaled_pixmap = self.character_pixmap.scaled(self.character_pixmap.size() * self.scale_factor, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
        elif label == self.preview_label:
            self.preview_scale_factor *= factor

    # ------------- Логика истории (undo/redo) -------------
    def record_history(self):
        state = {
            'gender': self.gender,
            'current_skin_index': self.current_skin_index,
            'selected_accessories': {k: [name for name, _ in v] for k, v in self.selected_accessories.items()},
            'colors': {name: self.colors[name].name() for name in self.colors}
        }
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index+1]
        self.history.append(state)
        self.history_index = len(self.history) - 1

    def restore_history_state(self, state):
        self.gender = state.get('gender', 'Man')
        self.gender_selector.setCurrentText(self.gender)
        self.load_sprites()
        self.current_skin_index = state.get('current_skin_index', 0)
        self.current_skin = self.skins[self.current_skin_index] if self.skins else None
        new_selected = {k: [] for k in self.accessories.keys()}
        for category, names in state.get('selected_accessories', {}).items():
            for name in names:
                for acc_name, image in self.accessories.get(category, []):
                    if acc_name == name:
                        new_selected[category].append((acc_name, image))
                        break
        self.selected_accessories = new_selected
        self.colors = {}
        for name, color_name in state.get('colors', {}).items():
            self.colors[name] = QColor(color_name)
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()

    def undo_history(self):
        if self.history_index > 0:
            self.history_index -= 1
            state = self.history[self.history_index]
            self.restore_history_state(state)
        else:
            QMessageBox.information(self, "Информация", "Нет предыдущих состояний.")

    def redo_history(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            state = self.history[self.history_index]
            self.restore_history_state(state)
        else:
            QMessageBox.information(self, "Информация", "Нет следующих состояний.")

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Z:
            self.undo_history()
        else:
            super().keyPressEvent(event)

    def show_history(self):
        history_window = HistoryWindow(self.history, self)
        history_window.exec_()

    def delete_preset(self, preset_name):
        reply = QMessageBox.question(self, "Удаление пресета", f"Удалить пресет '{preset_name}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            preset_file = os.path.join(self.presets_path, f"{preset_name}.json")
            icon_file = os.path.join(self.presets_path, f"{preset_name}.png")
            if os.path.exists(preset_file):
                os.remove(preset_file)
            if os.path.exists(icon_file):
                os.remove(icon_file)
            self.load_presets_list()

    def resave_preset(self, preset_name):
        config = {
            'gender': self.gender,
            'current_skin_index': self.current_skin_index,
            'selected_accessories': {k: [name for name, _ in v] for k, v in self.selected_accessories.items()},
            'colors': {name: self.colors[name].name() for name in self.colors}
        }
        preset_file = os.path.join(self.presets_path, f"{preset_name}.json")
        with open(preset_file, 'w') as f:
            json.dump(config, f)
        icon_file = os.path.join(self.presets_path, f"{preset_name}.png")
        if self.preview_animation_frames:
            self.preview_animation_frames[0].save(icon_file, "PNG")
        self.load_presets_list()
        self.record_history()

    def auto_save_temp_backup(self):
        timestamp = int(time.time())
        preset_name = f"tempbackup_{timestamp}"
        config = {
            'gender': self.gender,
            'current_skin_index': self.current_skin_index,
            'selected_accessories': {k: [name for name, _ in v] for k, v in self.selected_accessories.items()},
            'colors': {name: self.colors[name].name() for name in self.colors}
        }
        preset_file = os.path.join(self.presets_path, f"{preset_name}.json")
        with open(preset_file, 'w') as f:
            json.dump(config, f)
        icon_file = os.path.join(self.presets_path, f"{preset_name}.png")
        if self.preview_animation_frames:
            self.preview_animation_frames[0].save(icon_file, "PNG")

    def check_temp_backups(self):
        temp_files = []
        current_time = time.time()
        if not os.path.exists(self.presets_path):
            return
        for file_name in os.listdir(self.presets_path):
            if file_name.startswith("tempbackup_") and file_name.endswith(".json"):
                file_path = os.path.join(self.presets_path, file_name)
                file_mtime = os.path.getmtime(file_path)
                if current_time - file_mtime > 7 * 24 * 3600:
                    temp_files.append(file_path)
        if temp_files:
            notification = TempBackupNotificationWindow(temp_files, self)
            notification.exec_()

    def generate_random_character(self):
        if self.skins:
            self.current_skin_index = random.randrange(len(self.skins))
            self.current_skin = self.skins[self.current_skin_index]
        new_selected = {cat: [] for cat in self.accessories.keys()}
        for category, items in self.accessories.items():
            if items and random.random() < 0.5:
                new_selected[category].append(random.choice(items))
        self.selected_accessories = new_selected
        self.update_character_display()
        self.record_history()


# ---------------------- Окно анимации ---------------------------
class AnimationWindow(QWidget):
    def __init__(self, sprite_sheet):
        super().__init__()
        self.sprite_sheet = sprite_sheet
        self.init_ui()
        self.scale_factor = 3.0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(100)
        self.frame_index = 0
        self.current_animation_index = 0
        self.slices = self.auto_slice_sprite_sheet()

    def init_ui(self):
        self.setWindowTitle("Анимация персонажа")
        self.resize(400, 500)
        self.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px;
                text-align: center;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QLabel {
                font-size: 16px;
            }
        """)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.animation_label)
        self.animation_number_label = QLabel()
        self.animation_number_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.animation_number_label)
        controls_layout = QHBoxLayout()
        prev_animation_button = QPushButton("⟨ Предыдущая")
        prev_animation_button.clicked.connect(self.prev_animation)
        next_animation_button = QPushButton("Следующая ⟩")
        next_animation_button.clicked.connect(self.next_animation)
        controls_layout.addWidget(prev_animation_button)
        controls_layout.addWidget(next_animation_button)
        layout.addLayout(controls_layout)
        export_gif_button = QPushButton("Экспортировать анимацию в GIF")
        export_gif_button.clicked.connect(self.export_animation_to_gif)
        layout.addWidget(export_gif_button)

    def auto_slice_sprite_sheet(self):
        slices = []
        gray_image = self.sprite_sheet.convert("L")
        pixels = gray_image.load()
        width, height = gray_image.size
        y_slices = []
        in_sprite = False
        for y in range(height):
            is_transparent_row = all(pixels[x, y] == 0 for x in range(width))
            if not is_transparent_row and not in_sprite:
                start_y = y
                in_sprite = True
            elif is_transparent_row and in_sprite:
                end_y = y
                in_sprite = False
                y_slices.append((start_y, end_y))
        if in_sprite:
            y_slices.append((start_y, height))
        for start_y, end_y in y_slices:
            animation_frames = []
            x_slices = []
            in_frame = False
            for x in range(width):
                is_transparent_column = all(pixels[x, y] == 0 for y in range(start_y, end_y))
                if not is_transparent_column and not in_frame:
                    start_x = x
                    in_frame = True
                elif is_transparent_column and in_frame:
                    end_x = x
                    in_frame = False
                    x_slices.append((start_x, end_x))
            if in_frame:
                x_slices.append((start_x, width))
            for start_x, end_x in x_slices:
                frame = self.sprite_sheet.crop((start_x, start_y, end_x, end_y))
                animation_frames.append(frame)
            slices.append(animation_frames)
        return slices
    
    def update_frame(self):
        if not self.slices:
            return
        animation_frames = self.slices[self.current_animation_index]
        if not animation_frames:
            return
        frame = animation_frames[self.frame_index % len(animation_frames)]
        frame = self.center_frame(frame)
        scale_factor = self.scale_factor
        frame = frame.resize((int(frame.width * scale_factor), int(frame.height * scale_factor)), Image.NEAREST)
        pixmap = self.pil2pixmap(frame)
        self.animation_label.setPixmap(pixmap)
        self.animation_number_label.setText(f"Анимация {self.current_animation_index + 1} из {len(self.slices)}")
        self.frame_index = (self.frame_index + 1) % len(animation_frames)

    def center_frame(self, frame):
        bbox = frame.getbbox()
        if bbox:
            frame = frame.crop(bbox)
        else:
            return frame
        max_width = max(f.width for animation in self.slices for f in animation)
        max_height = max(f.height for animation in self.slices for f in animation)
        canvas = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 0))
        x_offset = (max_width - frame.width) // 2
        y_offset = (max_height - frame.height) // 2
        canvas.paste(frame, (x_offset, y_offset), frame)
        return canvas

    def prev_animation(self):
        self.current_animation_index = (self.current_animation_index - 1) % len(self.slices)
        self.frame_index = 0

    def next_animation(self):
        self.current_animation_index = (self.current_animation_index + 1) % len(self.slices)
        self.frame_index = 0

    def export_animation_to_gif(self):
        animation_frames = self.slices[self.current_animation_index]
        if not animation_frames:
            QMessageBox.warning(self, "Ошибка", "Нет кадров для экспорта.")
            return
        frames = []
        for frame in animation_frames:
            centered_frame = self.center_frame(frame)
            frames.append(centered_frame)
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить анимацию", "", "GIF Files (*.gif)", options=options)
        if file_name:
            if not file_name.endswith('.gif'):
                file_name += '.gif'
            frames[0].save(
                file_name,
                save_all=True,
                append_images=frames[1:],
                duration=100,
                loop=0,
                transparency=0,
                disposal=2
            )
            QMessageBox.information(self, "Экспорт завершен", f"Анимация сохранена в файл {file_name}")

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.scale_factor *= factor
        self.update_frame()

    def pil2pixmap(self, image):
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        qim = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qim)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Ищем архив с именем "Construct" с любым поддерживаемым расширением
    default_archive = find_default_archive()
    # Если архив не найден, передаем пустую строку
    window = SpriteCustomizer(default_archive)
    window.show()

    with loop:
        loop.run_forever()
