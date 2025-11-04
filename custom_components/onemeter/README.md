\# OneMeter Energy (Niestandardowa Integracja HA) ⚡️



Niestandardowa integracja Home Assistant, która subskrybuje wiadomości MQTT z urządzenia OneMeter i oblicza \*\*Moc Chwilową (kW)\*\*.



\## ⚙️ Cechy Integracji



\* \*\*Precyzyjna Moc Chwilowa:\*\* Obliczenia mocy chwilowej są wykonywane na podstawie \*\*różnicy czasu ($\\Delta t$) między dwoma ostatnimi impulsami\*\*, używając wzoru $P = \\frac{3600}{k \\cdot t}$. Zapewnia to szybką i dokładną reakcję na zmiany obciążenia.

\* \*\*Wygładzanie (Averaging):\*\* Wykorzystuje konfigurowalny bufor (`power\_average\_window`) do uśredniania mocy, co zapewnia stabilniejszy odczyt sensora w Home Assistant.

\* \*\*Logika Zerowania Mocy:\*\* Posiada konfigurowalny timeout (`power\_timeout\_seconds`), po którym brak impulsów oznacza prawdziwe zerowe zużycie (0.0 kW), zamiast utrzymywania ostatniej znanej wartości w nieskończoność.

\* \*\*MQTT Discovery:\*\* Automatycznie rejestruje sensory w Home Assistant.



---



\## 💾 Instalacja za pomocą HACS



1\.  \*\*Dodaj Repozytorium:\*\* W Home Assistant przejdź do \*\*HACS\*\* > \*\*Integracje\*\*.

2\.  Kliknij \*\*trzy kropki\*\* w prawym górnym rogu (`⋮`) i wybierz \*\*Niestandardowe repozytoria\*\* (Custom repositories).

3\.  Wklej link do swojego repozytorium GitHub (`https://github.com/arekh5/onemeter\_hacs`).

4\.  Wybierz \*\*Typ kategorii\*\* jako \*\*Integracja\*\*.

5\.  Kliknij \*\*DODAJ\*\*.

6\.  Wyszukaj \*\*OneMeter\*\* w HACS i kliknij \*\*POBIERZ\*\*.

7\.  \*\*Uruchom ponownie Home Assistant.\*\* (Wymagane do załadowania nowej integracji).



---



\## 🔌 Konfiguracja (Uruchomienie Integracji)



1\.  W Home Assistant przejdź do \*\*Ustawienia\*\* > \*\*Urządzenia i usługi\*\*.

2\.  Kliknij \*\*Dodaj integrację\*\* i wyszukaj \*\*OneMeter\*\*.

3\.  Wprowadź wymagane parametry MQTT i opcjonalne parametry obliczeń.



| Parametr | Typ pola | Domyślna wartość | Opis |

| :--- | :--- | :--- | :--- |

| \*\*Broker MQTT\*\* | Wymagane | `127.0.0.1` | Adres IP/host brokera MQTT. |

| \*\*Port MQTT\*\* | Wymagane | `1883` | Port brokera MQTT. |

| \*\*MQTT User/Pass\*\* | Wymagane | `mqtt` | Dane uwierzytelniające do brokera MQTT. |

| \*\*Impulses per kWh\*\* | Opcjonalne | `1000` | Stała licznika ($k$ impulsów/kWh). |

| \*\*Max Power (kW)\*\* | Opcjonalne | `20` | Maksymalna akceptowalna moc chwilowa (bezpiecznik). |

| \*\*Power Update Interval\*\* | Opcjonalne | `15` | Jak często (w sekundach) stan sensora jest publikowany do HA. |

| \*\*Power Average Window\*\* | Opcjonalne | `5` | Rozmiar bufora do uśredniania (liczba ostatnich odczytów). |

| \*\*Power Timeout Seconds\*\* | Opcjonalne | `300` | Czas (w sekundach), po którym brak impulsu oznacza reset mocy do \*\*0.0 kW\*\*. |



---



\## 💡 Sensory Tworzone przez Integrację



Po poprawnej konfiguracji integracja automatycznie utworzy następujące sensory:



| Nazwa | Unique ID | Unit of Measurement | Klasa urządzenia |

| :--- | :--- | :--- | :--- |

| \*\*OneMeter Power\*\* | `om9613\_power\_kw` | `kW` | `power` |

| \*\*OneMeter Energy\*\* | `om9613\_energy\_kwh` | `kWh` | `energy` |

| \*\*OneMeter Timestamp\*\* | `om9613\_timestamp` | (Brak) | (Brak) |



---



\## ❓ Rozwiązywanie Problemów



Jeśli sensory nie pojawiają się lub nie aktualizują:



1\.  \*\*Sprawdź Logi:\*\* Włącz debugowanie dla domeny `onemeter` w logach Home Assistant, aby zobaczyć komunikaty dotyczące połączenia MQTT i przetwarzania wiadomości.

2\.  \*\*Połączenie MQTT:\*\* Upewnij się, że urządzenie OneMeter poprawnie publikuje dane na temat \*\*`onemeter/s10/v1`\*\* oraz że podane dane uwierzytelniające w konfiguracji HA są poprawne.

3\.  \*\*Zależności:\*\* Upewnij się, że biblioteka `paho-mqtt` została poprawnie zainstalowana (jest wymagana w `manifest.json`).

