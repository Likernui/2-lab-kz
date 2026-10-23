"""Выбор пункта, его параметры и показ результата."""

from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from PIL import Image

import processing as edit
import statistics_image as stats


STEPS = [
    ("1", "1. Исходное изображение"), ("2", "2. Каналы и гистограммы"),
    ("3", "3. Окно 11 × 11"), ("4", "4. Однородность областей"),
    ("5a", "5а. Яркость"), ("5b", "5б. Контраст"), ("5c", "5в. Негатив"),
    ("5d", "5г. Обмен каналов"), ("5e", "5д. Отражение"),
    ("5f", "5е. Размытие"), ("5g", "5ж. Гамма-коррекция"),
    ("6", "6. Профиль яркости"), ("7", "7. Карта контрастности"),
    ("8", "8. Сохранение"),
]

# Подпись, минимум, максимум и начальное значение ползунка.
SLIDERS = {
    "5a": [("Общая", -100, 100, 0), ("R", -100, 100, 0),
           ("G", -100, 100, 0), ("B", -100, 100, 0)],
    "5b": [("Контраст", -100, 100, 0)],
    "5g": [("Гамма", 0.2, 3, 1)],
}
CHOICES = {
    "2": ["Оттенки серого", "Красный канал", "Зелёный канал", "Синий канал"],
    "5d": ["Красный ↔ Зелёный", "Красный ↔ Синий", "Зелёный ↔ Синий"],
    "5e": ["Слева направо", "Сверху вниз"],
    "7": ["Четыре соседа", "Восемь соседей", "Квадратное окно"],
}


class LabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KZ lab 2")
        self.geometry("1100x760")
        self.image = self.flipped = self.frame = None
        self.table, self.points, self.values = [], [], []
        self.saved = {}
        self.last_point = None

        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Открыть изображение", command=self.open_image).pack(side="left")
        self.step = ttk.Combobox(toolbar, values=[title for _, title in STEPS],
                                 state="readonly", width=35)
        self.step.current(0)
        self.step.pack(side="left", padx=15)
        self.step.bind("<<ComboboxSelected>>", self.select_step)
        self.controls = ttk.Frame(self, padding=10)
        self.controls.pack(fill="x")
        self.info = ttk.Label(self, wraplength=1050, justify="left")
        self.info.pack(anchor="w", padx=10)
        self.figure = Figure(figsize=(9, 5), layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("motion_notify_event", self.show_pixel)
        sample = Path(__file__).with_name("фото-улицы.png")
        if sample.is_file():
            self.load_image(sample)

    def open_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("PNG, BMP, TIFF", "*.png *.bmp *.tif *.tiff")]
        )
        if path:
            self.load_image(path)

    def load_image(self, path):
        try:
            with Image.open(path) as source:
                if source.mode != "RGB" or source.format not in ("PNG", "BMP", "TIFF"):
                    raise ValueError("Нужно RGB-изображение PNG, BMP или TIFF.")
                self.image = source.copy()
        except (OSError, ValueError) as error:
            messagebox.showerror("Ошибка загрузки", str(error))
            return
        self.table = stats.brightness_table(self.image)
        self.saved = {"Оригинал": self.image.copy()}
        self.points = []
        self.step.current(0)
        self.select_step()

    def select_step(self, _event=None):
        for child in self.controls.winfo_children():
            child.destroy()
        self.values, self.frame, self.last_point = [], None, None
        self.info.configure(text="")
        if self.image is None:
            return
        self.flipped = self.image.copy()
        code = STEPS[self.step.current()][0]
        choices = list(self.saved) if code == "8" else CHOICES.get(code)
        if choices:
            box = ttk.Combobox(self.controls, values=choices, state="readonly", width=35)
            box.current(0)
            box.pack(side="left", padx=5)
            self.values.append(box)
        sliders = SLIDERS.get(code, [])
        if code == "6":
            sliders = [("Строка y", 0, self.image.height - 1, self.image.height // 2)]
        if code == "7":
            sliders = [("Размер окна", 3, 15, 5)]
        for title, low, high, value in sliders:
            slider = tk.Scale(self.controls, label=title, from_=low, to=high,
                              resolution=0.1 if code == "5g" else 2 if code == "7" else 1,
                              orient="horizontal", length=170)
            slider.set(value)
            slider.pack(side="left", padx=5)
            self.values.append(slider)
        if code == "5c":
            for color in ("R", "G", "B"):
                value = tk.BooleanVar(value=True)
                ttk.Checkbutton(self.controls, text=color, variable=value).pack(side="left", padx=10)
                self.values.append(value)
        if code == "7":
            self.values[0].bind("<<ComboboxSelected>>", self.update_window_size)
            self.update_window_size()
        text = "Применить"
        if code == "8":
            text = "Сохранить выбранное"
        elif code == "3":
            text = "Запомнить окно"
        if code not in ("1", "4"):
            ttk.Button(self.controls, text=text, command=self.run).pack(side="left", padx=10)
        if code == "8":
            self.values[0].bind("<<ComboboxSelected>>", self.preview_saved)
        self.show_images([self.image], ["Исходное изображение"])
        if code == "3":
            self.frame = Rectangle((0, 0), 13, 13, fill=False, color="gold", visible=False)
            self.figure.axes[0].add_patch(self.frame)
            self.info.configure(text="Двигайте курсор по изображению. Окно 11 × 11; рамка 13 × 13.")
        elif code == "4":
            self.show_comparison()

    def show_images(self, pictures, titles):
        self.figure.clear()
        for index, picture in enumerate(pictures):
            axis = self.figure.add_subplot(1, len(pictures), index + 1)
            axis.imshow(picture, cmap="gray", vmin=0, vmax=255)
            axis.set_title(titles[index])
            axis.axis("off")
        self.canvas.draw_idle()

    def update_window_size(self, _event=None):
        self.values[1].configure(state="normal" if self.values[0].current() == 2 else "disabled")

    def run(self):
        code = STEPS[self.step.current()][0]
        values = [widget.get() for widget in self.values]
        name = self.step.get()
        result = None

        if code == "2":
            pictures, histograms = stats.channels_and_histograms(self.image)
            index = self.values[0].current()
            for title, picture in zip(CHOICES["2"], pictures):
                self.saved[title] = picture.copy()
            self.figure.clear()
            axis = self.figure.add_subplot(1, 2, 1)
            axis.imshow(pictures[index], cmap="gray", vmin=0, vmax=255)
            axis.set_title(values[0])
            axis.axis("off")
            axis = self.figure.add_subplot(1, 2, 2)
            color = ["gray", "red", "green", "blue"][index]
            axis.bar(range(256), histograms[index], color=color)
            axis.set(xlabel="Значение 0–255", ylabel="Количество пикселей", title="Гистограмма")
        elif code == "3":
            if self.last_point is not None:
                self.points.append(self.last_point)
                self.info.configure(text="Окно запомнено. Сравнение — в пункте 4.")
        elif code == "5a":
            result = edit.change_brightness(self.image, values[0], values[1], values[2], values[3])
        elif code == "5b":
            result = edit.change_contrast(self.image, values[0])
        elif code == "5c":
            result = edit.make_negative(self.image, values[0], values[1], values[2])
        elif code == "5d":
            mode = ["red_green", "red_blue", "green_blue"][self.values[0].current()]
            result = edit.swap_channels(self.image, mode)
        elif code == "5e":
            mode = "horizontal" if self.values[0].current() == 0 else "vertical"
            self.flipped = edit.flip_image(self.flipped, mode)
            result = self.flipped
        elif code == "5f":
            four = edit.blur_image(self.image, "four")
            eight = edit.blur_image(self.image, "eight")
            self.saved["Размытие: 4 соседа"], self.saved["Размытие: 8 соседей"] = four, eight
            self.show_images(
                [self.image, four, eight], ["Оригинал", "4-связность", "8-связность"]
            )
        elif code == "5g":
            result = edit.gamma_correction(self.image, values[0])
        elif code == "6":
            row = int(values[0])
            self.figure.clear()
            axis = self.figure.add_subplot(2, 1, 1)
            axis.imshow(self.image)
            axis.axhline(row, color="gold")
            axis.set_title(f"Строка y = {row}")
            axis.axis("off")
            axis = self.figure.add_subplot(2, 1, 2)
            axis.plot(stats.brightness_profile(self.table, row), color="black")
            axis.set(xlabel="Координата x", ylabel="Яркость", ylim=(0, 255))
            buffer = BytesIO()
            self.figure.savefig(buffer, format="png")
            buffer.seek(0)
            with Image.open(buffer) as picture:
                self.saved[f"Профиль, строка {row}"] = picture.copy()
        elif code == "7":
            mode = ["four", "eight", "window"][self.values[0].current()]
            result = stats.contrast_map(self.table, mode, int(values[1]))
            name = "Карта: " + values[0]
            if mode == "window":
                name += f" {int(values[1])}x{int(values[1])}"
        elif code == "8":
            path = filedialog.asksaveasfilename(
                initialfile=values[0] + ".png", defaultextension=".png"
            )
            if path:
                try:
                    self.saved[values[0]].save(path, format="PNG")
                except OSError as error:
                    messagebox.showerror("Ошибка сохранения", str(error))
        if result is not None:
            self.saved[name] = result.copy()
            self.show_images([self.image, result], ["Оригинал", name])
        self.canvas.draw_idle()

    def preview_saved(self, _event=None):
        name = self.values[0].get()
        self.show_images([self.saved[name]], [name])

    def show_pixel(self, event):
        if STEPS[self.step.current()][0] != "3" or self.frame is None:
            return
        if event.inaxes is None or event.xdata is None or event.ydata is None:
            self.frame.set_visible(False)
            self.canvas.draw_idle()
            return
        x, y = int(event.xdata + 0.5), int(event.ydata + 0.5)
        if not (0 <= x < self.image.width and 0 <= y < self.image.height):
            return
        self.frame.set_xy((x - 6.5, y - 6.5))
        self.frame.set_visible(True)
        r, g, b = self.image.getpixel((x, y))
        text = f"x={x}, y={y} | RGB=({r}, {g}, {b}) | Интенсивность={(r + g + b) / 3:.2f}\n"
        result = stats.window_statistics(self.table, x, y)
        self.last_point = None
        if result is None:
            text += "Окно выходит за край изображения."
        else:
            mean, variance, deviation = result
            text += (
                f"Среднее={mean:.2f} | Дисперсия={variance:.2f} | "
                f"Стандартное отклонение={deviation:.2f}"
            )
            self.last_point = (x, y, mean, deviation)
        self.info.configure(text=text)
        self.canvas.draw_idle()

    def show_comparison(self):
        self.figure.clear()
        axis = self.figure.add_subplot()
        axis.axis("off")
        if self.points:
            rows = [
                [x, y, f"{mean:.2f}", f"{deviation:.2f}"]
                for x, y, mean, deviation in self.points
            ]
            axis.table(
                cellText=rows, colLabels=["x", "y", "Среднее", "Станд. отклонение"],
                loc="center",
            )
        self.info.configure(text=(
            "Однородность: близкие яркости, узкая гистограмма, малая дисперсия.\n"
            "Неоднородность: большой разброс яркостей. "
            "Среднее показывает светлоту, а не однородность.\n"
            "Добавьте примеры кнопкой «Запомнить окно» в пункте 3."
        ))
        self.canvas.draw_idle()
