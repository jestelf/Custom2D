import sys
import os
import zipfile
import random
import itertools
from PIL import Image, ImageQt, ImageEnhance, ImageOps, ImageChops
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog, QListWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QScrollArea, QComboBox, QSplitter, QColorDialog, QInputDialog,
    QScrollArea, QSizePolicy, QFrame, QToolButton, QMenu, QAction, QMessageBox, QProgressBar, QDialog, QSpinBox
)
from PyQt5.QtGui import QPixmap, QIcon, QImage, QFont, QColor, QWheelEvent
from PyQt5.QtCore import Qt, QSettings, QSize, QTimer, QThread, pyqtSignal
import json
import uuid  # Для генерации уникальных имен файлов


class SpriteCustomizer(QWidget):
    def __init__(self, zip_path):
        super().__init__()
        self.zip_path = zip_path
        self.extract_path = "extracted_sprites"
        self.modified_path = "modified_accessories"
        self.presets_path = "presets"  # Директория для хранения пресетов
        self.gender = "Man"  # Начальный пол персонажа

        # Распаковываем zip-файл
        self.extract_zip()

        # Инициализация переменных
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
        self.colors = {}  # Словарь для хранения цветов аксессуаров

        # Загрузка спрайтов
        self.load_sprites()

        # Создание интерфейса
        self.init_ui()

        # Обновление отображения персонажа
        self.update_character_display()

    def extract_zip(self):
        """Извлекает ZIP-файл в директорию 'extracted_sprites'."""
        if not os.path.exists(self.extract_path):
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.extract_path)

        # Создаем директории, если они не существуют
        os.makedirs(self.modified_path, exist_ok=True)
        os.makedirs(self.presets_path, exist_ok=True)

    def load_sprites(self):
        """Загружает все спрайты и сортирует их по категориям, включая модифицированные варианты."""
        base_path = os.path.join(self.extract_path, "Construct", self.gender)
        self.accessories = {layer: [] for layer in self.layers_order if layer != "Skin"}
        self.selected_accessories = {key: [] for key in self.accessories.keys()}
        self.skins = []
        self.current_skin = None
        self.colors = {}

        # Загрузка спрайтов из директорий
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

        # Загрузка модифицированных аксессуаров
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
                        else:
                            self.accessories[category] = [(file, image)]

    def init_ui(self):
        """Создает интерфейс приложения."""
        self.setWindowTitle("Sprite Customizer")
        self.resize(1200, 800)

        # Применяем стиль
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

        # Инициализация accessory_list заранее
        self.accessory_list = QListWidget()
        self.accessory_list.itemClicked.connect(self.toggle_accessory)
        self.accessory_list.setIconSize(QSize(128, 128))
        self.accessory_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Основной макет с разделителем
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Левая панель с категориями аксессуаров и превью
        left_panel = QVBoxLayout()

        # Выбор пола
        self.gender_selector = QComboBox()
        self.gender_selector.addItems(["Man", "Woman"])
        self.gender_selector.currentTextChanged.connect(self.change_gender)
        left_panel.addWidget(self.gender_selector)

        # Список категорий аксессуаров
        self.category_list = QListWidget()
        for category in self.accessories.keys():
            item = QListWidgetItem(category)
            self.category_list.addItem(item)
        self.category_list.currentItemChanged.connect(self.display_accessories)
        left_panel.addWidget(self.category_list)

        # Устанавливаем первый элемент как текущий, если он есть
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0)

        # Превью персонажа
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_panel.addWidget(self.preview_label)

        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        self.splitter.addWidget(left_widget)

        # Центральная панель с персонажем и контролами
        character_layout = QVBoxLayout()
        self.character_label = QLabel()
        self.character_label.setAlignment(Qt.AlignCenter)
        self.character_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        character_layout.addWidget(self.character_label)

        # Кнопки переключения скинов
        skin_controls = QHBoxLayout()
        prev_skin_button = QPushButton("Предыдущий скин")
        prev_skin_button.clicked.connect(self.prev_skin)
        next_skin_button = QPushButton("Следующий скин")
        next_skin_button.clicked.connect(self.next_skin)
        skin_controls.addWidget(prev_skin_button)
        skin_controls.addWidget(next_skin_button)
        character_layout.addLayout(skin_controls)

        # Кнопка сохранения
        save_button = QPushButton("Сохранить изображение")
        save_button.clicked.connect(self.save_combined_image)
        character_layout.addWidget(save_button)

        # Кнопка для открытия окна анимации
        animation_button = QPushButton("Показать анимацию")
        animation_button.clicked.connect(self.show_animation_window)
        character_layout.addWidget(animation_button)

        # Кнопка сохранения пресета
        save_config_button = QPushButton("Сохранить пресет")
        save_config_button.clicked.connect(self.save_character_config)
        character_layout.addWidget(save_config_button)

        # Кнопка очистки пресета
        clear_button = QPushButton("Очистить пресет")
        clear_button.clicked.connect(self.clear_preset)
        character_layout.addWidget(clear_button)

        # Кнопка генерации спрайтов
        generate_button = QPushButton("Генерация спрайтов")
        generate_button.clicked.connect(self.open_generation_window)
        character_layout.addWidget(generate_button)

        # Горизонтальный список пресетов
        self.presets_scroll_area = QScrollArea()
        self.presets_scroll_area.setWidgetResizable(True)
        self.presets_widget = QWidget()
        self.presets_layout = QHBoxLayout(self.presets_widget)
        self.presets_layout.setAlignment(Qt.AlignLeft)
        self.presets_scroll_area.setWidget(self.presets_widget)
        character_layout.addWidget(QLabel("Сохраненные пресеты:"))
        character_layout.addWidget(self.presets_scroll_area)

        # Загрузка существующих пресетов
        self.load_presets_list()

        character_widget = QWidget()
        character_widget.setLayout(character_layout)
        self.splitter.addWidget(character_widget)

        # Правая панель с аксессуарами
        accessory_layout = QVBoxLayout()
        accessory_layout.addWidget(self.accessory_list)

        # Кнопка изменения цвета аксессуара
        color_button = QPushButton("Изменить цвет аксессуара")
        color_button.clicked.connect(self.change_accessory_color)
        accessory_layout.addWidget(color_button)

        accessory_widget = QWidget()
        accessory_widget.setLayout(accessory_layout)
        self.splitter.addWidget(accessory_widget)

        # Таймер для анимации превью
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview_animation)
        self.preview_frame_index = 0
        self.preview_animation_frames = []
        self.preview_timer.start(100)  # Обновляем каждые 100 мс

        # Загружаем настройки разделителя
        self.load_settings()

        # Инициализируем масштабирование
        self.scale_factor = 1.0
        self.preview_scale_factor = 1.0
        self.character_pixmap = None

    def change_gender(self, gender):
        """Меняет пол персонажа и перезагружает спрайты."""
        self.gender = gender
        self.load_sprites()
        self.current_skin_index = 0
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()

    def display_accessories(self, current, previous):
        """Отображает список аксессуаров выбранной категории."""
        if current is None:
            return
        category = current.text()
        self.accessory_list.clear()
        if category in self.accessories:
            for name, image in self.accessories[category]:
                item = QListWidgetItem(name)
                icon_pixmap = self.get_icon_from_sprite(image)
                icon = QIcon(icon_pixmap)
                item.setIcon(icon)
                item.setCheckState(Qt.Unchecked)
                self.accessory_list.addItem(item)

                # Отмечаем уже выбранные аксессуары
                if name in [name for name, _ in self.selected_accessories[category]]:
                    item.setCheckState(Qt.Checked)
        else:
            QMessageBox.warning(self, "Ошибка", f"Категория '{category}' не найдена.")

    def toggle_accessory(self, item):
        """Добавляет или убирает аксессуар при клике."""
        category = self.category_list.currentItem().text()
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
        else:
            QMessageBox.warning(self, "Ошибка", f"Категория '{category}' не найдена.")

    def change_accessory_color(self):
        """Изменяет цвет выбранного аксессуара, создавая новый вариант и отключая предыдущий."""
        selected_items = self.accessory_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Внимание", "Пожалуйста, выберите аксессуар для изменения цвета.")
            return

        item = selected_items[0]
        accessory_name = item.text()
        category = self.category_list.currentItem().text()

        # Выбираем цвет
        color = QColorDialog.getColor()
        if not color.isValid():
            return

        # Применяем цвет к аксессуару
        original_image = None
        for name, image in self.accessories[category]:
            if name == accessory_name and not name.startswith("modified_"):
                original_image = image
                break

        if original_image is None:
            QMessageBox.warning(self, "Ошибка", "Оригинальное изображение не найдено.")
            return

        # Создаем версию изображения с наложением оттенка
        colored_image = self.tint_image(original_image, color)

        # Генерируем уникальное имя для нового аксессуара
        unique_id = str(uuid.uuid4())[:8]
        new_accessory_name = f"modified_{accessory_name}_{unique_id}.png"

        # Сохраняем изображение на диск
        modified_category_path = os.path.join(self.modified_path, self.gender, category)
        os.makedirs(modified_category_path, exist_ok=True)
        save_path = os.path.join(modified_category_path, new_accessory_name)
        colored_image.save(save_path, "PNG")

        # Добавляем новый аксессуар в список
        self.accessories[category].append((new_accessory_name, colored_image))

        # Отключаем предыдущий аксессуар
        self.selected_accessories[category] = [
            (name, img) for name, img in self.selected_accessories[category] if name != accessory_name
        ]

        # Обновляем UI
        self.display_accessories(self.category_list.currentItem(), None)

        # Отмечаем новый аксессуар как выбранный
        items = self.accessory_list.findItems(new_accessory_name, Qt.MatchExactly)
        if items:
            new_item = items[0]
            new_item.setCheckState(Qt.Checked)
            self.selected_accessories[category].append((new_accessory_name, colored_image))

        # Снимаем отметку с предыдущего аксессуара
        prev_items = self.accessory_list.findItems(accessory_name, Qt.MatchExactly)
        if prev_items:
            prev_item = prev_items[0]
            prev_item.setCheckState(Qt.Unchecked)

        # Сохраняем цвет в словаре
        self.colors[new_accessory_name] = color

        self.update_character_display()

    def tint_image(self, image, tint_color):
        """Накладывает оттенок на изображение, сохраняя текстурные детали."""
        image = image.convert("RGBA")
        tint_image = Image.new("RGBA", image.size, tint_color.getRgb())
        blended = ImageChops.multiply(image, tint_image)
        return blended

    def prev_skin(self):
        """Переключает на предыдущий скин."""
        if self.skins:
            self.current_skin_index = (self.current_skin_index - 1) % len(self.skins)
            self.current_skin = self.skins[self.current_skin_index]
            self.update_character_display()

    def next_skin(self):
        """Переключает на следующий скин."""
        if self.skins:
            self.current_skin_index = (self.current_skin_index + 1) % len(self.skins)
            self.current_skin = self.skins[self.current_skin_index]
            self.update_character_display()

    def update_character_display(self):
        """Обновляет изображение персонажа с примененными аксессуарами."""
        if not self.current_skin:
            return

        # Создаем копию базового скина
        final_image = self.current_skin.copy()

        # Накладываем аксессуары в правильном порядке
        for layer in self.layers_order:
            if layer == "Skin":
                continue
            for name, image in self.selected_accessories.get(layer, []):
                if layer == "Back Layers":
                    # Накладываем за персонажем
                    background = Image.new("RGBA", final_image.size)
                    background.paste(image, (0, 0), image)
                    background.paste(final_image, (0, 0), final_image)
                    final_image = background
                else:
                    final_image.paste(image, (0, 0), image)

        # Отображаем полный спрайт-лист
        full_pixmap = self.pil2pixmap(final_image)
        self.character_pixmap = full_pixmap  # Сохраняем исходный пиксмап
        scaled_pixmap = full_pixmap.scaled(full_pixmap.size() * self.scale_factor, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.character_label.setPixmap(scaled_pixmap)

        # Сохраняем финальное изображение для анимации и пресетов
        self.final_image = final_image

        # Нарезаем спрайт-лист для анимации превью
        self.preview_animation_frames = self.auto_slice_sprite_sheet(final_image)
        self.preview_frame_index = 0  # Сбрасываем индекс кадра

    def auto_slice_sprite_sheet(self, sprite_sheet):
        """Автоматически нарезает спрайт-лист на отдельные кадры."""
        slices = []

        # Преобразуем изображение в оттенки серого и получаем данные пикселей
        gray_image = sprite_sheet.convert("L")
        pixels = gray_image.load()
        width, height = gray_image.size

        # Список для хранения границ кадров
        frames = []

        # Поиск горизонтальных разделителей между анимациями по оси Y
        y_slices = []
        in_sprite = False
        for y in range(height):
            is_transparent_row = all(pixels[x, y] == 0 for x in range(width))
            if not is_transparent_row and not in_sprite:
                # Начало новой анимации
                start_y = y
                in_sprite = True
            elif is_transparent_row and in_sprite:
                # Конец анимации
                end_y = y
                in_sprite = False
                y_slices.append((start_y, end_y))
        if in_sprite:
            y_slices.append((start_y, height))

        # Используем только первую анимацию
        if y_slices:
            start_y, end_y = y_slices[0]
            animation_frames = []

            # Поиск вертикальных разделителей между кадрами по оси X
            x_slices = []
            in_frame = False
            for x in range(width):
                is_transparent_column = all(pixels[x, y] == 0 for y in range(start_y, end_y))
                if not is_transparent_column and not in_frame:
                    # Начало нового кадра
                    start_x = x
                    in_frame = True
                elif is_transparent_column and in_frame:
                    # Конец кадра
                    end_x = x
                    in_frame = False
                    x_slices.append((start_x, end_x))
            if in_frame:
                x_slices.append((start_x, width))

            # Вырезаем кадры анимации
            for start_x, end_x in x_slices:
                frame = sprite_sheet.crop((start_x, start_y, end_x, end_y))
                centered_frame = self.center_frame(frame)
                animation_frames.append(centered_frame)

            slices = animation_frames

        return slices

    def center_frame(self, frame):
        """Центрирует персонажа в кадре для уменьшения дрожания."""
        bbox = frame.getbbox()
        if bbox:
            frame = frame.crop(bbox)
        else:
            return frame

        # Создаем холст для центрирования
        max_width = max(f.width for f in [frame])
        max_height = max(f.height for f in [frame])
        canvas = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 0))
        x_offset = (max_width - frame.width) // 2
        y_offset = (max_height - frame.height) // 2
        canvas.paste(frame, (x_offset, y_offset), frame)
        return canvas

    def update_preview_animation(self):
        """Обновляет превью с текущим кадром анимации."""
        if not self.preview_animation_frames:
            return

        frame = self.preview_animation_frames[self.preview_frame_index % len(self.preview_animation_frames)]

        # Масштабируем для отображения
        scale_factor = self.preview_scale_factor * 3
        frame = frame.resize((int(frame.width * scale_factor), int(frame.height * scale_factor)), Image.NEAREST)

        # Отображаем кадр
        pixmap = self.pil2pixmap(frame)
        self.preview_label.setPixmap(pixmap)

        # Переходим к следующему кадру
        self.preview_frame_index = (self.preview_frame_index + 1) % len(self.preview_animation_frames)

    def get_icon_from_sprite(self, image, size=128):
        """Создает иконку из одного спрайта."""
        sprite_width, sprite_height = 64, 64  # Размеры спрайта
        single_sprite = image.crop((0, 0, sprite_width, sprite_height))
        single_sprite = single_sprite.resize((size, size), Image.LANCZOS)
        return self.pil2pixmap(single_sprite)

    def save_combined_image(self):
        """Сохраняет текущее изображение персонажа в папку 'exports'."""
        image_name, ok = QInputDialog.getText(self, "Сохранить изображение", "Введите название изображения:")
        if ok and image_name:
            exports_dir = os.path.join(os.getcwd(), "exports")
            os.makedirs(exports_dir, exist_ok=True)
            file_path = os.path.join(exports_dir, f"{image_name}.png")
            self.final_image.save(file_path, "PNG")

    def pil2pixmap(self, image):
        """Конвертирует изображение PIL в QPixmap."""
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        qim = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qim)

    def save_settings(self):
        """Сохраняет настройки приложения."""
        settings = QSettings('MyCompany', 'SpriteCustomizer')
        settings.setValue('splitterState', self.splitter.saveState())

    def load_settings(self):
        """Загружает настройки приложения."""
        settings = QSettings('MyCompany', 'SpriteCustomizer')
        splitter_state = settings.value('splitterState')
        if splitter_state:
            self.splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        """Событие закрытия приложения."""
        self.save_settings()
        super().closeEvent(event)

    def show_animation_window(self):
        """Открывает окно с анимацией."""
        self.animation_window = AnimationWindow(self.final_image)
        self.animation_window.show()

    def save_character_config(self):
        """Сохраняет текущие настройки персонажа в пресет."""
        preset_name, ok = QInputDialog.getText(self, "Сохранить пресет", "Введите название пресета:")
        if ok and preset_name:
            # Сохранение конфигурации
            config = {
                'gender': self.gender,
                'current_skin_index': self.current_skin_index,
                'selected_accessories': {k: [name for name, _ in v] for k, v in self.selected_accessories.items()},
                'colors': {name: self.colors[name].name() for name in self.colors}
            }
            preset_dir = os.path.join(self.presets_path)
            os.makedirs(preset_dir, exist_ok=True)
            preset_file = os.path.join(preset_dir, f"{preset_name}.json")
            with open(preset_file, 'w') as f:
                json.dump(config, f)

            # Сохраняем превью изображения как иконку
            icon_file = os.path.join(preset_dir, f"{preset_name}.png")
            self.preview_animation_frames[0].save(icon_file, "PNG")

            # Обновляем список пресетов
            self.load_presets_list()

    def load_character_config(self, preset_file):
        """Загружает настройки персонажа из пресета."""
        with open(preset_file, 'r') as f:
            config = json.load(f)
        self.gender = config.get('gender', 'Man')
        self.gender_selector.setCurrentText(self.gender)
        self.load_sprites()
        self.current_skin_index = config.get('current_skin_index', 0)
        self.current_skin = self.skins[self.current_skin_index]

        # Загружаем выбранные аксессуары
        self.selected_accessories = {k: [] for k in self.accessories.keys()}
        for category, names in config.get('selected_accessories', {}).items():
            for name in names:
                for acc_name, image in self.accessories.get(category, []):
                    if acc_name == name:
                        self.selected_accessories[category].append((acc_name, image))
                        break

        # Загружаем цвета аксессуаров
        self.colors = {}
        for name, color_name in config.get('colors', {}).items():
            self.colors[name] = QColor(color_name)

        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()

    def clear_preset(self):
        """Очищает текущий пресет."""
        self.selected_accessories = {k: [] for k in self.accessories.keys()}
        self.colors = {}
        self.current_skin_index = 0
        self.current_skin = self.skins[self.current_skin_index]
        self.update_character_display()
        if self.category_list.currentItem():
            self.display_accessories(self.category_list.currentItem(), None)
        else:
            self.accessory_list.clear()

    def load_presets_list(self):
        """Загружает список сохраненных пресетов."""
        # Очищаем текущий список виджетов
        for i in reversed(range(self.presets_layout.count())):
            widget = self.presets_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        preset_dir = os.path.join(self.presets_path)
        if os.path.exists(preset_dir):
            for file_name in os.listdir(preset_dir):
                if file_name.endswith('.json'):
                    preset_name = os.path.splitext(file_name)[0]
                    button = QPushButton()
                    button.setFixedSize(64, 64)
                    button.setToolTip(preset_name)
                    icon_file = os.path.join(preset_dir, f"{preset_name}.png")
                    if os.path.exists(icon_file):
                        icon = QIcon(icon_file)
                        button.setIcon(icon)
                        button.setIconSize(QSize(64, 64))
                    else:
                        button.setText(preset_name)
                    button.clicked.connect(lambda checked, name=preset_name: self.load_preset_by_name(name))
                    self.presets_layout.addWidget(button)

    def load_preset_by_name(self, preset_name):
        """Загружает пресет по его имени."""
        preset_file = os.path.join(self.presets_path, f"{preset_name}.json")
        if os.path.exists(preset_file):
            self.load_character_config(preset_file)
        else:
            QMessageBox.warning(self, "Ошибка", f"Файл пресета '{preset_file}' не найден.")

    def open_generation_window(self):
        """Открывает окно для ввода количества генераций и запуска генерации."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Генерация спрайтов")
        layout = QVBoxLayout(dialog)

        label = QLabel("Введите количество генераций:")
        layout.addWidget(label)

        spin_box = QSpinBox()
        spin_box.setRange(1, 10000)
        layout.addWidget(spin_box)

        generate_button = QPushButton("Сгенерировать")
        generate_button.clicked.connect(lambda: self.generate_random_sprite_sheets(spin_box.value(), dialog))
        layout.addWidget(generate_button)

        dialog.exec_()

    def generate_random_sprite_sheets(self, number, dialog=None):
        """Генерирует указанное количество случайных спрайт-листов."""
        if dialog:
            dialog.close()

        datasets_dir = os.path.join(os.getcwd(), "datasets")
        os.makedirs(datasets_dir, exist_ok=True)

        for i in range(number):
            # Случайно выбираем пол
            self.gender = random.choice(["Man", "Woman"])
            self.gender_selector.setCurrentText(self.gender)
            self.load_sprites()

            # Случайно выбираем скин
            self.current_skin_index = random.randint(0, len(self.skins) - 1)
            self.current_skin = self.skins[self.current_skin_index]

            # Случайно выбираем аксессуары
            self.selected_accessories = {k: [] for k in self.accessories.keys()}

            for category in self.accessories.keys():
                accessories_in_category = self.accessories[category]

                if category == "Clothing":
                    upper_clothes = [acc for acc in accessories_in_category if 'upper' in acc[0].lower()]
                    lower_clothes = [acc for acc in accessories_in_category if 'lower' in acc[0].lower()]
                    other_clothes = [acc for acc in accessories_in_category if acc not in upper_clothes + lower_clothes]

                    if upper_clothes and random.random() < 0.9:
                        accessory = random.choice(upper_clothes)
                        self.selected_accessories[category].append(accessory)

                    if lower_clothes and random.random() < 0.9:
                        accessory = random.choice(lower_clothes)
                        self.selected_accessories[category].append(accessory)

                    for accessory in other_clothes:
                        if random.random() < 0.5:
                            self.selected_accessories[category].append(accessory)
                else:
                    if accessories_in_category and random.random() < 0.5:
                        accessory = random.choice(accessories_in_category)
                        self.selected_accessories[category].append(accessory)

            # Возможность случайного изменения цвета аксессуаров
            for category, accessories in self.selected_accessories.items():
                for idx, (name, image) in enumerate(accessories):
                    if random.choice([True, False]):
                        # Случайно меняем цвет
                        tint = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                        tinted_image = self.tint_image(image, tint)
                        unique_id = str(uuid.uuid4())[:8]
                        new_name = f"auto_modified_{name}_{unique_id}.png"
                        self.accessories[category].append((new_name, tinted_image))
                        self.selected_accessories[category][idx] = (new_name, tinted_image)

            self.update_character_display()

            # Сохраняем финальное изображение
            file_path = os.path.join(datasets_dir, f"random_sprite_{i+1}_{self.gender}.png")
            self.final_image.save(file_path, "PNG")

        QMessageBox.information(self, "Генерация завершена", f"Сгенерировано {number} спрайтов.")

    def wheelEvent(self, event):
        """Обрабатывает событие прокрутки колеса мыши для масштабирования."""
        delta = event.angleDelta().y()
        if self.character_label.underMouse():
            self.zoom_label(self.character_label, delta)
        elif self.preview_label.underMouse():
            self.zoom_label(self.preview_label, delta)

    def zoom_label(self, label, delta):
        """Масштабирует изображение в QLabel."""
        factor = 1.1 if delta > 0 else 0.9
        if label == self.character_label:
            self.scale_factor *= factor
            if self.character_pixmap:
                scaled_pixmap = self.character_pixmap.scaled(self.character_pixmap.size() * self.scale_factor, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
        elif label == self.preview_label:
            self.preview_scale_factor *= factor
            # Масштабирование обновится в следующем кадре анимации

    # Удаляем метод generate_all_combinations и связанные с ним классы
    # ...

class AnimationWindow(QWidget):
    def __init__(self, sprite_sheet):
        super().__init__()
        self.sprite_sheet = sprite_sheet

        # Создаем интерфейс
        self.init_ui()

        # Добавляем возможность масштабирования
        self.scale_factor = 3.0  # Начальный масштаб

        # Запускаем таймер для обновления кадров
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(100)  # Обновляем каждые 100 мс

        # Инициализируем параметры анимации
        self.frame_index = 0
        self.current_animation_index = 0

        # Автоматически нарезаем спрайт-лист
        self.slices = self.auto_slice_sprite_sheet()

    def init_ui(self):
        self.setWindowTitle("Анимация персонажа")
        self.resize(400, 500)

        # Применяем стиль
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

        # Метка для отображения анимации
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.animation_label)

        # Метка для отображения номера анимации
        self.animation_number_label = QLabel()
        self.animation_number_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.animation_number_label)

        # Кнопки переключения анимаций
        controls_layout = QHBoxLayout()
        prev_animation_button = QPushButton("⟨ Предыдущая")
        prev_animation_button.clicked.connect(self.prev_animation)
        next_animation_button = QPushButton("Следующая ⟩")
        next_animation_button.clicked.connect(self.next_animation)
        controls_layout.addWidget(prev_animation_button)
        controls_layout.addWidget(next_animation_button)
        layout.addLayout(controls_layout)

        # Кнопка экспорта анимации в GIF
        export_gif_button = QPushButton("Экспортировать анимацию в GIF")
        export_gif_button.clicked.connect(self.export_animation_to_gif)
        layout.addWidget(export_gif_button)

    def auto_slice_sprite_sheet(self):
        """Автоматически нарезает спрайт-лист на отдельные кадры."""
        slices = []

        # Преобразуем изображение в оттенки серого и получаем данные пикселей
        gray_image = self.sprite_sheet.convert("L")
        pixels = gray_image.load()
        width, height = gray_image.size

        # Список для хранения границ кадров
        frames = []

        # Поиск горизонтальных разделителей между анимациями по оси Y
        y_slices = []
        in_sprite = False
        for y in range(height):
            is_transparent_row = all(pixels[x, y] == 0 for x in range(width))
            if not is_transparent_row and not in_sprite:
                # Начало новой анимации
                start_y = y
                in_sprite = True
            elif is_transparent_row and in_sprite:
                # Конец анимации
                end_y = y
                in_sprite = False
                y_slices.append((start_y, end_y))
        if in_sprite:
            y_slices.append((start_y, height))

        # Для каждой анимации по оси Y
        for start_y, end_y in y_slices:
            animation_frames = []

            # Поиск вертикальных разделителей между кадрами по оси X
            x_slices = []
            in_frame = False
            for x in range(width):
                is_transparent_column = all(pixels[x, y] == 0 for y in range(start_y, end_y))
                if not is_transparent_column and not in_frame:
                    # Начало нового кадра
                    start_x = x
                    in_frame = True
                elif is_transparent_column and in_frame:
                    # Конец кадра
                    end_x = x
                    in_frame = False
                    x_slices.append((start_x, end_x))
            if in_frame:
                x_slices.append((start_x, width))

            # Вырезаем кадры анимации
            for start_x, end_x in x_slices:
                frame = self.sprite_sheet.crop((start_x, start_y, end_x, end_y))
                animation_frames.append(frame)

            slices.append(animation_frames)

        return slices

    def update_frame(self):
        """Обновляет текущий кадр анимации."""
        if not self.slices:
            return

        animation_frames = self.slices[self.current_animation_index]
        if not animation_frames:
            return

        frame = animation_frames[self.frame_index % len(animation_frames)]

        # Центрируем персонажа в кадре
        frame = self.center_frame(frame)

        # Масштабируем для отображения
        scale_factor = self.scale_factor
        frame = frame.resize((int(frame.width * scale_factor), int(frame.height * scale_factor)), Image.NEAREST)

        # Отображаем кадр
        pixmap = self.pil2pixmap(frame)
        self.animation_label.setPixmap(pixmap)

        # Обновляем метку номера анимации
        self.animation_number_label.setText(f"Анимация {self.current_animation_index + 1} из {len(self.slices)}")

        # Переходим к следующему кадру
        self.frame_index = (self.frame_index + 1) % len(animation_frames)

    def center_frame(self, frame):
        """Центрирует персонажа в кадре для уменьшения дрожания."""
        bbox = frame.getbbox()
        if bbox:
            frame = frame.crop(bbox)
        else:
            return frame

        # Создаем холст для центрирования
        max_width = max(f.width for animation in self.slices for f in animation)
        max_height = max(f.height for animation in self.slices for f in animation)
        canvas = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 0))
        x_offset = (max_width - frame.width) // 2
        y_offset = (max_height - frame.height) // 2
        canvas.paste(frame, (x_offset, y_offset), frame)
        return canvas

    def prev_animation(self):
        """Переключает на предыдущую анимацию."""
        self.current_animation_index = (self.current_animation_index - 1) % len(self.slices)
        self.frame_index = 0

    def next_animation(self):
        """Переключает на следующую анимацию."""
        self.current_animation_index = (self.current_animation_index + 1) % len(self.slices)
        self.frame_index = 0

    def export_animation_to_gif(self):
        """Экспортирует текущую анимацию в GIF-файл."""
        animation_frames = self.slices[self.current_animation_index]
        if not animation_frames:
            QMessageBox.warning(self, "Ошибка", "Нет кадров для экспорта.")
            return

        # Центрируем и собираем кадры
        frames = []
        for frame in animation_frames:
            centered_frame = self.center_frame(frame)
            frames.append(centered_frame)

        # Запрашиваем путь для сохранения файла
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, "Сохранить анимацию", "", "GIF Files (*.gif)", options=options)
        if file_name:
            if not file_name.endswith('.gif'):
                file_name += '.gif'

            # Сохраняем анимацию в GIF
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
        """Обрабатывает событие прокрутки колеса мыши для масштабирования."""
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 0.9
        self.scale_factor *= factor
        self.update_frame()

    def pil2pixmap(self, image):
        """Конвертирует изображение PIL в QPixmap."""
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        qim = QImage(data, image.width, image.height, QImage.Format_RGBA8888)
        return QPixmap.fromImage(qim)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    zip_path = "Construct.zip"  # Укажите путь к вашему ZIP-файлу
    window = SpriteCustomizer(zip_path)
    window.show()
    sys.exit(app.exec_())
