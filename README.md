# 🧭 OneMeter – Home Assistant Integration

Integracja **OneMeter** umożliwia odczyt danych z urządzenia OneMeter bezpośrednio w Home Assistant.  
Została przygotowana z myślą o łatwej instalacji przez **HACS** (Home Assistant Community Store).

---

## 🖼️ Zrzut ekranu

Poniżej przykładowy widok integracji OneMeter w Home Assistant:  

![OneMeter screenshot](https://raw.githubusercontent.com/arekh5/onemeter-hacs/main/docs/screenshot.png)


---

## 🚀 Instalacja przez HACS

1. Upewnij się, że masz zainstalowany [HACS](https://hacs.xyz/).
2. W Home Assistant otwórz:
   **HACS → Integrations → ... (trzy kropki w prawym górnym rogu) → Custom repositories**
3. W okienku, które się otworzy:
   - W polu **Repository** wpisz:
     ```
     https://github.com/arekh5/onemeter-hacs
     ```
   - Wybierz typ: `Integration`
   - Kliknij **Add**
4. Wyszukaj integrację **OneMeter** w HACS i zainstaluj ją.
5. Po instalacji uruchom ponownie Home Assistant.
6. Dodaj integrację przez interfejs:
   **Ustawienia → Urządzenia i usługi → Dodaj integrację → OneMeter**

---

## 🧰 Ręczna instalacja (alternatywnie)

Jeśli nie używasz HACS, możesz dodać integrację ręcznie:

1. Pobierz najnowszą wersję z sekcji [Releases](https://github.com/arekh5/onemeter-hacs/releases).
2. Rozpakuj folder `custom_components/onemeter` do katalogu:
   ```
   /config/custom_components/onemeter
   ```
   (Upewnij się, że struktura wygląda tak: `/config/custom_components/onemeter/manifest.json` itd.)
3. Uruchom ponownie Home Assistant.
4. Dodaj integrację z listy dostępnych.

---

## 🧾 Struktura repozytorium

```
custom_components/onemeter/
├─ __init__.py
├─ manifest.json
├─ config_flow.py
├─ sensor.py
├─ translations/
│  ├─ en.json
│  └─ pl.json
└─ README.md
```

---

## 🛠️ Wymagania

- Home Assistant 2023.0 lub nowszy  
- Python 3.11 lub nowszy  
- Zainstalowany [HACS](https://hacs.xyz/) (jeśli instalujesz przez HACS)

---

## 💡 Pomoc / Zgłaszanie problemów

Jeśli napotkasz błędy lub masz pomysły na ulepszenia, zgłoś issue tutaj:  
👉 [https://github.com/arekh5/onemeter-hacs/issues](https://github.com/arekh5/onemeter-hacs/issues)

---

**Autor:** [@arekh5](https://github.com/arekh5)  
**Licencja:** MIT  
