# 🧭 OneMeter – Home Assistant Integration (v2.0.6)

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter przez MQTT i prezentowanie ich w Home Assistant. Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🌟 Najważniejsze zmiany w v2.0.6 (Krytyczna Aktualizacja)

Ta wersja wprowadza **fundamentalne ulepszenia stabilności i funkcjonalności**, zmieniając całkowicie architekturę integracji na nowoczesny standard Home Assistant (HA Entity + DataUpdateCoordinator):

* **TRWAŁA PROGNOZA MIESIĘCZNA (KLUCZOWA ZMIANA):** Nowa encja `OneMeter Monthly Forecast` korzysta z **RestoreEntity**. Stan początkowy (zużycie na początku miesiąca) jest teraz **trwale zapisywany w bazie HA** i odzyskiwany po restarcie. **Prognoza nie resetuje się już do 0** po ponownym uruchomieniu Home Assistant.
* **Architektura Asynchroniczna:** Pełna refaktoryzacja na **HA Entity** z Koordynatorem (Event-Driven), co zwiększa stabilność i zgodność z przyszłymi wersjami HA.
* **Poprawki Stabilności:**
    * Usunięto błąd przestarzałej składni `config_flow` (Deprecation fix).
    * Usunięto błędy ładowania platformy (`ImportError`, `NotImplementedError`).
* **Optymalizacja Szybkości:** Domyślne wartości przyspieszone: interwał aktualizacji sensora do **5s**, a okno uśredniania do **2** ostatnich odczytów.

> ⚠️ **WAŻNE:** Ze względu na fundamentalną zmianę architektury (z Async Executor Job na HA Entity), po aktualizacji do wersji v2.0.x **WYMAGANE JEST USUNIĘCIE I PONOWNE DODANIE INTEGRACJI** w Home Assistant, aby uniknąć błędów ładowania!

---

## 🚀 Instalacja przez HACS (Rekomendowana)

1.  Upewnij się, że masz zainstalowany [HACS](https://hacs.xyz/).
2.  W Home Assistant otwórz:
    **HACS → Integrations → ... (trzy kropki w prawym górnym rogu) → Custom repositories**
3.  W okienku, które się otworzy:
    -   W polu **Repository** wpisz adres swojego repozytorium GitHub (np. `https://github.com/arekh5/onemeter-hacs`)
    -   Wybierz typ: `Integration`
    -   Kliknij **Add**
4.  Wyszukaj integrację **OneMeter** w HACS i zainstaluj ją.
5.  Po instalacji **uruchom ponownie Home Assistant.**
6.  Dodaj integrację przez interfejs: **Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter**.

---

## ⚙️ Sensory Tworzone przez Integrację

Integracja automatycznie utworzy następujące sensory:

| Nazwa | Unique ID | Unit of Measurement | Klasa urządzenia | State Class | Opis |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **OneMeter Energy** | `om9613_energy_kwh` | `kWh` | `energy` | `total_increasing` | Licznik całkowitego zużycia energii. |
| **OneMeter Power** | `om9613_power_kw` | `kW` | `power` | `measurement` | Obliczona i uśredniona moc chwilowa. |
| **OneMeter Monthly Forecast** | `om9613_forecast_kwh` | `kWh` | `energy` | `measurement` | **Prognozowane** zużycie energii w bieżącym miesiącu. **Stan jest trwały!** |

**Parametry Konfiguracyjne (Opcje)**

Wszystkie parametry można edytować po instalacji: **Ustawienia → Urządzenia i usługi → OneMeter → Opcje**.

| Opcja | Domyślna v2.0.6 | Opis |
| :--- | :--- | :--- |
| **Impulses per kWh** | `1000` | Stała KWh/impuls dla Twojego licznika. |
| **Max Power (kW)** | `20` | Maksymalna akceptowalna moc chwilowa. |
| **Power Update Interval (s)** | **`5`** | Interwał odświeżania encji mocy w HA (zmniejszony z 15s). |
| **Power Average Window** | **`2`** | Rozmiar bufora do wygładzania mocy (zmniejszony z 5). |
| **Power Timeout Seconds** | `300` | Czas (w sekundach), po którym brak impulsu oznacza reset mocy do **0.0 kW**. |

---

## 🧾 Struktura repozytorium (v2.0.6)

custom_components/onemeter/
 ├─ init.py
 ├─ manifest.json
 ├─ config_flow.py
 ├─ sensor.py
 ├─ translations/
 │ ├─ en.json
 │ └─ pl.json
 └─ README.md