# -- coding: utf-8 --

"""
Aplikacja desktopowa do wizualizacji danych eksperymentalnych 2D
Wersja: 9.2 (Poprawka widoczności paska narzędzi, zmiana nazwy przycisku)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, TclError, colorchooser
from typing import Dict, Any, List
import pandas as pd
import numpy as np
import os
import logging
from scipy.fft import fft, fftfreq
from scipy.signal import savgol_filter
from scipy.ndimage import median_filter, gaussian_filter1d
import copy

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends._backend_tk import NavigationToolbar2Tk

class CustomNavigationToolbar(NavigationToolbar2Tk):
    toolitems = tuple(t for t in NavigationToolbar2Tk.toolitems if
                      t[0] in ('Home', 'Pan', 'Zoom', 'Subplots', 'Save'))

class HistoryManager:
    # ... (cała klasa HistoryManager bez zmian) ...
    def __init__(self, app_instance):
        self.app = app_instance
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
    def save_state(self, operation_name: str):
        try:
            state = copy.deepcopy(self.app.plotted_data)
            self.undo_stack.append(state)
            self.redo_stack.clear()
            if len(self.undo_stack) > 30: self.undo_stack.pop(0)
            self.app.update_edit_menu_state()
            logging.info(f"Zapisano stan: {operation_name}")
        except Exception as e: logging.error(f"Błąd podczas zapisywania stanu: {e}")
    def undo(self):
        if not self.undo_stack: return
        try:
            current_state = copy.deepcopy(self.app.plotted_data)
            self.redo_stack.append(current_state)
            previous_state = self.undo_stack.pop()
            self.app.plotted_data = previous_state
            self.app.redraw_all_plots()
            self.app._update_combobox()
            self.app.update_edit_menu_state()
            logging.info("Operacja cofnięta.")
        except Exception as e: logging.error(f"Błąd podczas cofania: {e}")
    def redo(self):
        if not self.redo_stack: return
        try:
            current_state = copy.deepcopy(self.app.plotted_data)
            self.undo_stack.append(current_state)
            next_state = self.redo_stack.pop()
            self.app.plotted_data = next_state
            self.app.redraw_all_plots()
            self.app._update_combobox()
            self.app.update_edit_menu_state()
            logging.info("Operacja ponowiona.")
        except Exception as e: logging.error(f"Błąd podczas ponawiania: {e}")

class DataVisualizerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._setup_logging()
        self.root.title("THz Data Visualizer v9.2")
        self.root.geometry("1450x900")

        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        self.history = HistoryManager(self)
        self.smoothing_method_var = tk.StringVar(value="Moving Average")
        self.smoothing_window_var = tk.IntVar(value=5)
        self.high_contrast_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        self.plotted_data: Dict[str, Dict[str, Any]] = {}
        self.visibility_vars: Dict[str, tk.BooleanVar] = {}
        self._is_updating_ui = False
        self.excel_filepath = None
        self.grid_visible_var = tk.BooleanVar(value=True)
        self.grid_color_var = tk.StringVar(value="#cccccc")
        self.grid_style_display_var = tk.StringVar(value="Kreskowana")
        self.grid_style_internal_var = tk.StringVar(value="--")
        self.grid_width_var = tk.DoubleVar(value=0.6)
        self.markers: List[Any] = []; self.marker_text = None
        self.data_canvas = None; self.chart_options_canvas = None; self.stats_canvas = None

        self._create_menu()
        self._create_main_layout()
        self._create_plot_area()
        self._create_control_panel_layout()
        self._initialize_plot()
        self._connect_events()
        
        logging.info("Aplikacja uruchomiona pomyślnie.")

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Plik", menu=file_menu)
        file_menu.add_command(label="Wczytaj plik(i) .txt", command=self.load_data_and_plot)
        file_menu.add_command(label="Wczytaj arkusze z .xlsx", command=self._load_excel_file)
        file_menu.add_separator()
        file_menu.add_command(label="Wyczyść wszystko", command=self.clear_plot)
        file_menu.add_separator()
        file_menu.add_command(label="Wyjdź", command=self.root.quit)
        self.edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edycja", menu=self.edit_menu)
        self.edit_menu.add_command(label="Cofnij (Ctrl+Z)", command=self.history.undo, state=tk.DISABLED)
        self.edit_menu.add_command(label="Ponów (Ctrl+Y)", command=self.history.redo, state=tk.DISABLED)

    def _create_plot_area(self):
        self.fig = Figure(figsize=(8, 6), dpi=100, constrained_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.crosshair_v = self.ax.axvline(0, color='gray', lw=0.8, linestyle='--', visible=False)
        self.crosshair_h = self.ax.axhline(0, color='gray', lw=0.8, linestyle='--', visible=False)
        
        # ZMIANA: Modyfikacja sposobu pakowania dla lepszej responsywności
        toolbar_frame = ttk.Frame(self.plot_frame)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False) # Pasek zawsze na dole, bez rozszerzania w pionie
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True) # Kanwa wypełnia resztę miejsca
        
        self.toolbar = CustomNavigationToolbar(self.canvas, toolbar_frame)
        self.toolbar.update()
        
    # ... (reszta metod bez zmian aż do metod modyfikujących dane) ...
    def _create_control_panel_layout(self):
        notebook = ttk.Notebook(self.control_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        data_tab = ttk.Frame(notebook); notebook.add(data_tab, text="Źródła Danych")
        data_container = ttk.LabelFrame(data_tab, text="Wczytane Zbiory Danych", padding=10)
        data_container.pack(side=tk.TOP, fill='both', expand=True, padx=10, pady=(10, 5))
        self.data_canvas = tk.Canvas(data_container, highlightthickness=0)
        data_scrollbar = ttk.Scrollbar(data_container, orient="vertical", command=self.data_canvas.yview)
        self.data_canvas.configure(yscrollcommand=data_scrollbar.set); data_scrollbar.pack(side=tk.RIGHT, fill='y')
        self.data_canvas.pack(side=tk.LEFT, fill='both', expand=True); self.scrollable_data_frame = ttk.Frame(self.data_canvas)
        self.scrollable_data_frame_id = self.data_canvas.create_window((0, 0), window=self.scrollable_data_frame, anchor="nw")
        self.scrollable_data_frame.bind("<Configure>", lambda e: self._update_scroll_region(self.data_canvas))
        self.data_canvas.bind('<Configure>', lambda e: self.data_canvas and self.data_canvas.itemconfig(self.scrollable_data_frame_id, width=e.width))
        select_all_frame = ttk.Frame(self.scrollable_data_frame); select_all_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(select_all_frame, text="Zaznacz wszystkie", command=self._select_all_sheets).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(select_all_frame, text="Odznacz wszystkie", command=self._deselect_all_sheets).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
        self.checkbox_container = ttk.Frame(self.scrollable_data_frame); self.checkbox_container.pack(fill='x')
        self.initial_data_label = ttk.Label(self.checkbox_container, text="Nie wczytano żadnych danych.", wraplength=350); self.initial_data_label.pack(padx=5, pady=5)
        import_frame = ttk.LabelFrame(data_tab, text="Importuj / Zarządzaj", padding=10)
        import_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(import_frame, text="Wczytaj dane z pliku .txt", command=self.load_data_and_plot).pack(fill=tk.X, pady=(0, 2))
        ttk.Button(import_frame, text="Wczytaj arkusze z pliku .xlsx", command=self._load_excel_file).pack(fill=tk.X, pady=(2, 2))
        ttk.Button(import_frame, text="Wyczyść wszystko", command=self.clear_plot).pack(fill=tk.X, pady=(2, 5))
        chart_options_tab = ttk.Frame(notebook); notebook.add(chart_options_tab, text="Opcje Wykresu")
        self.chart_options_canvas = tk.Canvas(chart_options_tab, highlightthickness=0)
        chart_opt_scrollbar = ttk.Scrollbar(chart_options_tab, orient="vertical", command=self.chart_options_canvas.yview)
        self.chart_options_canvas.configure(yscrollcommand=chart_opt_scrollbar.set); chart_opt_scrollbar.pack(side="right", fill="y"); self.chart_options_canvas.pack(side="left", fill="both", expand=True)
        chart_content_frame = ttk.Frame(self.chart_options_canvas); chart_content_frame_id = self.chart_options_canvas.create_window((0, 0), window=chart_content_frame, anchor="nw")
        chart_content_frame.bind("<Configure>", lambda e: self._update_scroll_region(self.chart_options_canvas)); self.chart_options_canvas.bind('<Configure>', lambda e: self.chart_options_canvas and self.chart_options_canvas.itemconfig(chart_content_frame_id, width=e.width))
        common_signal_frame_1 = ttk.LabelFrame(chart_content_frame, text="Aktywny Sygnał (Referencja)", padding=10); common_signal_frame_1.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        self.active_signal_var = tk.StringVar(); self.signal_selector = ttk.Combobox(common_signal_frame_1, textvariable=self.active_signal_var, state='readonly')
        self.signal_selector.pack(fill=tk.X, pady=(0, 10)); self.signal_selector.bind("<<ComboboxSelected>>", self._on_signal_selected)
        edit_frame = ttk.LabelFrame(chart_content_frame, text="Edycja Wyglądu Sygnału", padding=10); edit_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        ttk.Label(edit_frame, text="Współczynnik skalowania:").pack(fill=tk.X, pady=(5, 0)); self.scale_entry_var = tk.StringVar(value="1.0"); scale_entry = ttk.Entry(edit_frame, textvariable=self.scale_entry_var)
        scale_entry.pack(fill=tk.X, pady=(0, 5)); scale_entry.bind("<Return>", self._update_from_entry); scale_entry.bind("<FocusOut>", self._update_from_entry)
        self.log_scale_slider = ttk.Scale(edit_frame, from_=-3.0, to=3.0, orient=tk.HORIZONTAL, command=self._update_from_slider); self.log_scale_slider.set(0.0); self.log_scale_slider.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(edit_frame, text="Nowa nazwa:").pack(anchor='w'); self.label_edit_var = tk.StringVar(); ttk.Entry(edit_frame, textvariable=self.label_edit_var).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(edit_frame, text="Zmień etykietę", command=self._update_label).pack(fill=tk.X, pady=(0,5)); ttk.Button(edit_frame, text="Zmień kolor", command=self._change_active_plot_color).pack(fill=tk.X)
        plot_options_frame = ttk.LabelFrame(chart_content_frame, text="Opcje Wykresu", padding=10); plot_options_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        self.legend_visible_var = tk.BooleanVar(value=True); ttk.Checkbutton(plot_options_frame, text="Pokaż legendę", variable=self.legend_visible_var, command=self._toggle_legend_visibility).pack(anchor='w', pady=(0, 5))
        self.fit_view_button = ttk.Button(plot_options_frame, text="Dopasuj widok do danych", command=self.fit_view_to_data); self.fit_view_button.pack(fill=tk.X, pady=(0, 5))
        self.normalize_button = ttk.Button(plot_options_frame, text="Normalizuj Amplitudy", command=self.normalize_amplitudes); self.normalize_button.pack(fill=tk.X)
        grid_frame = ttk.LabelFrame(chart_content_frame, text="Ustawienia Siatki (Linii Pomocniczych)", padding=10); grid_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        ttk.Checkbutton(grid_frame, text="Pokaż siatkę", variable=self.grid_visible_var, command=self._update_grid).pack(anchor='w')
        color_frame = ttk.Frame(grid_frame); color_frame.pack(fill=tk.X, pady=5); ttk.Button(color_frame, text="Zmień kolor", command=self._choose_grid_color).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.grid_color_preview = tk.Frame(color_frame, width=24, height=24, relief='sunken', borderwidth=1); self.grid_color_preview.pack(side=tk.LEFT); self.grid_color_preview.config(bg=self.grid_color_var.get())
        style_frame = ttk.Frame(grid_frame); style_frame.pack(fill=tk.X, pady=5); ttk.Label(style_frame, text="Styl linii:").pack(side=tk.LEFT)
        style_map = {"Ciągła": "-", "Kreskowana": "--", "Kropkowana": ":", "Kreska-kropka": "-."}; self.grid_style_selector = ttk.Combobox(style_frame, textvariable=self.grid_style_display_var, values=list(style_map.keys()), state='readonly')
        self.grid_style_selector.bind("<<ComboboxSelected>>", lambda e: self._on_grid_style_selected(style_map)); self.grid_style_selector.pack(side=tk.RIGHT, expand=True, fill=tk.X)
        width_frame = ttk.Frame(grid_frame); width_frame.pack(fill=tk.X, pady=5); ttk.Label(width_frame, text="Grubość (0.1-5.0):").pack(side=tk.LEFT)
        ttk.Spinbox(width_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.grid_width_var, command=self._update_grid, wrap=True).pack(side=tk.RIGHT, expand=True, fill=tk.X)
        stats_tab = ttk.Frame(notebook); notebook.add(stats_tab, text="Statystyka i Przetwarzanie")
        self.stats_canvas = tk.Canvas(stats_tab, highlightthickness=0)
        stats_scrollbar = ttk.Scrollbar(stats_tab, orient="vertical", command=self.stats_canvas.yview)
        self.stats_canvas.configure(yscrollcommand=stats_scrollbar.set); stats_scrollbar.pack(side="right", fill="y"); self.stats_canvas.pack(side="left", fill="both", expand=True)
        stats_content_frame = ttk.Frame(self.stats_canvas); stats_content_frame_id = self.stats_canvas.create_window((0, 0), window=stats_content_frame, anchor="nw")
        stats_content_frame.bind("<Configure>", lambda e: self._update_scroll_region(self.stats_canvas)); self.stats_canvas.bind('<Configure>', lambda e: self.stats_canvas and self.stats_canvas.itemconfig(stats_content_frame_id, width=e.width))
        common_signal_frame_2 = ttk.LabelFrame(stats_content_frame, text="Aktywny Sygnał (Referencja)", padding=10); common_signal_frame_2.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        self.signal_selector_2 = ttk.Combobox(common_signal_frame_2, textvariable=self.active_signal_var, state='readonly'); self.signal_selector_2.pack(fill=tk.X, pady=(0, 10))
        self.signal_selector_2.bind("<<ComboboxSelected>>", self._on_signal_selected)
        stats_frame = ttk.LabelFrame(stats_content_frame, text="Statystyki Aktywnego Sygnału", padding=10); stats_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        self.stats_labels: Dict[str, tk.StringVar] = {"Max": tk.StringVar(value="--"), "Min": tk.StringVar(value="--"), "Pozycja Piku": tk.StringVar(value="--"), "Średnia": tk.StringVar(value="--")}
        for name, var in self.stats_labels.items(): f = ttk.Frame(stats_frame); f.pack(fill=tk.X); ttk.Label(f, text=f"{name}:").pack(side=tk.LEFT, padx=(0, 5)); ttk.Label(f, textvariable=var, anchor='e').pack(side=tk.RIGHT)
        processing_frame = ttk.LabelFrame(stats_content_frame, text="Przetwarzanie Sygnału", padding=10); processing_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        smoothing_options_frame = ttk.Frame(processing_frame); smoothing_options_frame.pack(fill=tk.X, pady=5)
        ttk.Label(smoothing_options_frame, text="Metoda:").pack(side=tk.LEFT, padx=(0,5)); smoothing_methods = ["Moving Average", "Savitzky-Golay", "Median Filter", "Gaussian Filter"]
        self.smoothing_combo = ttk.Combobox(smoothing_options_frame, textvariable=self.smoothing_method_var, values=smoothing_methods, state='readonly'); self.smoothing_combo.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Label(smoothing_options_frame, text="Okno/Siła:").pack(side=tk.LEFT, padx=(10,5))
        vcmd = (self.root.register(self._validate_odd_int), '%P'); self.smoothing_spinbox = ttk.Spinbox(smoothing_options_frame, from_=1, to=101, increment=2, textvariable=self.smoothing_window_var, wrap=True, width=5, validate='key', validatecommand=vcmd)
        self.smoothing_spinbox.pack(side=tk.LEFT)
        smoothing_apply_frame = ttk.Frame(processing_frame); smoothing_apply_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(smoothing_apply_frame, text="Zastosuj do aktywnego", command=self._apply_smoothing_to_active).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(smoothing_apply_frame, text="Zastosuj do wszystkich", command=self._apply_smoothing_to_all).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
        smoothing_buttons_frame = ttk.Frame(processing_frame); smoothing_buttons_frame.pack(fill=tk.X, pady=(5,0))
        ttk.Button(smoothing_buttons_frame, text="Resetuj wygładzenie", command=self._reset_smoothing).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(smoothing_buttons_frame, text="Zestaw z oryginałem", command=self._compare_all_with_original).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0)) # ZMIANA: Nazwa przycisku
        ttk.Separator(processing_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        self.show_fft_var = tk.BooleanVar(value=False); ttk.Checkbutton(processing_frame, text="Pokaż Transformację Fouriera (FFT)", variable=self.show_fft_var, command=self.toggle_fft_view).pack(anchor='w')
        ttk.Button(processing_frame, text="Pokaż Histogram Amplitud", command=self._show_histogram).pack(fill=tk.X, pady=(10,0))

    # ... (cała reszta kodu jest identyczna jak w poprzedniej wersji i nie wymaga zmian)
    
    def _initialize_plot(self):
        is_fft = self.show_fft_var.get()
        x_label = "Częstotliwość (THz)" if is_fft else "Czas (ps)"; y_label = "Amplituda FFT (a.u.)" if is_fft else "Sygnał (a.u.)"
        self.ax.set_xlabel(x_label); self.ax.set_ylabel(y_label)
        self.ax.grid(self.grid_visible_var.get(), color=self.grid_color_var.get(), linestyle=self.grid_style_internal_var.get(), linewidth=self.grid_width_var.get())
        self.canvas.draw_idle()
    def _setup_logging(self):
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'); log_file = 'app_log.txt'
        file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8'); file_handler.setFormatter(log_formatter); file_handler.setLevel(logging.INFO)
        logger = logging.getLogger(); logger.setLevel(logging.INFO)
        if logger.hasHandlers(): logger.handlers.clear()
        logger.addHandler(file_handler)
    def _create_main_layout(self):
        main_paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED); main_paned_window.pack(fill=tk.BOTH, expand=True)
        self.plot_frame = ttk.Frame(main_paned_window, width=1020); main_paned_window.add(self.plot_frame, stretch="always")
        self.control_frame = ttk.Frame(main_paned_window, width=420); main_paned_window.add(self.control_frame, stretch="never"); self.control_frame.pack_propagate(False)
        self.status_bar = ttk.Label(self.root, text=" Najechanie na wykres pokaże współrzędne", relief=tk.SUNKEN, anchor='w'); self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    def update_edit_menu_state(self):
        undo_state = tk.NORMAL if self.history.undo_stack else tk.DISABLED
        redo_state = tk.NORMAL if self.history.redo_stack else tk.DISABLED
        if hasattr(self, 'edit_menu'):
            self.edit_menu.entryconfig("Cofnij (Ctrl+Z)", state=undo_state)
            self.edit_menu.entryconfig("Ponów (Ctrl+Y)", state=redo_state)
    def _update_scroll_region(self, canvas):
        scroll_bbox = canvas.bbox("all"); canvas.configure(scrollregion=scroll_bbox)
        content_height = scroll_bbox[3] - scroll_bbox[1] if scroll_bbox else 0
        if content_height <= canvas.winfo_height(): canvas.yview_moveto(0)
    def _lighten_color(self, hex_color: str) -> str:
        try:
            r, g, b = [int(hex_color[i:i+2], 16) for i in (1, 3, 5)]; factor = 0.6
            light_r, light_g, light_b = int(r*(1-factor)+255*factor), int(g*(1-factor)+255*factor), int(b*(1-factor)+255*factor)
            return f'#{light_r:02x}{light_g:02x}{light_b:02x}'
        except Exception: return "#cccccc"
    def redraw_all_plots(self):
        xlim, ylim = None, None; view_preserved = False
        if self.ax.has_data(): xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim(); view_preserved = True
        self.ax.cla(); self.crosshair_v = self.ax.axvline(0, color='gray', lw=0.8, linestyle='--', visible=False); self.crosshair_h = self.ax.axhline(0, color='gray', lw=0.8, linestyle='--', visible=False); self._clear_markers()
        is_fft = self.show_fft_var.get(); sorted_plot_ids = sorted(self.plotted_data.keys())
        for plot_id in sorted_plot_ids:
            data = self.plotted_data[plot_id]
            if not data.get('visible', False): continue
            linestyle = '--' if data.get('is_comparison', False) else '-'
            color = self._lighten_color(data['original_color']) if data.get('is_comparison', False) else data['color']
            style_dict = {'color': color, 'linestyle': linestyle}
            df, scale = data['df'], data['scale_factor']; label_text = f"{data['label']} (x{scale:.3f})"
            x_data_original = df.iloc[:, 0].to_numpy(dtype=float); y_data_original = df.iloc[:, 1].to_numpy(dtype=float) * scale
            y_data_to_plot = self._apply_smoothing(y_data_original, plot_id)
            line_data_x, line_data_y = x_data_original, y_data_to_plot
            if is_fft:
                n_points = len(x_data_original)
                if n_points > 1:
                    time_step = float(np.mean(np.diff(x_data_original))) * 1e-12; yf, xf = fft(y_data_to_plot), fftfreq(n_points, time_step)
                    positive_freq_indices = np.where(xf >= 0)[0]; xf_positive = xf[positive_freq_indices] / 1e12
                    yf_positive_amp = 2.0/n_points * np.abs(np.asarray(yf[positive_freq_indices])); line_data_x, line_data_y = xf_positive, yf_positive_amp
            line, = self.ax.plot(line_data_x, line_data_y, label=label_text, **style_dict); data['line'] = line
        self._initialize_plot()
        if self.legend_visible_var.get() and self.ax.has_data(): self.ax.legend()
        if view_preserved and not is_fft and xlim is not None and ylim is not None: self.ax.set_xlim(xlim); self.ax.set_ylim(ylim)
        elif is_fft:
            if self.ax.has_data(): self.ax.set_xlim(left=0); self.ax.autoscale(enable=True, axis='y')
        self.canvas.draw(); self._update_statistics_display()
    def _apply_smoothing(self, y_data, plot_id):
        data = self.plotted_data.get(plot_id)
        if not data or not data.get('smoothed', False) or len(y_data) < 3: return y_data
        try:
            window = data.get('smoothing_window', self.smoothing_window_var.get())
            method = data.get('smoothing_method', self.smoothing_method_var.get())
            if method == "Gaussian Filter": sigma = max(1, window); return gaussian_filter1d(y_data, sigma=sigma)
            if window < 3: return y_data
            if method == "Moving Average": return pd.Series(y_data).rolling(window=window, center=True, min_periods=1).mean().to_numpy()
            elif method == "Savitzky-Golay": poly_order = min(3, window - 1 if window > 3 else 1); return savgol_filter(y_data, window, poly_order)
            elif method == "Median Filter": return median_filter(y_data, size=window)
        except Exception: return y_data
        return y_data
    def _add_or_update_data(self, plot_id: str, df: pd.DataFrame, label: str):
        if plot_id in self.plotted_data: return False
        load_index = len([pid for pid in self.plotted_data if not self.plotted_data[pid].get('is_comparison', False)])
        initial_color = self.high_contrast_colors[load_index % len(self.high_contrast_colors)]
        self.plotted_data[plot_id] = {'df': df, 'line': None, 'scale_factor': 1.0, 'label': label, 'visible': True, 'color': initial_color, 'original_color': initial_color, 'smoothed': False}
        var = tk.BooleanVar(value=True); self.visibility_vars[plot_id] = var
        if self.initial_data_label.winfo_exists(): self.initial_data_label.pack_forget()
        cb = ttk.Checkbutton(self.checkbox_container, text=label, variable=var, command=lambda pid=plot_id: self._on_visibility_changed(pid)); cb.pack(anchor='w', fill='x', padx=5)
        return True
    def _on_visibility_changed(self, plot_id: str):
        if plot_id in self.plotted_data and plot_id in self.visibility_vars: 
            is_visible = self.visibility_vars[plot_id].get(); logging.info(f"Zmiana widoczności dla '{self.plotted_data[plot_id]['label']}' na {is_visible}")
            self.plotted_data[plot_id]['visible'] = is_visible; self._update_combobox(); self.redraw_all_plots()
    def _apply_smoothing_to_active(self):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id: messagebox.showwarning("Brak danych", "Proszę wybrać aktywny sygnał do wygładzenia."); return
        self.history.save_state("Wygładź aktywny")
        logging.info(f"Stosowanie wygładzania do: {self.plotted_data[plot_id]['label']}")
        data = self.plotted_data[plot_id]; data['smoothed'] = True
        data['smoothing_window'] = self.smoothing_window_var.get(); data['smoothing_method'] = self.smoothing_method_var.get()
        self.redraw_all_plots()
    def _apply_smoothing_to_all(self):
        self.history.save_state("Wygładź wszystkie")
        logging.info("Stosowanie wygładzania do wszystkich widocznych sygnałów.")
        any_smoothed = False
        for plot_id, data in self.plotted_data.items():
            if data.get('visible', False) and not data.get('is_comparison', False):
                data['smoothed'] = True; data['smoothing_window'] = self.smoothing_window_var.get(); data['smoothing_method'] = self.smoothing_method_var.get()
                any_smoothed = True
        if any_smoothed: self.redraw_all_plots()
        else: messagebox.showinfo("Informacja", "Brak widocznych sygnałów do wygładzenia.")
    def _reset_smoothing(self):
        self.history.save_state("Resetuj wygładzenie")
        logging.info("Resetowanie wygładzania dla wszystkich sygnałów.")
        comparison_keys = [pid for pid, data in self.plotted_data.items() if data.get('is_comparison', False)]
        for key in comparison_keys: del self.plotted_data[key]
        for data in self.plotted_data.values(): data['smoothed'] = False
        self.redraw_all_plots(); self._update_combobox()
    def _compare_all_with_original(self):
        self.history.save_state("Zestaw wszystkie z oryginałem")
        logging.info("Tworzenie porównań dla wszystkich wygładzonych i widocznych sygnałów.")
        any_compared = False
        for plot_id, data in list(self.plotted_data.items()):
            if data.get('visible', False) and data.get('smoothed', False) and not data.get('is_comparison', False):
                comparison_id = f"{plot_id}_comparison"
                if comparison_id not in self.plotted_data:
                    comparison_data = copy.deepcopy(data); comparison_data['label'] = f"{data['label']} (oryg.)"
                    comparison_data['smoothed'] = False; comparison_data['is_comparison'] = True; comparison_data['visible'] = True
                    self.plotted_data[comparison_id] = comparison_data; any_compared = True
        if any_compared: self.redraw_all_plots()
        else: messagebox.showinfo("Informacja", "Brak widocznych i wygładzonych sygnałów do porównania.")
    def clear_plot(self):
        self.history.save_state("Wyczyść wszystko")
        logging.info("Czyszczenie wykresu i wszystkich danych.")
        self.ax.cla(); self.plotted_data.clear(); self.visibility_vars.clear(); self._clear_markers()
        self.crosshair_v = self.ax.axvline(0, color='gray', lw=0.8, linestyle='--', visible=False); self.crosshair_h = self.ax.axhline(0, color='gray', lw=0.8, linestyle='--', visible=False)
        self._clear_data_ui()
        self.signal_selector['values'] = []; self.signal_selector_2['values'] = []
        self._on_signal_selected(); self.legend_visible_var.set(True)
        if self.show_fft_var.get(): self.show_fft_var.set(False)
        self.toggle_fft_view(initial_clear=True); self.root.update_idletasks()
        self.history.undo_stack.clear(); self.history.redo_stack.clear(); self.update_edit_menu_state()
    def _clear_data_ui(self):
        for widget in self.scrollable_data_frame.winfo_children(): widget.destroy()
        select_all_frame = ttk.Frame(self.scrollable_data_frame); select_all_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(select_all_frame, text="Zaznacz wszystkie", command=self._select_all_sheets).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,2))
        ttk.Button(select_all_frame, text="Odznacz wszystkie", command=self._deselect_all_sheets).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2,0))
        self.checkbox_container = ttk.Frame(self.scrollable_data_frame); self.checkbox_container.pack(fill='x')
        self.initial_data_label = ttk.Label(self.checkbox_container, text="Nie wczytano żadnych danych.", wraplength=280); self.initial_data_label.pack(padx=5, pady=5)
        self.excel_filepath = None
    def _load_excel_file(self):
        filepath = filedialog.askopenfilename(title="Wybierz plik Excel", filetypes=(("Pliki Excel", "*.xlsx"), ("Wszystkie pliki", "*.*")))
        if not filepath: logging.info("Anulowano wybór pliku Excel."); return
        self.history.save_state("Wczytaj plik XLSX")
        logging.info(f"Wybrano plik Excel: {filepath}"); self.excel_filepath = filepath
        self._process_excel_file()
    def _process_excel_file(self):
        if not self.excel_filepath or not os.path.exists(self.excel_filepath): return
        try:
            xls = pd.ExcelFile(self.excel_filepath); sheet_names = xls.sheet_names
            if not sheet_names: messagebox.showwarning("Pusty Plik", f"Plik '{os.path.basename(self.excel_filepath)}' jest pusty."); return
            new_files_loaded = False
            for sheet_name in sheet_names:
                plot_id = f"excel_{self.excel_filepath}_{sheet_name}"
                df = pd.read_excel(self.excel_filepath, sheet_name=sheet_name)
                if len(df.columns) < 2: continue
                if self._add_or_update_data(plot_id, df, str(sheet_name)): new_files_loaded = True
            if new_files_loaded:
                self._update_combobox()
                self._redraw_and_fit(f"Dopasowano widok po wczytaniu arkuszy z '{os.path.basename(self.excel_filepath)}'.")
        except Exception as e: logging.error(f"Błąd podczas wczytywania Excela '{self.excel_filepath}': {e}", exc_info=True); messagebox.showerror("Błąd wczytywania Excela", f"Nie można odczytać pliku '{self.excel_filepath}'.\n\nBłąd: '{e}'")
    def load_data_and_plot(self):
        filepaths = filedialog.askopenfilenames(title="Wybierz pliki z danymi", filetypes=(("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")))
        if not filepaths: logging.info("Nie wczytano żadnych plików do wczytania."); return
        self.history.save_state("Wczytaj pliki TXT")
        logging.info(f"Wybrano do wczytania pliki: {filepaths}"); new_files_loaded, last_loaded_label, skipped_files = False, None, []
        for filepath in filepaths:
            plot_id = f"manual_{filepath}"
            try:
                df = pd.read_csv(filepath, sep=r'\s+', comment='#', header=None, skiprows=1, engine='python')
                if df.empty or df.shape[1] < 2: continue
                if df.shape[1] >= 3: df = df.iloc[:, :3]
                df.columns = ['Time (ps)', 'Rad THz', 'Rad Time'][:df.shape[1]]; df = df.apply(pd.to_numeric, errors='coerce').dropna()
                if df.empty: continue
                label, last_loaded_label = os.path.basename(filepath), os.path.basename(filepath)
                if self._add_or_update_data(plot_id, df, label): new_files_loaded = True
            except Exception as e: logging.error(f"Błąd wczytywania pliku {os.path.basename(filepath)}: {e}", exc_info=True); messagebox.showerror(f"Błąd wczytywania pliku {os.path.basename(filepath)}", f"Wystąpił błąd: {e}")
        if new_files_loaded:
            self._update_combobox()
            if last_loaded_label: self.active_signal_var.set(last_loaded_label); self._on_signal_selected()
            self._redraw_and_fit("Automatycznie dopasowano widok po wczytaniu plików .txt.")
        if skipped_files: messagebox.showinfo("Pominięto pliki", "Następujące pliki zostały pominięte:\n\n" + "\n".join(skipped_files))
    def _validate_odd_int(self, value_if_allowed): return value_if_allowed.isdigit() or value_if_allowed == ""
    def _show_histogram(self):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id: messagebox.showwarning("Brak danych", "Proszę wybrać aktywny sygnał."); return
        hist_window = tk.Toplevel(self.root); hist_window.title(f"Histogram: {self.plotted_data[plot_id]['label']}"); hist_window.geometry("600x450")
        fig = Figure(figsize=(6, 4), dpi=100, constrained_layout=True); ax = fig.add_subplot(111)
        data = self.plotted_data[plot_id]; y_data = data['df'].iloc[:, 1].to_numpy(dtype=float) * data['scale_factor']; y_data = self._apply_smoothing(y_data, plot_id)
        ax.hist(y_data, bins='auto', color=data['color'], alpha=0.75)
        ax.set_title("Rozkład wartości amplitudy"); ax.set_xlabel("Amplituda (a.u.)"); ax.set_ylabel("Liczba wystąpień"); ax.grid(True, linestyle='--', alpha=0.6)
        canvas = FigureCanvasTkAgg(fig, master=hist_window); canvas.draw(); canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    def _connect_events(self): 
        self.fig.canvas.mpl_connect('motion_notify_event', self._on_mouse_move); self.fig.canvas.mpl_connect('axes_leave_event', self._on_mouse_leave); self.fig.canvas.mpl_connect('button_press_event', self._on_plot_click)
        self.root.bind('<Control-z>', lambda event: self.history.undo())
        self.root.bind('<Control-y>', lambda event: self.history.redo())
    def _on_mouse_move(self, event):
        if not event.inaxes: self.crosshair_v.set_visible(False); self.crosshair_h.set_visible(False); self.status_bar.config(text=" Najechanie na wykres pokaże współrzędne"); self.canvas.draw_idle(); return
        self.crosshair_v.set_data([event.xdata, event.xdata], [0, 1]); self.crosshair_h.set_data([0, 1], [event.ydata, event.ydata]); self.crosshair_v.set_visible(True); self.crosshair_h.set_visible(True)
        self.status_bar.config(text=f" Czas: {event.xdata:,.3f} ps  |  Sygnał: {event.ydata:,.5f} a.u."); self.canvas.draw_idle()
    def _on_mouse_leave(self, event): self.crosshair_v.set_visible(False); self.crosshair_h.set_visible(False); self.status_bar.config(text=" Najechanie na wykres pokaże współrzędne"); self.canvas.draw_idle()
    def _on_plot_click(self, event):
        if not event.inaxes or self.show_fft_var.get(): return
        if event.button == 2:
            if len(self.markers) >= 2: oldest_marker = self.markers.pop(0); oldest_marker['line'].remove(); oldest_marker['text'].remove()
            line = self.ax.axvline(event.xdata, color='red', linestyle=':', linewidth=1.5); text = self.ax.text(event.xdata, self.ax.get_ylim()[1], f" {len(self.markers)+1}", color='red', va='bottom', ha='left')
            self.markers.append({'line': line, 'text': text, 'x': event.xdata}); self._update_marker_calculations()
        elif event.button == 3: self.history.save_state("Wyczyść znaczniki"); self._clear_markers()
        self.canvas.draw_idle()
    def _clear_markers(self):
        for marker in self.markers: marker['line'].remove(); marker['text'].remove()
        self.markers.clear();
        if self.marker_text: self.marker_text.remove(); self.marker_text = None
        self.canvas.draw_idle()
    def _update_marker_calculations(self):
        if self.marker_text: self.marker_text.remove(); self.marker_text = None
        if len(self.markers) == 2:
            m1_x, m2_x = self.markers[0]['x'], self.markers[1]['x']; delta_t = abs(m2_x - m1_x); plot_id = self._get_plot_id_from_active_signal(); delta_y_text = "n/a"
            if plot_id and plot_id in self.plotted_data:
                data = self.plotted_data[plot_id]; x_data = data['df'].iloc[:, 0].to_numpy(dtype=float); y_data = data['df'].iloc[:, 1].to_numpy(dtype=float) * data['scale_factor']; y_data = self._apply_smoothing(y_data, plot_id)
                idx1, idx2 = np.argmin(np.abs(x_data - m1_x)), np.argmin(np.abs(x_data - m2_x))
                delta_y = abs(y_data[idx2] - y_data[idx1]); delta_y_text = f"{float(delta_y):,.5f} a.u."
            text_content = f"Δt = {float(delta_t):,.3f} ps\nΔy = {delta_y_text}"
            self.marker_text = self.ax.text(0.98, 0.98, text_content, transform=self.ax.transAxes, fontsize=10, va='top', ha='right', bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.8))
    def _update_statistics_display(self):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id or self.show_fft_var.get():
            for var in self.stats_labels.values(): var.set("--")
            return
        data = self.plotted_data[plot_id]; x_data = data['df'].iloc[:, 0].to_numpy(dtype=float); y_data = data['df'].iloc[:, 1].to_numpy(dtype=float) * data['scale_factor']; y_data = self._apply_smoothing(y_data, plot_id)
        if y_data.size > 0:
            max_val, min_val, mean_val = np.max(y_data), np.min(y_data), np.mean(y_data); peak_time = x_data[np.argmax(np.abs(y_data))]
            self.stats_labels["Max"].set(f"{float(max_val):.5f}"); self.stats_labels["Min"].set(f"{float(min_val):.5f}"); self.stats_labels["Pozycja Piku"].set(f"{float(peak_time):.3f} ps"); self.stats_labels["Średnia"].set(f"{float(mean_val):.5f}")
        else:
            for var in self.stats_labels.values(): var.set("--")
    def _select_all_sheets(self, select=True):
        if not self.visibility_vars: logging.info("Brak danych do zaznaczenia."); return
        self.history.save_state("Zaznacz/Odznacz wszystkie")
        logging.info(f"Zaznaczanie wszystkich danych: {select}")
        for plot_id, var in self.visibility_vars.items():
             var.set(select); self.plotted_data[plot_id]['visible'] = select
        self._redraw_and_fit(f"Dopasowano widok po zaznaczeniu/odznaczeniu wszystkich danych.")
    def _deselect_all_sheets(self): self._select_all_sheets(select=False)
    def _on_grid_style_selected(self, style_map: Dict[str, str]):
        self.grid_style_display_var.get(); internal_style = style_map.get(self.grid_style_display_var.get(), "--")
        self.grid_style_internal_var.set(internal_style); self._update_grid()
    def _update_grid(self, event=None):
        if self.grid_visible_var.get(): self.ax.grid(True, color=self.grid_color_var.get(), linestyle=self.grid_style_internal_var.get(), linewidth=self.grid_width_var.get())
        else: self.ax.grid(False)
        self.canvas.draw_idle()
    def _choose_grid_color(self):
        color_code = colorchooser.askcolor(title="Wybierz kolor siatki", initialcolor=self.grid_color_var.get())
        if color_code and color_code[1]: self.grid_color_var.set(color_code[1]); self.grid_color_preview.config(bg=color_code[1]); self._update_grid()
    def normalize_amplitudes(self):
        self.history.save_state("Normalizuj amplitudy")
        logging.info("Rozpoczęto normalizację amplitud.")
        if self.show_fft_var.get(): logging.warning("Próba normalizacji w widoku FFT."); messagebox.showinfo("Informacja", "Normalizacja jest dostępna tylko w trybie domeny czasu."); return
        ref_plot_id = self._get_plot_id_from_active_signal()
        if not ref_plot_id: logging.warning("Normalizacja przerwana - brak sygnału ref."); messagebox.showwarning("Brak Referencji", "Proszę wybrać sygnał referencyjny."); return
        ref_label = self.plotted_data[ref_plot_id]['label']; logging.info(f"Sygnał referencyjny: '{ref_label}'")
        ref_y_raw = self.plotted_data[ref_plot_id]['df'].iloc[:, 1].to_numpy(dtype=float)
        if ref_y_raw.size == 0: logging.error(f"Sygnał referencyjny '{ref_label}' nie zawiera danych."); messagebox.showwarning("Błąd Danych", f"Sygnał referencyjny '{ref_label}' nie zawiera danych."); return
        max_ref_amp = np.max(np.abs(ref_y_raw))
        if max_ref_amp == 0: logging.warning(f"Sygnał referencyjny '{ref_label}' ma zerową amplitudę."); messagebox.showwarning("Błąd", "Sygnał referencyjny ma zerową amplitudę."); return
        visible_plots = {pid: d for pid, d in self.plotted_data.items() if d.get('visible', False) and not d.get('is_comparison')}
        if len(visible_plots) < 2: logging.info("Normalizacja niewymagana - < 2 wykresy."); messagebox.showinfo("Informacja", "Potrzebne są co najmniej dwa widoczne wykresy."); return
        for plot_id, data in visible_plots.items():
            if plot_id == ref_plot_id: data['scale_factor'] = 1.0; continue
            current_y_raw = data['df'].iloc[:, 1].to_numpy(dtype=float)
            if current_y_raw.size == 0: logging.warning(f"Wykres '{data['label']}' nie zawiera danych."); data['scale_factor'] = 1.0; continue
            max_current_amp = np.max(np.abs(current_y_raw))
            if max_current_amp > 0: data['scale_factor'] = float(max_ref_amp / max_current_amp)
            else: data['scale_factor'] = 1.0
            logging.info(f"Znormalizowano '{data['label']}' z współczynnikiem {data['scale_factor']:.4f}")
        self._on_signal_selected(); self.redraw_all_plots(); logging.info("Normalizacja zakończona.")
    def _update_from_slider(self, log_value_str: str):
        if self._is_updating_ui: return
        self._is_updating_ui = True; scale_factor = 10**float(log_value_str)
        self.scale_entry_var.set(f"{scale_factor:.4f}"); self._apply_scaling_to_plot(scale_factor, save_history=False); self._is_updating_ui = False
    def _update_from_entry(self, event=None):
        if self._is_updating_ui: return
        self._is_updating_ui = True
        try:
            scale_factor = float(self.scale_entry_var.get())
            if scale_factor <= 0: raise ValueError("Współczynnik musi być dodatni")
            self.history.save_state("Zmiana skali (wpisanie)")
            self._update_scaling_ui(scale_factor, update_entry=False); self._apply_scaling_to_plot(scale_factor, save_history=False)
        except (ValueError, TclError): messagebox.showerror("Błąd wartości", "Proszę wprowadzić prawidłową liczbę dodatnią.")
        finally: self._is_updating_ui = False
    def _apply_scaling_to_plot(self, scale_factor: float, save_history=True):
        if save_history: self.history.save_state("Zmiana skali (suwak)")
        plot_id = self._get_plot_id_from_active_signal()
        if plot_id: self.plotted_data[plot_id]['scale_factor'] = scale_factor; self.redraw_all_plots()
    def _update_scaling_ui(self, scale_factor: float, update_entry=True):
        self._is_updating_ui = True
        try:
            if update_entry: self.scale_entry_var.set(f"{scale_factor:.4f}")
            log_value = np.log10(scale_factor) if scale_factor > 0 else -3.0
            self.log_scale_slider.set(float(max(min(log_value, 3.0), -3.0)))
        except TclError: pass
        finally: self._is_updating_ui = False
    def _on_signal_selected(self, event=None):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id: self._update_scaling_ui(1.0); self.label_edit_var.set(''); self.active_signal_var.set(''); self._update_statistics_display(); return
        data = self.plotted_data[plot_id]
        self._update_scaling_ui(data['scale_factor']); self.label_edit_var.set(data['label']); self._update_statistics_display()
    def _change_active_plot_color(self):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id: messagebox.showwarning("Brak zaznaczenia", "Proszę wybrać widoczny sygnał."); return
        self.history.save_state("Zmiana koloru")
        current_color = self.plotted_data[plot_id].get('color')
        color_data = colorchooser.askcolor(initialcolor=current_color if current_color else "#000000", title="Wybierz kolor wykresu")
        if color_data and color_data[1]: 
            logging.info(f"Zmiana koloru dla '{self.plotted_data[plot_id]['label']}' na {color_data[1]}")
            self.plotted_data[plot_id]['color'] = color_data[1]; self.plotted_data[plot_id]['original_color'] = color_data[1]; self.redraw_all_plots()
    def _update_combobox(self):
        visible_labels = [data['label'] for pid, data in self.plotted_data.items() if data.get('visible', False) and not data.get('is_comparison', False)]
        current_selection = self.active_signal_var.get()
        sorted_labels = sorted(visible_labels)
        self.signal_selector['values'] = sorted_labels; self.signal_selector_2['values'] = sorted_labels
        if current_selection not in visible_labels:
            if visible_labels: self.active_signal_var.set(sorted_labels[0])
            else: self.active_signal_var.set('')
        self._on_signal_selected()
    def toggle_fft_view(self, initial_clear=False):
        is_fft = self.show_fft_var.get(); logging.info(f"Przełączanie widoku FFT na: {is_fft}")
        new_state = 'disabled' if is_fft else 'normal'
        self.fit_view_button.config(state=new_state); self.normalize_button.config(state=new_state)
        self._clear_markers(); self._update_statistics_display()
        if not initial_clear: self.redraw_all_plots()
    def _get_plot_id_from_active_signal(self) -> str | None:
        selected_label = self.active_signal_var.get()
        if not selected_label: return None
        for pid, data in self.plotted_data.items():
            if data['label'] == selected_label and data.get('visible', False): return pid
        return None
    def _toggle_legend_visibility(self):
        is_visible = self.legend_visible_var.get(); logging.info(f"Przełączanie legendy na: {is_visible}")
        legend = self.ax.get_legend()
        if legend: legend.set_visible(is_visible)
        elif is_visible and self.ax.has_data(): self.ax.legend()
        self.canvas.draw_idle()
    def _update_label(self):
        plot_id = self._get_plot_id_from_active_signal()
        if not plot_id: messagebox.showwarning("Brak zaznaczenia", "Proszę wybrać widoczny sygnał."); return
        self.history.save_state("Zmiana etykiety")
        old_label = self.plotted_data[plot_id]['label']; new_label = self.label_edit_var.get().strip()
        if not new_label: messagebox.showwarning("Pusta etykieta", "Etykieta nie może być pusta."); return
        for pid, data in self.plotted_data.items():
            if data.get('visible', False) and data['label'] == new_label and pid != plot_id: messagebox.showerror("Błąd", "Ta etykieta jest już używana."); return
        logging.info(f"Zmiana etykiety z '{old_label}' na '{new_label}'.")
        self.plotted_data[plot_id]['label'] = new_label
        self._update_combobox(); self.redraw_all_plots(); self.active_signal_var.set(new_label)
    def fit_view_to_data(self):
        try:
            visible_lines = [data['line'] for data in self.plotted_data.values() if data.get('visible') and data.get('line')]
            if not visible_lines: return
            logging.info("Dopasowywanie widoku do danych.")
            min_x, max_x, min_y, max_y = np.inf, -np.inf, np.inf, -np.inf
            for line in visible_lines:
                x_data, y_data = line.get_xdata(), line.get_ydata()
                if x_data.size > 0: min_x, max_x = min(min_x, np.min(x_data)), max(max_x, np.max(x_data))
                if y_data.size > 0: min_y, max_y = min(min_y, np.min(y_data)), max(max_y, np.max(y_data))
            if np.isinf(min_x) or np.isinf(min_y): return
            y_margin = (max_y - min_y) * 0.05
            if y_margin == 0: y_margin = 1
            self.ax.set_xlim(float(min_x), float(max_x)); self.ax.set_ylim(float(min_y - y_margin), float(max_y + y_margin))
            self.canvas.draw_idle()
        except Exception as e: logging.error(f"Błąd podczas dopasowywania widoku: {e}", exc_info=True)
    def _redraw_and_fit(self, log_message: str): self.redraw_all_plots(); self.fit_view_to_data(); logging.info(log_message)

if __name__ == "__main__":
    root = tk.Tk()
    app = DataVisualizerApp(root)
    def on_closing():
        logging.info("Aplikacja jest zamykana.")
        try: 
            app.root.quit()
            app.root.destroy()
        except TclError: pass
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
