
# Kreiranje i implementacija custom UDP protokola za slanje video frame-ova
## Pripremili: Mladen Lazić i Smajlović Admir

Ovaj projekat implementira real-time video streaming sistem zasnovan na UDP transportu sa custom aplikacionim protokolom. Sistem omogućava prenos video slike sa kamere, prikaz u web pregledniku i praćenje performansi kroz detaljne metrike.

Ovaj sistem omogućava: 
- Video prijenos u realnom vremenu
- Web prikaz videa i metrika u browser-u

# Kako radi ovaj custom UDP protokol

UDP sam po sebi ne garantuje redoslijed niti isporuku paketa. Zbog toga je "iznad" UDP-a implementiran custom protokol koji svakom paketu dodaje strukturu, identifikaciju frame-a i vremensku oznaku.

Sistem se sastoji od dvije glavne komponente. 
- **udp_server** : Čita video sa kamere, enkodira frejmove u JPEG, fragmentira ih i šalje putem UDP-a.
- **web_client** : Prima UDP pakete, rekonstruiše video frejmove, prikazuje ih u web pregledniku i prikuplja metrike.

Komponente mogu raditi:

- Na jednom računaru preko run_all.py

- Na dva računara (server i klijent odvojeno)

## Struktura UDP paketa

Svaki UDP paket ima sljedeću strukturu:

-  HEADER (24 bajta)  

-  PAYLOAD (JPEG dio)

Header sadrži (protocol.py):

- version – verzija protokola

- flags – rezervisano (npr. key-frame u budućnosti)

- codec – tip podataka (JPEG)

- frame_id – identifikator frejma

- fragment_id – redni broj fragmenta

- total_fragments – ukupan broj fragmenata frejma

- timestamp_ms – vrijeme slanja frejma

- payload_size – veličina payloada

- checksum – jednostavna provjera integriteta

Ove informacije omogućavaju klijentu da pravilno rekonstruiše originalni frame.

## Tok slanja sa udp_server

1.Čita se frejm sa kamere (OpenCV).

2.Frejm se enkodira u JPEG.

3.JPEG se dijeli na fragmente fiksne veličine.

4.Za svaki fragment se:

- gradi header

- dodaje payload

- šalje UDP paket

5.Paralelno se šalju server metrike kao JSON poruke preko posebnog UDP porta.

## Tok prijema na web_client

1.UDP receiver prima pakete.

2.Header se parsira (parse_packet).

3.Fragmenti se grupišu po frame_id.

4.Kada stignu svi fragmenti:

- payloadi se spajaju u kompletan JPEG

- frame se označava kao dekodiran

5.Zadnji validni JPEG se prikazuje u browseru putem MJPEG streama (/video).


# Razlike u odnosu na UDP i TCP

## U odnosu na UDP:

| **UDP**                    | **Custom protokol**                |
| -------------------------- | ------------------------------ |
| Nema strukture             | Ima header i payload           |
| Nema konteksta             | Zna kojem frame-u pripada       |
| Nema metrika               | Omogućava mjerenje performansi |
| Teško rekonstruisati video | Moguća rekonstrukcija frame-a   |

## U odnosu na TCP:
| **TCP**                    | **Custom UDP protokol**   |
| -------------------------- | --------------------- |
| Garantuje isporuku         | Ne garantuje          |
| Veći latency               | Nizak latency         |
| Retransmisija              | Nema retransmisije    |
| Nije pogodan za live video | Pogodan za live video |


# Metrike koje se prikazuju

## Klijentske metrike

- Last FPS – FPS posljednjeg frame-a
- Avg FPS – prosječni FPS
- Last Delay (ms) – kašnjenje posljednjeg frame-a
- Avg Delay (ms) – prosječno kašnjenje
- Primljeni paketi – ukupan broj UDP paketa
- Primljeni bajtovi – ukupan broj bajtova
- Dekodirani frejmovi – broj uspješno rekonstruisanih frame-ova

## Serverske metrike

-	Server FPS – brzina slanja frame-ova
-	Bitrate (kbps) – trenutni bitrate
-	Paketi poslani – broj UDP paketa
-	Bajtovi poslani – količina poslanih podataka
-	Timestamp – vrijeme generisanja metrika








## Pokretanje programa na jednom računaru

Program se pokreće pmoću run_all.py koji u isto vrijeme pokreće
- udp_server
- web_client

Web UI je dostupan na
- http://127.0.0.1:8000


## Pokretanje programa na dva računara

1.Pokretanje web_client.py

```bash
  python web_client.py
```

2.Pokretanje udp_server.py

```bash
  python udp_server.py
```
U config.json moramo izmijeniti

```bash
  "client_ip": "IP_KLIJENTA"
```

