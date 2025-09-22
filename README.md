[![AI Assisted](https://img.shields.io/badge/AI-Assisted-blue?style=for-the-badge&logo=openai)](./AI_POLICY.md) [![Built with Gemini](https://img.shields.io/badge/Built%20with-Gemini-4285F4?style=for-the-badge&logo=google-gemini)](https://gemini.google.com/)

# DaVisu_THz v9.2

## 1. Wprowadzenie

**DaVisu_THz** (THz Data Visualizer) to zaawansowana aplikacja desktopowa napisana w języku Python, wykorzystująca biblioteki Tkinter i Matplotlib. Została zaprojektowana specjalnie do interaktywnej wizualizacji, analizy i przetwarzania danych dwuwymiarowych, z głównym przeznaczeniem dla wyników eksperymentów spektroskopii w dziedzinie czasu (Time-Domain Spectroscopy), w szczególności spektroskopii terahercowej (THz-TDS).

Aplikacja umożliwia użytkownikom płynne badanie sygnałów w domenie czasu, przeprowadzanie szybkiej transformacji Fouriera (FFT) w celu analizy spektralnej, a także stosowanie zaawansowanych technik cyfrowego przetwarzania sygnałów w celu redukcji szumów i ekstrakcji kluczowych parametrów fizycznych. Dzięki wbudowanemu systemowi historii operacji (Undo/Redo), analiza staje się elastyczna i bezpieczna.

## 2. Architektura i Funkcjonalności

Interfejs użytkownika został podzielony na trzy główne zakładki, grupujące funkcje w sposób logiczny i intuicyjny, a także wyposażony w globalne menu "Edycja" do zarządzania historią operacji.

### 2.1. Zakładka: Źródła Danych

Moduł odpowiedzialny za centralne zarządzanie danymi wejściowymi.
- **Dynamiczny import**: Umożliwia wczytywanie wielu plików tekstowych (`.txt`) oraz arkuszy z plików Excel (`.xlsx`) poprzez okna dialogowe.
- **Zunifikowana lista danych**: Wszystkie wczytane zbiory danych są prezentowane na jednej, wspólnej liście z checkboxami, pozwalając na dynamiczne włączanie i wyłączanie ich widoczności na wykresie.
- **Operacje wsadowe**: Przyciski "Zaznacz wszystkie" i "Odznacz wszystkie" pozwalają na szybkie zarządzanie widocznością wszystkich wczytanych danych.
- **Zarządzanie sesją**: Możliwość całkowitego wyczyszczenia przestrzeni roboczej jednym kliknięciem.

### 2.2. Zakładka: Opcje Wykresu

Narzędzia do personalizacji i manipulacji wizualizacją.
- **Wybór aktywnego sygnału**: Lista rozwijana (ComboBox) pozwala na wybór jednego sygnału, który staje się referencją dla operacji analitycznych i edycyjnych.
- **Skalowanie i edycja**: Możliwość mnożenia amplitudy sygnału przez dowolny współczynnik, zmiana etykiety (legendy) oraz koloru linii.
- **Nawigacja i widok**: W pełni funkcjonalny pasek narzędzi Matplotlib (z pominięciem zbędnych przycisków historii) do intuicyjnego powiększania i przesuwania widoku. Aplikacja inteligentnie zachowuje ustawienia widoku po operacjach odświeżających.
- **Konfiguracja wizualna**: Pełna kontrola nad widocznością legendy oraz siatki pomocniczej (kolor, styl, grubość linii).

### 2.3. Zakładka: Statystyka i Przetwarzanie

Zaawansowane narzędzia do analizy numerycznej i cyfrowego przetwarzania sygnałów.
- **Podstawowe statystyki**: Automatyczne obliczanie i wyświetlanie kluczowych parametrów dla aktywnego sygnału: wartości maksymalnej (Max), minimalnej (Min), średniej arytmetycznej (Średnia) oraz położenia w czasie piku o maksymalnej amplitudzie (Pozycja Piku).
- **Wygładzanie sygnału**: Implementacja czterech algorytmów filtracji cyfrowej, stosowanych na żądanie za pomocą dedykowanych przycisków.
- **Porównanie z oryginałem**: Funkcja wizualizacji oryginalnego, niewygładzonego sygnału (jako linia przerywana w jaśniejszym odcieniu tego samego koloru) obok jego wygładzonej wersji.
- **Transformacja Fouriera (FFT)**: Przełącza widok z dziedziny czasu na dziedzinę częstotliwości, prezentując widmo amplitudowe sygnału.
- **Histogram Amplitud**: Generuje histogram rozkładu wartości amplitudy, użyteczny w analizie statystycznej szumu.

### 2.4. System Undo/Redo
- **Pełna historia operacji**: Kluczowe działania modyfikujące dane (np. wczytywanie plików, skalowanie, zmiana koloru, wygładzanie) są zapisywane w historii.
- **Skróty klawiszowe**: Pełne wsparcie dla `Ctrl+Z` (Cofnij) i `Ctrl+Y` (Ponów).
- **Menu "Edycja"**: Dostęp do funkcji cofania i ponawiania z poziomu górnego menu aplikacji, z dynamicznie aktualizowanym stanem (aktywny/nieaktywny).

## 3. Metody Przetwarzania i Analizy Danych

### 3.1. Interaktywna Analiza Różnicowa

Aplikacja umożliwia precyzyjne pomiary różnic w dziedzinie czasu i amplitudy za pomocą interaktywnych znaczników (markery). Użytkownik może umieścić na wykresie dwa znaczniki, a system automatycznie obliczy:
- **Różnicę czasu ($\Delta t$)**: Bezwzględna różnica między położeniami dwóch znaczników na osi czasu.
$$
\Delta t = |t_2 - t_1|
$$
- **Różnicę amplitudy ($\Delta y$)**: Bezwzględna różnica wartości sygnału w punktach odpowiadających znacznikom.
$$
\Delta y = |y(t_2) - y(t_1)|
$$

### 3.2. Normalizacja Amplitudy

Funkcja ta służy do porównywania kształtów sygnałów o różnej mocy. Proces skaluje wszystkie widoczne sygnały względem wybranego sygnału referencyjnego ($S_{\text{ref}}$). Współczynnik skali $k_i$ dla każdego sygnału $S_i$ jest obliczany jako stosunek maksymalnej wartości bezwzględnej amplitudy sygnału referencyjnego do maksymalnej wartości bezwzględnej amplitudy sygnału normalizowanego:
$$
k_i = \frac{\max(|S_{\text{ref}}|)}{\max(|S_i|)}
$$
Przeskalowany sygnał $S'_{i}$ jest dany wzorem:
$$
S'_{i}(t) = S_i(t) \cdot k_i
$$

### 3.3. Algorytmy Wygładzania Sygnału

Aplikacja implementuje cztery fundamentalne filtry cyfrowe do redukcji szumów.

#### 3.3.1. Średnia Krocząca (Moving Average)
Prosty filtr dolnoprzepustowy. Każda próbka sygnału wyjściowego $y[i]$ jest średnią arytmetyczną $N$ sąsiednich próbek sygnału wejściowego $x[i]$ (implementacja z oknem wyśrodkowanym):
$$
y[i] = \frac{1}{N} \sum_{j=-(N-1)/2}^{(N-1)/2} x[i+j]
$$

#### 3.3.2. Filtr Medianowy (Median Filter)
Nieliniowy filtr cyfrowy, efektywny w usuwaniu szumów impulsowych. Działanie filtru polega na zastąpieniu wartości każdej próbki $x[i]$ medianą wartości w jej lokalnym otoczeniu o rozmiarze $N$:
$$
y[i] = \text{median}(x[i-k], \dots, x[i], \dots, x[i+k]), \quad N=2k+1
$$

#### 3.3.3. Filtr Savitzky-Golay
Zaawansowany filtr, który dopasowuje lokalnie fragment sygnału do wielomianu niskiego rzędu metodą najmniejszych kwadratów, co pozwala zachować kształt i szerokość pików.

#### 3.3.4. Filtr Gaussa (Gaussian Filter)
Filtr ten wykorzystuje splot sygnału z funkcją Gaussa, co prowadzi do efektywnego wygładzenia. Stopień wygładzenia jest kontrolowany przez odchylenie standardowe ($\sigma$) funkcji Gaussa $G(x)$:
$$
G(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{x^2}{2\sigma^2}}
$$

### 3.4. Szybka Transformacja Fouriera (FFT)

Aplikacja transformuje sygnał z dziedziny czasu $E(t)$ do dziedziny częstotliwości $E(f)$ za pomocą Dyskretnej Transformaty Fouriera (DFT), obliczanej z wykorzystaniem wydajnego algorytmu FFT. Dla sygnału dyskretnego $x_n$ DFT jest zdefiniowana jako:
$$
X_k = \sum_{n=0}^{N-1} x_n \cdot e^{-i \frac{2\pi}{N} kn}
$$
Wynikowe widmo amplitudowe jest skalowane w celu uniezależnienia go od liczby punktów pomiarowych:
$$
A(f_k) = \frac{2}{N} |X_k|
$$

## 4. Instrukcja Użytkowania

### 4.1. Zależności
- Python 3.x
- Tkinter (standardowo dołączany do Pythona)
- Pandas
- NumPy
- SciPy
- Matplotlib

Zależności można zainstalować za pomocą `pip`:
```bash
pip install pandas numpy scipy matplotlib
```

### 4.2. Uruchomienie
Aby uruchomić aplikację, należy zapisać kod jako plik `.py` (np. `app.py`) i wykonać poniższą komendę w terminalu:
```bash
python app.py
```

## 5. Diagnostyka

Aplikacja automatycznie generuje plik `app_log.txt` w głównym katalogu. Plik ten zawiera chronologiczny zapis kluczowych operacji oraz szczegółowe informacje o ewentualnych błędach.
