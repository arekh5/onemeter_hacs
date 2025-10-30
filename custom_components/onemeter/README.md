\# OneMeter OM9613 Integration for Home Assistant



\*\*Opis:\*\*  

Integracja monitoruje zużycie energii i moc chwilową z licznika \*\*OneMeter OM9613\*\* poprzez bramkę \*\*GL-S10\*\*, używając własnego serwera MQTT.



\*\*Instrukcja bramki GL-S10:\*\*  

https://onemeter.com/pl/docs/gateway/gl-s10/installation/  



\*\*Zmiana względem producenta:\*\*  

\- Dane przesyłane na własny broker MQTT w Home Assistant zamiast serwera OneMeter.



\*\*Wymagania HA:\*\*

\- Home Assistant 2023.x lub nowszy

\- HACS (opcjonalnie)

\- Włączony broker MQTT w HA (np. Mosquitto)



\*\*Sensory w HA:\*\*

OneMeter

├─ onemeter\_om9613\_energy\_kwh

├─ onemeter\_om9613\_power\_kw

└─ onemeter\_om9613\_last\_update





\*\*Konfiguracja integracji w GUI HA:\*\*

\- Broker (IP lub hostname)

\- Port (1883 domyślnie)

\- Login / Hasło

\- max\_power\_kw – maksymalna moc chwilowa (domyślnie 20 kW)

\- window\_seconds – okno czasowe do liczenia mocy chwilowej (domyślnie 60 s)



