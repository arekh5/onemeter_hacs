# OneMeter Energy (Niestandardowa Integracja HA) ⚡️

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter bezpośrednio w Home Assistant. Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🚀 Instalacja przez HACS

1. Upewnij się, że masz zainstalowany [HACS](https://hacs.xyz/).
2. W Home Assistant otwórz:
   **HACS → Integrations → ... (trzy kropki w prawym górnym rogu) → Custom repositories**
3. W okienku, które się otworzy:
   - W polu **Repository** wpisz:
     ```
     [https://github.com/arekh5/onemeter-hacs](https://github.com/arekh5/onemeter-hacs)
     ```
   - Wybierz typ: `Integration`
   - Kliknij **Add**
4. Wyszukaj integrację **OneMeter** w HACS i zainstaluj ją.
5. Po instalacji **uruchom ponownie Home Assistant.**

---

## ⚙️ Konfiguracja i Parametry

Integracja wykorzystuje logikę opartą na **różnicy czasu ($t$) między impulsami** ($P = \frac{3600}{k \cdot t}$).

Dodaj integrację przez interfejs: **Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter**.

| Parametr | Typ pola | Domyślna wartość | Opis |
| :--- | :--- | :--- | :--- |
| **Broker MQTT** | Wymagane | `127.0.0.1` | Adres IP/host brokera MQTT. |
| **Port MQTT** | Wymagane | `1883` | Port brokera MQTT. |
| **MQTT User/Pass** | Wymagane | `mqtt` | Dane uwierzytelniające do brokera MQTT. |
| **Impulses per kWh** | Opcjonalne | `1000` | Stała licznika ($k$ impulsów/kWh). |
| **Max Power (kW)** | Opcjonalne | `20` | Maksymalna akceptowalna moc chwilowa (bezpiecznik). |
| **Power Update Interval** | Opcjonalne | `15` | Jak często (w sekundach) stan sensora jest publikowany do HA. |
| **Power Average Window** | Opcjonalne | `5` | Rozmiar bufora do **wygładzania** mocy chwilowej (liczba ostatnich odczytów). |
| **Power Timeout Seconds** | Opcjonalne | `300` | Czas (w sekundach), po którym brak impulsu oznacza reset mocy do **0.0 kW** (logika "ostatniej znanej mocy"). |

---

## 💡 Sensory Tworzone przez Integrację

Integracja automatycznie utworzy następujące sensory:

| Nazwa | Unit of Measurement | Klasa urządzenia | Opis |
| :--- | :--- | :--- | :--- |
| **OneMeter Power** | `kW` | `power` | Obliczona moc chwilowa (na podstawie $\Delta t$). |
| **OneMeter Energy** | `kWh` | `energy` | Licznik całkowitego zużycia energii. |
| **OneMeter Timestamp** | (Brak) | (Brak) | Ostatnia sygnatura czasowa odczytu. |

---

## 🧰 Ręczna instalacja (alternatywnie)

Jeśli nie używasz HACS, możesz dodać integrację ręcznie:

1. Pobierz najnowszą wersję z sekcji [Releases](https://github.com/arekh5/onemeter-hacs/releases).
2. Rozpakuj folder `custom_components/onemeter` do katalogu: /config/custom_components/onemeter
3. Uruchom ponownie Home Assistant.
4. Dodaj integrację z listy dostępnych.

---

## 🧾 Struktura repozytorium
custom_components/onemeter/
 ├─ init.py
 ├─ manifest.json
 ├─ config_flow.py
 ├─ sensor.py
 ├─ translations/
 │ ├─ en.json
 │ └─ pl.json
 └─ README.md

---

## 🛠️ Wymagania

- Home Assistant 2023.0 lub nowszy
- Python 3.11 lub nowszy
- Zainstalowany [HACS](https://hacs.xyz/) (jeśli instalujesz przez HACS)

---

## ❓ Pomoc / Zgłaszanie problemów

Jeśli napotkasz błędy lub masz pomysły na ulepszenia, zgłoś issue tutaj:
👉 [https://github.com/arekh5/onemeter-hacs/issues](https://github.com/arekh5/onemeter-hacs/issues)

---

**Autor:** [@arekh5](https://github.com/arekh5)
**Licencja:** MIT