# ⚡ OneMeter – Integracja z Home Assistant (Custom Component)

Integracja **OneMeter** umożliwia odczyt i wizualizację danych z licznika energii **OneMeter S10 / S10P** poprzez MQTT w Home Assistant.  
Dodatkowo integracja automatycznie oblicza **prognozę miesięcznego zużycia energii** i pozwala na **ręczne ustawienie bieżącego zużycia w danym miesiącu** – idealne przy restarcie HA lub wymianie urządzenia.

---

## 🚀 Funkcje

- ✅ Odczyt danych z urządzenia OneMeter przez MQTT (`onemeter/s10/v1`)
- ⚙️ Obsługa wielu urządzeń (identyfikacja po `MAC`)
- 📊 Trzy encje:
  - **sensor.onemeter_energy_kwh** – całkowite zużycie energii (kWh)
  - **sensor.onemeter_power_kw** – chwilowa moc (kW)
  - **sensor.onemeter_monthly_forecast_kwh** – prognoza zużycia miesięcznego (kWh)
- 💾 Trwałe przechowywanie stanu (HA Restore)
- 🔄 Automatyczna aktualizacja prognozy co godzinę
- 🧮 Pole **„Zużycie bieżące w miesiącu (kWh)”** – przydatne do ustawienia wartości początkowej przy restarcie

---

## 🧩 Instalacja

1. Skopiuj folder integracji do: /config/custom_components/onemeter/


Upewnij się, że w folderze znajdują się:
__init__.py
manifest.json
sensor.py
config_flow.py
README.md


2. Zrestartuj Home Assistant.

3. W Home Assistant przejdź do: Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter


4. Jeśli integracja się nie pojawia, wyczyść pamięć podręczną i odśwież stronę (CTRL+F5).

---

## ⚙️ Konfiguracja

### 🔧 Dane podstawowe
Podczas dodawania integracji podaj:
- **ID urządzenia** (np. `om9613`)
- **MAC urządzenia** (np. `E58D81019613`)
- **Temat MQTT** (np. `onemeter/s10/v1`)
- **Stan licznika początkowy (kWh)** – np. `1234.56`
- **Zużycie bieżące w miesiącu (kWh)** – np. `45.3` *(nowa funkcja!)*

### ⚙️ Parametry techniczne
- **Impulsy na kWh** – domyślnie `1000`
- **Maksymalna moc (kW)** – liczba całkowita, np. `25`
- **Okno uśredniania mocy** – domyślnie `2`
- **Limit braku impulsów (sekundy)** – po ilu sekundach braku impulsów moc = 0

---

## 📈 Prognoza miesięczna

Prognoza (`sensor.onemeter_monthly_forecast_kwh`) obliczana jest automatycznie:

\[
\text{Prognoza} = \frac{\text{Zużycie od początku miesiąca}}{\text{Upływ dni}} \times \text{Liczba dni w miesiącu}
\]

Przykład:  
Jeśli w połowie miesiąca zużyłeś 150 kWh, a miesiąc ma 30 dni → prognoza wyniesie ok. **300 kWh**.

Integracja:
- Automatycznie resetuje prognozę przy zmianie miesiąca
- Odzyskuje dane po restarcie HA
- Aktualizuje prognozę **co godzinę**
- Używa wartości z `monthly_usage_kwh`, jeśli brak danych impulsów

---

## 💡 Dostępne encje

| Encja | Opis | Jednostka | Klasa |
|-------|------|------------|--------|
| `sensor.onemeter_energy_kwh` | Całkowite zużycie energii | kWh | `total_increasing` |
| `sensor.onemeter_power_kw` | Chwilowa moc | kW | `measurement` |
| `sensor.onemeter_monthly_forecast_kwh` | Prognozowane zużycie miesięczne | kWh | `measurement` |

---

## 🔧 MQTT

**Odczyt danych:**  
Domyślny temat MQTT odbierany przez integrację: onemeter/s10/v1

**Publikacja danych do HA:**  
Przetworzony stan publikowany w: onemeter/energy/<device_id>/state

Przykład wiadomości:
```json
{
  "timestamp": "2025-11-04 18:30:12",
  "impulses": 1567321,
  "kwh": 1567.321,
  "power_kw": 1.85
}

🧠 Dodatkowe informacje

Integracja publikuje status MQTT (online / offline)

Dane prognozy aktualizują się co 60 minut

Wartość monthly_usage_kwh można później edytować w opcjach integracji

🧾 Historia wersji
Wersja	Zmiany
2.0.0	Pierwsza wersja integracji
2.0.5	Dodano uśrednianie mocy
2.0.51	Obsługa MQTT i impulsów
2.0.69	Automatyczna prognoza miesięczna
2.1.1	🆕 Dodano monthly_usage_kwh oraz max_power_kw jako int
❤️ Autor

Projekt: Integracja OneMeter do Home Assistant
Autor: arekh5
Licencja: MIT

📊 Przykładowy dashboard Lovelace

Możesz dodać prostą kartę energii w Home Assistant:

type: vertical-stack
cards:
  - type: entities
    title: Licznik OneMeter
    entities:
      - entity: sensor.onemeter_energy_kwh
        name: Zużycie całkowite
      - entity: sensor.onemeter_power_kw
        name: Moc chwilowa
      - entity: sensor.onemeter_monthly_forecast_kwh
        name: Prognoza miesięczna
  - type: history-graph
    entities:
      - entity: sensor.onemeter_energy_kwh
      - entity: sensor.onemeter_monthly_forecast_kwh
    hours_to_show: 72
    refresh_interval: 300

