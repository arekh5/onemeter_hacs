# 🧭 OneMeter – Home Assistant Integration (v2.0.63)

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter przez MQTT i prezentowanie ich w Home Assistant. Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🌟 Najważniejsze zmiany w v2.0.63 (Korekta Statystyk Długoterminowych)

Ta wersja wprowadza szybką poprawkę w celu zapewnienia prawidłowego śledzenia statystyk długoterminowych.

* **FIX: Klasa Stanu Prognozy ✅:** Przywrócono atrybut `_attr_state_class = SensorStateClass.MEASUREMENT` dla sensora **'OneMeter Prognoza miesięczna'**. Rozwiązuje to błąd Home Assistant zgłaszający brak klasy stanu i umożliwia wznowienie śledzenia długoterminowych statystyk i poprawną wizualizację w panelu Energy.
* **Stabilność Po Restarcie 🛡️:** Utrzymana stabilność po usunięciu problematycznego kodu asynchroniczności (z poprzedniej wersji 2.0.62).

---

## 🚀 Instalacja przez HACS (Rekomendowana)

1.  Upewnij się, że masz zainstalowany [HACS](https://hacs.xyz/).
2.  Dodaj to repozytorium jako **"Custom Repository"** w HACS (Typ: Integracja).
3.  Zainstaluj integrację **OneMeter** w HACS.
4.  Zrestartuj Home Assistant.
5.  Dodaj integrację przez interfejs: **Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter**.

---

## ⚙️ Sensory Tworzone przez Integrację

Integracja automatycznie utworzy następujące sensory (w przykładzie użyto domyślnego `device_id`: `om9613`):

| Nazwa | Unique ID | Unit of Measurement | Klasa urządzenia | State Class | Opis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OneMeter Energy** | `om9613_energy_kwh` | `kWh` | `energy` | `total_increasing` | **Trwały** licznik całkowitego zużycia energii. |
| **OneMeter Power** | `om9613_power_kw` | `kW` | `power` | `measurement` | Obliczona i uśredniona moc chwilowa (aktualizowana po każdym impulsie). |
| **OneMeter Monthly Forecast** | `om9613_monthly_forecast_kwh` | `kWh` | (Brak) | `measurement` | **Prognozowane** zużycie energii w bieżącym miesiącu (stan trwały). |

---

## 🔧 Parametry Konfiguracyjne (Opcje)

Wszystkie parametry można edytować po instalacji: **Ustawienia → Urządzenia i usługi → OneMeter → Opcje**.

| Opcja | Domyślna | Opis |
| :--- | :--- | :--- |
| **Initial kWh** | `0.0` | Początkowa wartość licznika (używana tylko przy pierwszej instalacji lub odzyskiwaniu stanu). |
| **Impulses per kWh** | `1000` | Stała KWh/impuls dla Twojego licznika. |
| **Max Power (kW)** | `20.0` | Maksymalna akceptowalna moc (do filtrowania szumów). |
| **Power Average Window** | `2` | Liczba impulsów używanych do obliczenia średniej mocy (minimalizuje wahania). |
| **Power Timeout (seconds)** | `300` | Po ilu sekundach bez impulsu moc zostanie ustawiona na `0.0 kW`. |

## 🧾 Struktura repozytorium (v2.0.63)

custom_components/onemeter/
 ├─ init.py
 ├─ manifest.json
 ├─ config_flow.py
 ├─ sensor.py
 ├─ translations/
 │ ├─ en.json
 │ └─ pl.json
 └─ README.md