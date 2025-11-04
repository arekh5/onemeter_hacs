# 🧭 OneMeter – Home Assistant Integration (v2.0.7)

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter przez MQTT i prezentowanie ich w Home Assistant. Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🌟 Najważniejsze zmiany w v2.0.7 (Poprawka Krytyczna)

Ta wersja wprowadza **poprawkę walidacji sensorów** Home Assistant:

* **Poprawka Walidacji Prognozy:** Usunięto konflikt `device_class: energy` z `state_class: measurement` dla sensora prognozy miesięcznej, usuwając błędy w logach HA.
* **Trwała Prognoza Miesięczna:** Encja `OneMeter Monthly Forecast` **nie resetuje się do 0 po restarcie** (zmiana wprowadzona w v2.0.6).
* **Architektura Asynchroniczna:** Pełna refaktoryzacja na **HA Entity** z Koordynatorem (Event-Driven), co zwiększa stabilność i zgodność z przyszłymi wersjami HA.

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
| **OneMeter Monthly Forecast** | `om9613_forecast_kwh` | `kWh` | (Brak) | `measurement` | **Prognozowane** zużycie energii w bieżącym miesiącu. **Stan jest trwały!** |

**Parametry Konfiguracyjne (Opcje)**

Wszystkie parametry można edytować po instalacji: **Ustawienia → Urządzenia i usługi → OneMeter → Opcje**.

| Opcja | Domyślna v2.0.7 | Opis |
| :--- | :--- | :--- |
| **Impulses per kWh** | `1000` | Stała KWh/impuls dla Twojego licznika. |
| **Max Power (kW)** | `20` | Maksymalna akceptowalna moc chwilowa. |
| **Power Update Interval (s)** | `5` | Interwał odświeżania encji mocy w HA. |
| **Power Average Window** | `2` | Rozmiar bufora do wygładzania mocy. |
| **Power Timeout Seconds** | `300` | Czas (w sekundach), po którym brak impulsu oznacza reset mocy do **0.0 kW**. |

---

## 🧾 Struktura repozytorium (v2.0.7)

custom_components/onemeter/
 ├─ init.py
 ├─ manifest.json
 ├─ config_flow.py
 ├─ sensor.py
 ├─ translations/
 │ ├─ en.json
 │ └─ pl.json
 └─ README.md