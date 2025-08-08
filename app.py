# -- coding: utf-8 --

"""
Aplikacja desktopowa do wizualizacji danych eksperymentalnych 2D
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, TclError, colorchooser
from typing import Union, Dict, Any
import pandas as pd
import numpy as np
import os
from scipy.fft import fft, fftfreq

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends._backend_tk import NavigationToolbar2Tk

class DataVisualizerApp:
    """
    Główna klasa aplikacji do wizualizacji danych, hermetyzująca
    całą logikę interfejsu użytkownika i przetwarzania danych.
    """
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("THz Data Visualizer v3.9 (Multi-File Load)")
        self.root.geometry("1280x800")

        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        self.high_contrast_colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
        ]

        self.plotted_data: Dict[str, Dict[str, Any]] = {}
        self.visibility_vars: Dict[str, tk.BooleanVar] = {}
        
        self.control_canvas = None
        self._is_updating_ui = False
        
        self._create_main_layout()
        self._create_plot_area()
        self._create_control_panel()
        self._initialize_plot()
        
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        self.root.bind_all("<Button-4>", self._on_mousewheel)
        self.root.bind_all("<Button-5>", self._on_mousewheel)

    def _create_main_layout(self):
        main_paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        main_paned_window.pack(fill=tk.BOTH, expand=True)
        self.plot_frame = ttk.Frame(main_paned_window, width=980)
        main_paned_window.add(self.plot_frame, stretch="always")
        self.control_frame = ttk.Frame(main_paned_window, width=320)
        main_paned_window.add(self.control_frame, stretch="never")
        self.control_frame.pack_propagate(False)

    def _create_plot_area(self):
        self.fig = Figure(figsize=(8, 6), dpi=100, constrained_layout=True)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar_frame = ttk.Frame(self.plot_frame)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        
    def _create_control_panel(self):
        self.control_canvas = tk.Canvas(self.control_frame)
        scrollbar = ttk.Scrollbar(self.control_frame, orient="vertical", command=self.control_canvas.yview)
        self.control_canvas.configure(yscrollcommand=scrollbar.set)
        self.scrollable_content_frame = ttk.Frame(self.control_canvas)
        self.control_canvas.create_window((0, 0), window=self.scrollable_content_frame, anchor="nw")
        self.scrollable_content_frame.bind("<Configure>", lambda e: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all")))
        scrollbar.pack(side="right", fill="y")
        self.control_canvas.pack(side="left", fill="both", expand=True)

        content_frame = self.scrollable_content_frame

        file_ops_frame = ttk.LabelFrame(content_frame, text="Operacje na Plikach", padding=10)
        file_ops_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        ttk.Button(file_ops_frame, text="Wczytaj dane", command=self.load_data_and_plot).pack(fill=tk.X, pady=5)
        ttk.Button(file_ops_frame, text="Wyczyść wykres", command=self.clear_plot).pack(fill=tk.X, pady=5)
        
        self.visibility_frame = ttk.LabelFrame(content_frame, text="Zarządzanie Wykresami", padding=10)
        self.visibility_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))

        processing_frame = ttk.LabelFrame(content_frame, text="Przetwarzanie Sygnału", padding=10)
        processing_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        self.show_fft_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(processing_frame, text="Pokaż Transformację Fouriera (FFT)", variable=self.show_fft_var, command=self.toggle_fft_view).pack(anchor='w')

        plot_options_frame = ttk.LabelFrame(content_frame, text="Opcje Wykresu", padding=10)
        plot_options_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        self.legend_visible_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_options_frame, text="Pokaż legendę", variable=self.legend_visible_var, command=self._toggle_legend_visibility).pack(anchor='w', pady=(0, 5))
        self.fit_view_button = ttk.Button(plot_options_frame, text="Dopasuj widok do danych", command=self.fit_view_to_data)
        self.fit_view_button.pack(fill=tk.X, pady=(0, 5))
        self.normalize_button = ttk.Button(plot_options_frame, text="Normalizuj Amplitudy", command=self.normalize_amplitudes)
        self.normalize_button.pack(fill=tk.X)

        self.zoom_frame = ttk.LabelFrame(content_frame, text="Automatyczne Skalowanie", padding=10)
        self.zoom_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        self.zoom_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.zoom_frame, text="Włącz auto-zoom na impuls", variable=self.zoom_active_var, command=self._apply_auto_zoom).pack(anchor='w')
        ttk.Label(self.zoom_frame, text="Szerokość okna (ps):").pack(anchor='w', pady=(10, 0))
        self.zoom_window_var = tk.StringVar(value="100")
        ttk.Entry(self.zoom_frame, textvariable=self.zoom_window_var).pack(fill=tk.X)

        edit_frame = ttk.LabelFrame(content_frame, text="Edycja Aktywnego Sygnału", padding=10)
        edit_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        ttk.Label(edit_frame, text="Aktywny sygnał (referencja do normalizacji):").pack(fill=tk.X)
        self.active_signal_var = tk.StringVar()
        self.signal_selector = ttk.Combobox(edit_frame, textvariable=self.active_signal_var, state='readonly')
        self.signal_selector.pack(fill=tk.X, pady=(0, 10))
        self.signal_selector.bind("<<ComboboxSelected>>", self._on_signal_selected)
        ttk.Label(edit_frame, text="Współczynnik skalowania:").pack(fill=tk.X, pady=(5, 0))
        self.scale_entry_var = tk.StringVar(value="1.0")
        scale_entry = ttk.Entry(edit_frame, textvariable=self.scale_entry_var)
        scale_entry.pack(fill=tk.X, pady=(0, 5))
        scale_entry.bind("<Return>", self._update_from_entry)
        scale_entry.bind("<FocusOut>", self._update_from_entry)
        self.log_scale_slider = ttk.Scale(edit_frame, from_=-3.0, to=3.0, orient=tk.HORIZONTAL, command=self._update_from_slider)
        self.log_scale_slider.set(0)
        self.log_scale_slider.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(edit_frame, text="Nowa nazwa:").pack(anchor='w')
        self.label_edit_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.label_edit_var).pack(fill=tk.X, pady=(0, 5))
        ttk.Button(edit_frame, text="Zmień etykietę", command=self._update_label).pack(fill=tk.X, pady=(0,5))
        ttk.Button(edit_frame, text="Zmień kolor", command=self._change_active_plot_color).pack(fill=tk.X)

    def _on_mousewheel(self, event):
        if not self.control_canvas or not str(event.widget).startswith(str(self.control_canvas)): return
        if event.num == 4: self.control_canvas.yview_scroll(-1, "units")
        elif event.num == 5: self.control_canvas.yview_scroll(1, "units")
        else: self.control_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def _initialize_plot(self):
        if self.show_fft_var.get():
            self.ax.set_title("Analiza Częstotliwościowa (FFT)", fontsize=14)
            self.ax.set_xlabel("Częstotliwość (THz)", fontsize=12)
            self.ax.set_ylabel("Amplituda FFT (a.u.)", fontsize=12)
        else:
            self.ax.set_title("Wizualizacja danych z eksperymentu THz", fontsize=14)
            self.ax.set_xlabel("Time (ps)", fontsize=12)
            self.ax.set_ylabel("Signal (a.u.)", fontsize=12)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        self.canvas.draw()

    def clear_plot(self):
        self.ax.cla()
        self.plotted_data.clear()
        self.visibility_vars.clear()
        for widget in self.visibility_frame.winfo_children(): widget.destroy()
        self.signal_selector['values'] = []
        self._on_signal_selected()
        self.legend_visible_var.set(True)
        if self.show_fft_var.get():
            self.show_fft_var.set(False)
            self.toggle_fft_view()
        else:
            self._initialize_plot()
            self.canvas.draw()
        self.root.update_idletasks()

    def load_data_and_plot(self):
        # ZMIANA: Użycie askopenfilenames do wczytania wielu plików
        filepaths = filedialog.askopenfilenames(
            title="Wybierz pliki z danymi", 
            filetypes=(("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*"))
        )
        if not filepaths: return

        new_files_loaded = False
        last_loaded_filename = None
        skipped_files = []

        for filepath in filepaths:
            if filepath in self.plotted_data:
                skipped_files.append(os.path.basename(filepath))
                continue
            try:
                df = pd.read_csv(filepath, sep='\t', comment='#')
                if len(df.columns) < 2:
                    messagebox.showwarning("Błąd Pliku", f"Plik {os.path.basename(filepath)} ma nieprawidłową strukturę i został pominięty.")
                    continue
                
                filename = os.path.basename(filepath)
                last_loaded_filename = filename
                
                load_index = len(self.plotted_data)
                initial_color = self.high_contrast_colors[load_index % len(self.high_contrast_colors)]
                
                self.plotted_data[filepath] = {
                    'df': df, 'line': None, 'scale_factor': 1.0, 
                    'filename': filename, 'label': filename, 'visible': True,
                    'load_index': load_index, 'color': initial_color
                }
                
                var = tk.BooleanVar(value=True)
                self.visibility_vars[filepath] = var
                cb = ttk.Checkbutton(self.visibility_frame, text=filename, variable=var,
                                     command=lambda fp=filepath: self._on_visibility_changed(fp))
                cb.pack(anchor='w')
                new_files_loaded = True
            except Exception as e:
                messagebox.showerror(f"Błąd wczytywania pliku {os.path.basename(filepath)}", f"Wystąpił błąd: {e}")
        
        # ZMIANA: Aktualizuj UI tylko raz, po zakończeniu pętli
        if new_files_loaded:
            self._update_combobox()
            if last_loaded_filename:
                self.active_signal_var.set(last_loaded_filename)
                self._on_signal_selected()
            self.redraw_all_plots()
            
        if skipped_files:
            messagebox.showinfo("Pominięto pliki", "Następujące pliki zostały pominięte, ponieważ są już wczytane:\n\n" + "\n".join(skipped_files))

    def redraw_all_plots(self):
        self.ax.cla()
        is_fft = self.show_fft_var.get()
        for data in self.plotted_data.values():
            if not data.get('visible', False): continue
            style_dict = {'color': data['color'], 'linestyle': '-'}
            df, scale = data['df'], data['scale_factor']
            label_text = f"{data['label']} (x{scale:.3f})"
            x_data_original = df.iloc[:, 0].to_numpy(dtype=float)
            y_data_original = df.iloc[:, 1].to_numpy(dtype=float) * scale
            line_data_x, line_data_y = x_data_original, y_data_original
            if is_fft:
                n_points = len(x_data_original)
                if n_points > 1:
                    time_step = float(np.mean(np.diff(x_data_original))) * 1e-12
                    yf, xf = fft(y_data_original), fftfreq(n_points, time_step)
                    positive_freq_indices = np.where(xf >= 0)[0] 
                    xf_positive = xf[positive_freq_indices] / 1e12
                    yf_positive_amp = 2.0/n_points * np.abs(np.asarray(yf[positive_freq_indices]))
                    line_data_x, line_data_y = xf_positive, yf_positive_amp
            line, = self.ax.plot(line_data_x, line_data_y, label=label_text, **style_dict)
            data['line'] = line
        self._initialize_plot()
        if self.legend_visible_var.get() and self.ax.has_data(): self.ax.legend()
        if not is_fft: self._apply_auto_zoom()
        else:
            if self.ax.has_data():
                self.ax.set_xlim(left=0)
                self.ax.autoscale(enable=True, axis='y')
        self.canvas.draw()
    
    def normalize_amplitudes(self):
        if self.show_fft_var.get():
            messagebox.showinfo("Informacja", "Normalizacja amplitud jest dostępna tylko w trybie domeny czasu.")
            return
        ref_filepath = self._get_filepath_from_active_signal()
        if not ref_filepath:
            messagebox.showwarning("Brak Referencji", "Proszę wybrać sygnał referencyjny z listy, aby dokonać normalizacji.")
            return
        visible_plots = {fp: d for fp, d in self.plotted_data.items() if d.get('visible')}
        if len(visible_plots) < 2:
            messagebox.showinfo("Informacja", "Potrzebne są co najmniej dwa widoczne wykresy do przeprowadzenia normalizacji.")
            return
        try:
            ref_y_raw = visible_plots[ref_filepath]['df'].iloc[:, 1].to_numpy(dtype=float)
            max_ref_amp = np.max(np.abs(ref_y_raw))
            if max_ref_amp == 0:
                messagebox.showwarning("Błąd", "Sygnał referencyjny ma zerową amplitudę i nie może być użyty do normalizacji.")
                return
            for filepath, data in visible_plots.items():
                if filepath == ref_filepath:
                    data['scale_factor'] = 1.0
                    continue
                current_y_raw = data['df'].iloc[:, 1].to_numpy(dtype=float)
                max_current_amp = np.max(np.abs(current_y_raw))
                if max_current_amp > 0: data['scale_factor'] = max_ref_amp / max_current_amp
                else: data['scale_factor'] = 1.0
            self._on_signal_selected()
            self.redraw_all_plots()
        except Exception as e:
            messagebox.showerror("Błąd normalizacji", f"Wystąpił nieoczekiwany błąd: {e}")

    def _update_from_slider(self, log_value_str: str):
        if self._is_updating_ui: return
        self._is_updating_ui = True
        log_value = float(log_value_str)
        scale_factor = 10**log_value
        self.scale_entry_var.set(f"{scale_factor:.4f}")
        self._apply_scaling_to_plot(scale_factor)
        self._is_updating_ui = False

    def _update_from_entry(self, event=None):
        if self._is_updating_ui: return
        self._is_updating_ui = True
        try:
            scale_factor = float(self.scale_entry_var.get())
            if scale_factor <= 0: raise ValueError("Współczynnik musi być dodatni")
            self._update_scaling_ui(scale_factor, update_entry=False)
            self._apply_scaling_to_plot(scale_factor)
        except ValueError: messagebox.showerror("Błąd wartości", "Proszę wprowadzić prawidłową liczbę dodatnią.")
        finally: self._is_updating_ui = False

    def _apply_scaling_to_plot(self, scale_factor: float):
        filepath = self._get_filepath_from_active_signal()
        if filepath:
            self.plotted_data[filepath]['scale_factor'] = scale_factor
            self.redraw_all_plots()
    
    def _update_scaling_ui(self, scale_factor: float, update_entry=True):
        self._is_updating_ui = True
        try:
            if update_entry: self.scale_entry_var.set(f"{scale_factor:.4f}")
            log_value = np.log10(scale_factor) if scale_factor > 0 else -3.0
            log_value = max(min(log_value, 3.0), -3.0)
            self.log_scale_slider.set(log_value)
        finally: self._is_updating_ui = False

    def _on_signal_selected(self, event=None):
        filepath = self._get_filepath_from_active_signal()
        if not filepath:
            self._update_scaling_ui(1.0)
            self.label_edit_var.set('')
            self.active_signal_var.set('')
            return
        data = self.plotted_data[filepath]
        self._update_scaling_ui(data['scale_factor'])
        self.label_edit_var.set(data['label'])
    
    def _change_active_plot_color(self):
        filepath = self._get_filepath_from_active_signal()
        if not filepath:
            messagebox.showwarning("Brak zaznaczenia", "Proszę wybrać widoczny sygnał z listy, aby zmienić jego kolor.")
            return
        current_color = self.plotted_data[filepath].get('color')
        color_data = colorchooser.askcolor(initialcolor=current_color, title="Wybierz kolor wykresu")
        if color_data and color_data[1]:
            self.plotted_data[filepath]['color'] = color_data[1]
            self.redraw_all_plots()
    
    def _on_visibility_changed(self, filepath: str):
        if filepath in self.plotted_data and filepath in self.visibility_vars:
            self.plotted_data[filepath]['visible'] = self.visibility_vars[filepath].get()
            self._update_combobox()
            self.redraw_all_plots()

    def _update_combobox(self):
        visible_filenames = [
            data['filename'] for data in self.plotted_data.values() if data.get('visible', False)
        ]
        self.signal_selector['values'] = visible_filenames
        if self.active_signal_var.get() not in visible_filenames: self._on_signal_selected()

    def _apply_auto_zoom(self):
        if self.show_fft_var.get(): return
        if not self.zoom_active_var.get():
            self.fit_view_to_data()
            return
        self.toolbar.home()
        first_visible_key = next((fp for fp, data in self.plotted_data.items() if data.get('visible')), None)
        if first_visible_key:
            try:
                main_df = self.plotted_data[first_visible_key]['df']
                x_data, y_data = main_df.iloc[:, 0].to_numpy(dtype=float), main_df.iloc[:, 1].to_numpy(dtype=float)
                gradient = np.abs(np.diff(y_data))
                pulse_index = np.argmax(gradient)
                pulse_time = x_data[pulse_index]
                window_width = float(self.zoom_window_var.get())
                self.ax.set_xlim(pulse_time - window_width / 2, pulse_time + window_width / 2)
                self.ax.autoscale(enable=True, axis='y')
            except (ValueError, IndexError) as e:
                messagebox.showwarning("Błąd Auto-Zoom", f"Nie można było znaleźć impulsu do wyśrodkowania: {e}")
                self.fit_view_to_data()
        else: self.fit_view_to_data()
        self.canvas.draw_idle()
    
    def toggle_fft_view(self):
        is_fft = self.show_fft_var.get()
        new_state = 'disabled' if is_fft else 'normal'
        self.zoom_frame.config(state=new_state)
        self.fit_view_button.config(state=new_state)
        self.normalize_button.config(state=new_state)
        for child in self.zoom_frame.winfo_children():
            if hasattr(child, 'configure') and 'state' in child.configure():
                child.configure(state=new_state)
        self.redraw_all_plots()

    def _get_filepath_from_active_signal(self) -> str | None:
        selected_filename = self.active_signal_var.get()
        if not selected_filename: return None
        for fp, data in self.plotted_data.items():
            if data['filename'] == selected_filename and data.get('visible'): return fp
        return None

    def _toggle_legend_visibility(self):
        legend = self.ax.get_legend()
        if legend: legend.set_visible(self.legend_visible_var.get())
        elif self.legend_visible_var.get() and self.ax.has_data(): self.ax.legend()
        self.canvas.draw_idle()

    def _update_label(self):
        filepath = self._get_filepath_from_active_signal()
        if not filepath:
            messagebox.showwarning("Brak zaznaczenia", "Proszę wybrać widoczny sygnał z listy.")
            return
        new_label = self.label_edit_var.get().strip()
        if not new_label:
            messagebox.showwarning("Pusta etykieta", "Etykieta nie może być pusta.")
            return
        self.plotted_data[filepath]['label'] = new_label
        self.redraw_all_plots()

    def fit_view_to_data(self):
        visible_lines = [line for line in self.ax.lines if line.get_visible()]
        if not visible_lines: return
        self.zoom_active_var.set(False)
        min_x, max_x, min_y, max_y = np.inf, -np.inf, np.inf, -np.inf
        for line in visible_lines:
            x_data, y_data = line.get_xdata(), line.get_ydata()
            if x_data.size > 0: min_x, max_x = min(min_x, np.min(x_data)), max(max_x, np.max(x_data))
            if y_data.size > 0: min_y, max_y = min(min_y, np.min(y_data)), max(max_y, np.max(y_data))
        if np.isinf(min_x) or np.isinf(min_y): return
        y_margin = (max_y - min_y) * 0.05
        if y_margin == 0: y_margin = 1
        self.ax.set_xlim(min_x, max_x)
        self.ax.set_ylim(min_y - y_margin, max_y + y_margin)
        self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    app = DataVisualizerApp(root)
    
    def on_closing():
        try:
            app.root.quit()
            app.root.destroy()
        except TclError: pass 
            
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
