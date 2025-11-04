# 🧭 OneMeter – Home Assistant Integration (v2.0.12)

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter przez MQTT i prezentowanie ich w Home Assistant. Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🌟 Najważniejsze zmiany w v2.0.12 (Krytyczne Poprawki)

Ta wersja wprowadza kluczowe zmiany rozwiązujące problemy z resetowaniem stanu i komunikacją MQTT:

* **Trwałość Stanu Licznika (Persistence) ✅:** Sensor **Energy (kWh) nie resetuje się** po restarcie Home Assistant. Integracja odzyskuje ostatnią zapisaną wartość kWh.
* **Ponowna Publikacja Przetworzonego Stanu MQTT 📤:** Przywrócono funkcjonalność publikowania pełnego, przetworzonego JSON-a (z `kwh`, `power_kw`, `impulses`) na temacie:
    ```
    onemeter/energy/om9613/state
    ```
* **Stabilny Start MQTT ⏱️:** Subskrypcje i publikacja statusu (`online`/`offline`) są wykonywane **dopiero po pełnej inicjalizacji** wewnętrznego klienta MQTT w Home Assistant.
* **Usunięcie Błędów:** Rozwiązano błędy: `AttributeError: 'OneMeterCoordinator' object has no attribute 'async_remove_listener'` oraz `NotImplementedError: Update method not implemented`.

---

## 🚀 Instalacja przez HACS (Rekomendowana)

1.  Upewnij się, że masz zainstalowany [HACS](https://hacs.xyz/).
2.  W Home Assistant otwórz:
    **HACS → Integrations → ... (trzy kropki w prawym górnym rogu) → Custom repositories**
3.  W okienku, które się otworzy, podaj adres swojego repozytorium i wybierz typ: `Integration`.
4.  Wyszukaj integrację **OneMeter** w HACS i zainstaluj ją.
5.  Po instalacji **uruchom ponownie Home Assistant.**
6.  Dodaj integrację przez interfejs: **Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter**.

---

## ⚙️ Sensory Tworzone przez Integrację

Integracja automatycznie utworzy następujące sensory:

| Nazwa | Unique ID | Unit of Measurement | Klasa urządzenia | State Class | Opis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OneMeter Energy** | `om9613_energy_kwh` | `kWh` | `energy` | `total_increasing` | **Trwały** licznik całkowitego zużycia energii. |
| **OneMeter Power** | `om9613_power_kw` | `kW` | `power` | `measurement` | Obliczona i uśredniona moc chwilowa. |
| **OneMeter Monthly Forecast** | `om9613_forecast_kwh` | `kWh` | (Brak) | `measurement` | **Prognozowane** zużycie energii w bieżącym miesiącu (stan trwały). |

---

## 🔧 Parametry Konfiguracyjne (Opcje)

Wszystkie parametry można edytować po instalacji: **Ustawienia → Urządzenia i usługi → OneMeter → Opcje**.

| Opcja | Domyślna | Opis |
| :--- | :--- | :--- |
| **Impulses per kWh** | `1000` | Stała KWh/impuls dla Twojego licznika. |
| **Max Power (kW)** | `20` | Maksymalna akceptowalna moc chwilowa. |
| **Power Average Window** | `2` | Rozmiar bufora do uśredniania mocy. |
| **Power Timeout Seconds** | `300` | Czas (w sekundach), po którym brak impulsu oznacza reset mocy do **0.0 kW**. |

---

## 🧾 Struktura repozytorium (v2.0.12)

custom_components/onemeter/
 ├─ init.py
 ├─ manifest.json
 ├─ config_flow.py
 ├─ sensor.py
 ├─ translations/
 │ ├─ en.json
 │ └─ pl.json
 └─ README.md