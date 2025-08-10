[![AI Assisted](https://img.shields.io/badge/AI-Assisted-blue?style=for-the-badge&logo=openai)](./AI_POLICY.md) [![Built with Gemini](https://img.shields.io/badge/Built%20with-Gemini-4285F4?style=for-the-badge&logo=google-gemini)](https://gemini.google.com/)

# THz Data Visualizer v6.4

## 1. Wprowadzenie

**THz Data Visualizer** to zaawansowana aplikacja desktopowa napisana w języku Python, wykorzystująca bibliotekę Tkinter do stworzenia interfejsu graficznego. Została zaprojektowana specjalnie do wizualizacji, analizy i przetwarzania danych dwuwymiarowych pochodzących z eksperymentów spektroskopii w dziedzinie czasu (Time-Domain Spectroscopy), ze szczególnym uwzględnieniem spektroskopii terahercowej (THz-TDS).

Aplikacja umożliwia użytkownikom interaktywne badanie sygnałów w dziedzinie czasu, przeprowadzanie szybkiej transformacji Fouriera (FFT) w celu analizy spektralnej w dziedzinie częstotliwości oraz stosowanie zaawansowanych technik cyfrowego przetwarzania sygnałów w celu redukcji szumów i ekstrakcji kluczowych parametrów fizycznych.

## 2. Architektura Aplikacji i Funkcjonalności

Interfejs użytkownika został podzielony na trzy główne zakładki, grupujące funkcje w sposób logiczny i intuicyjny.

### 2.1. Zakładka: Źródła Danych

Moduł odpowiedzialny za zarządzanie danymi wejściowymi.
- **Import z plików `.txt`**: Umożliwia wczytanie wielu plików tekstowych zawierających dane w formacie dwukolumnowym (czas, amplituda). Parser automatycznie ignoruje linie nagłówka i komentarzy (rozpoczynające się od `#`).
- **Automatyczne ładowanie z `wyniki.xlsx`**: Aplikacja przy starcie automatycznie skanuje i ładuje arkusze z pliku `wyniki.xlsx`, co ułatwia pracę z wcześniej przetworzonymi danymi.
- **Zarządzanie widocznością**: Każdy wczytany sygnał posiada dedykowany checkbox, pozwalający na dynamiczne włączanie i wyłączanie jego widoczności na wykresie.
- **Operacje wsadowe**: Przyciski "Zaznacz wszystkie" i "Odznacz wszystkie" pozwalają na szybkie zarządzanie widocznością wszystkich arkuszy z pliku Excel.

### 2.2. Zakładka: Opcje Wykresu

Narzędzia do personalizacji i manipulacji wizualizacją.
- **Wybór aktywnego sygnału**: Lista rozwijana (ComboBox) pozwala na wybór jednego sygnału, który staje się referencją dla operacji analitycznych i edycyjnych.
- **Skalowanie i edycja**: Możliwość mnożenia amplitudy sygnału przez dowolny współczynnik, zmiana etykiety (legendy) oraz koloru linii.
- **Konfiguracja wizualna**: Pełna kontrola nad widocznością legendy oraz siatki pomocniczej (kolor, styl, grubość linii).
- **Automatyczny zoom**: Funkcja `Włącz auto-zoom na impuls` automatycznie centruje widok na głównym impulsie terahercowym, identyfikując obszar o największej zmianie sygnału.

### 2.3. Zakładka: Statystyka i Przetwarzanie

Zaawansowane narzędzia do analizy numerycznej i cyfrowego przetwarzania sygnałów.
- **Podstawowe statystyki**: Automatyczne obliczanie i wyświetlanie kluczowych parametrów dla aktywnego sygnału: wartości maksymalnej (Max), minimalnej (Min), średniej arytmetycznej (Średnia) oraz położenia w czasie piku o maksymalnej amplitudzie (Pozycja Piku).
- **Wygładzanie sygnału**: Implementacja czterech algorytmów filtracji cyfrowej w celu redukcji szumów.
- **Transformacja Fouriera (FFT)**: Przełącza widok z dziedziny czasu na dziedzinę częstotliwości, prezentując widmo amplitudowe sygnału.
- **Histogram Amplitud**: Generuje histogram rozkładu wartości amplitudy, co jest użyteczne w analizie statystycznej szumu.

## 3. Opis Metod Przetwarzania i Analizy Danych

### 3.1. Interaktywna Analiza Różnicowa

Aplikacja umożliwia precyzyjne pomiary różnic w dziedzinie czasu i amplitudy za pomocą interaktywnych znaczników. Użytkownik może umieścić na wykresie dwa znaczniki, a system automatycznie obliczy:

- **Różnicę czasu (Δt)**: Bezwzględna różnica między położeniami dwóch znaczników na osi czasu.
  $$ \Delta t = |t_2 - t_1| $$
- **Różnicę amplitudy (Δy)**: Bezwzględna różnica wartości sygnału w punktach odpowiadających znacznikom.
  $$ \Delta y = |y(t_2) - y(t_1)| $$

### 3.2. Normalizacja Amplitudy

Funkcja ta służy do porównywania kształtów i cech czasowych sygnałów o różnej mocy. Proces skaluje wszystkie widoczne sygnały względem wybranego sygnału referencyjnego ($S_{\text{ref}}$). Współczynnik skali $k_i$ dla każdego sygnału $S_i$ jest obliczany jako stosunek maksymalnej wartości bezwzględnej amplitudy sygnału referencyjnego do maksymalnej wartości bezwzględnej amplitudy sygnału normalizowanego:

$$ k_i = \frac{\max(|S_{\text{ref}}|)}{\max(|S_i|)} $$

Przeskalowany sygnał $S'_{i}$ jest dany wzorem:

$$ S'_{i}(t) = S_i(t) \cdot k_i $$

### 3.3. Algorytmy Wygładzania Sygnału (Filtracja Cyfrowa)

Redukcja szumów jest kluczowym etapem w przetwarzaniu danych eksperymentalnych. Aplikacja implementuje cztery fundamentalne filtry cyfrowe.

#### 3.3.1. Filtr Medianowy (Median Filter)

Jest to nieliniowy filtr cyfrowy, szczególnie efektywny w usuwaniu szumów impulsowych (typu "sól i pieprz") przy jednoczesnym zachowaniu ostrości krawędzi sygnału. Działanie filtru polega na zastąpieniu wartości każdej próbki $x[i]$ medianą wartości w jej lokalnym otoczeniu o rozmiarze $N = 2k+1$:

$$ y[i] = \text{median}(x[i-k], \dots, x[i], \dots, x[i+k]) $$

#### 3.3.2. Filtr Savitzky-Golay

To zaawansowany filtr, który dopasowuje lokalnie fragment sygnału do wielomianu niskiego rzędu metodą najmniejszych kwadratów. Dzięki temu znacznie lepiej niż prosta średnia krocząca zachowuje kształt, szerokość i amplitudę pików. Jego implementacja opiera się na funkcji `scipy.signal.savgol_filter`.

#### 3.3.3. Filtr Gaussa (Gaussian Filter)

Filtr ten wykorzystuje splot sygnału z funkcją Gaussa, co prowadzi do bardzo efektywnego wygładzenia. Stopień wygładzenia jest kontrolowany przez odchylenie standardowe ($\sigma$) funkcji Gaussa. Jednowymiarowa funkcja Gaussa jest zdefiniowana jako:

$$ G(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{x^2}{2\sigma^2}} $$

Większa wartość $\sigma$ (w aplikacji kontrolowana parametrem "Okno/Siła") skutkuje silniejszym rozmyciem i wygładzeniem sygnału. Implementacja bazuje na `scipy.ndimage.gaussian_filter1d`.

#### 3.3.4. Średnia Krocząca (Moving Average)

Jest to prosty filtr dolnoprzepustowy typu FIR (o skończonej odpowiedzi impulsowej). Każda próbka sygnału wyjściowego $y[i]$ jest średnią arytmetyczną $N$ ostatnich próbek sygnału wejściowego $x[i]$:

$$ y[i] = \frac{1}{N} \sum_{j=0}^{N-1} x[i-j] $$

### 3.4. Szybka Transformacja Fouriera (FFT)

Analiza w dziedzinie częstotliwości jest kluczowa w spektroskopii. Aplikacja transformuje sygnał z dziedziny czasu $E(t)$ do dziedziny częstotliwości $E(f)$ za pomocą Dyskretnej Transformaty Fouriera (DFT), która jest obliczana z wykorzystaniem wydajnego algorytmu FFT (`scipy.fft.fft`).

Dla sygnału dyskretnego $x_n$ składającego się z $N$ próbek, DFT jest zdefiniowana jako:

$$ X_k = \sum_{n=0}^{N-1} x_n \cdot e^{-i \frac{2\pi}{N} kn} $$

gdzie $k$ jest indeksem częstotliwości, a $i$ jest jednostką urojoną.

Oś częstotliwości jest obliczana za pomocą funkcji `scipy.fft.fftfreq`. Wynikowe widmo amplitudowe jest skalowane w celu uniezależnienia go od liczby punktów pomiarowych i jest zdefiniowane jako:

$$ A(f_k) = \frac{2}{N} |X_k| $$

Wynik jest prezentowany dla dodatnich częstotliwości ($f_k \ge 0$), a oś odciętych jest wyskalowana w jednostkach Teraherców (THz).

## 4. Instrukcja Użytkowania

### 4.1. Zależności

Do poprawnego działania aplikacji wymagane są następujące biblioteki:
- Python 3.x
- Tkinter (standardowo dołączany do Pythona)
- Pandas
- NumPy
- SciPy
- Matplotlib

### 4.2. Uruchomienie

Aby uruchomić aplikację, należy wykonać poniższą komendę w terminalu, znajdując się w głównym folderze projektu:
```bash
python appDODATKOWE.py
```

## 5. Diagnostyka

Aplikacja automatycznie generuje plik `app_log.txt` w głównym katalogu. Plik ten zawiera chronologiczny zapis kluczowych operacji wykonywanych przez użytkownika oraz szczegółowe informacje o ewentualnych błędach. Jest on nadpisywany przy każdym uruchomieniu i stanowi cenne narzędzie do diagnostyki problemów.
