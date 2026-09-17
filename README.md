# Bank til Tripletex

Gjør kontoutskrifter fra nettbanken om til en **Mamut GBAT10**-importfil for Tripletex.

Støtter Nordea, DNB/Sbanken, Sparebank1/Eika og Handelsbanken.
Hver transaksjon blir ett bilag: `1920 Bank` mot `1909 Diverse motpost`.

## Innhold

| Fil | Hva det er |
|---|---|
| `index.html` | Hele verktøyet — én selvstendig fil, ingen avhengigheter |
| `convert_to_gbat10.py` | Samme konvertering som kommandolinjeverktøy |
| `lag-testfiler.py` | Genererer de syntetiske testfilene |
| `test.js` | Regresjonstest — `node test.js` |
| `testfiler/` | Syntetiske testfiler — **alle data er oppdiktet** |

## Personvern

Filen brukeren velger **leses i nettleseren og forlater aldri maskinen**.
Ingen opplasting, ingen server, ingen analyse, ingen informasjonskapsler.

Siden setter `Content-Security-Policy: connect-src 'none'`, som gjør at den
*teknisk ikke kan* sende data noe sted — det er håndhevet av nettleseren,
ikke bare et løfte i teksten.

> **Ekte bankutskrifter skal aldri inn i dette repoet.**
> De ligger i `../bankdata/`, utenfor git. `.gitignore` er satt opp som
> sikkerhetsnett, men den er siste forsvarslinje — ikke den første.

## Bruk

Åpne https://soranni.github.io/bank-til-tripletex/ — eller `index.html` lokalt.
Ingen installasjon.

Kommandolinje:

```bash
python3 convert_to_gbat10.py "kontoutskrift.csv" ut.csv
```

## Testing

```bash
python3 lag-testfiler.py   # regenerer testfilene
node test.js               # kjører regresjonstesten
```

`test.js` kjører den faktiske koden fra `index.html` mot hver testfil med en
DOM-stub, og sjekker format, antall transaksjoner, farge på kontrollbanneret,
forventede merknader og at hvert bilag balanserer til null.

Åpne så `index.html` og dra inn hver testfil:

| Fil | Forventet resultat |
|---|---|
| `demo-sparebank1-gyldig.csv` | ✅ Grønt banner, 12 transaksjoner |
| `test-1-ukjent-bank.csv` | ⚠️ Fant ingen transaksjoner — format ikke gjenkjent |
| `test-2-ingen-transaksjoner.csv` | ⚠️ Fant ingen transaksjoner — men format *gjenkjent* |
| `test-3-excel-lagret.csv` | ✅ Leses nå — Excel beholdt semikolon, men fjernet hermetegn |
| `test-4-nytt-kolonnenavn.csv` | ✅ Leses nå — «Bokføringsdato» i stedet for «Bokført dato» |
| `test-7-excel-komma.csv` | ⚠️ Egen forklaring: komma kolliderer med desimaltegnet |
| `test-5-avvik-i-sum.csv` | 🔴 Rødt banner — summen matcher ikke bankens sluttsummer |
| `test-6-uleselige-linjer.csv` | ⚠️ Merknad: «2 linjer med dato ble ikke lest inn» |

Skillet mellom test-1 og test-2 er poenget: «ikke gjenkjent» betyr ny/ukjent
bank, mens «Sparebank1/Eika» + null transaksjoner betyr at filen var tom.

## Feilsøking uten konsoll

Brukeren er regnskapsfører, ikke utvikler. Feil vises derfor i selve siden,
med en **📋 Kopier feildetaljer**-knapp. Rapporten inneholder versjonsnummer,
filnavn, størrelse, oppdaget format og de fem første linjene i filen — nok
til å stille diagnose uten å be om selve bankfilen.

## Åpne spørsmål

**Mva-avhukingen ved import (fjernet 17.09.2026).**
Instruksjonene ba tidligere brukeren huke av «La Tripletex generere
mva-posteringene». Den er tatt bort, fordi den etter alt å dømme er uten
effekt her: GBAT10-filen setter mva-kode `1` — altså ingen mva — på samtlige
linjer, og motposten er `1909 Diverse motpost`. Mva oppstår først når 1909
omposteres videre til resultatkonti, og det skjer manuelt i Tripletex etterpå,
ikke ved importen.

Dette er en regnskapsfaglig vurdering som **ikke er bekreftet med
regnskapsfører**. Viser det seg at avhukingen faktisk trengs, legg steget inn
igjen i `index.html` (lista under «Slik importerer du i Tripletex») og i
utskriften fra `convert_to_gbat10.py`.

## Konto og motkonto

Standard er **1920 Bank** mot **1909 Diverse motpost**. Begge kan endres i
steg 3 — nødvendig når klienten har flere bankkonti, ellers havner både
driftskonto og skattetrekkskonto på 1920. «Annet kontonummer …» gir fritekst
for kontoplaner uten forhåndsvalg. Ufullstendig inntasting faller tilbake til
standard, så filen aldri blir ugyldig underveis.

Brukes andre konti enn standard, kommer de med i filnavnet —
`host-tattoo-as_2026-08_1921-1999_gbat10.csv`. Uten det ville flere varianter
av samme måned fått identisk navn og blitt umulige å skille i nedlastingsmappa.

## Når banken ikke gjenkjennes

Feiler gjenkjenningen, tilbyr siden **«Sett opp kolonnene selv»**. Da vises de
ti første radene i filen med et nedtrekk over hver kolonne — Dato, Tekst,
Inn, Ut eller Beløp (+/−). Skilletegn og første datarad gjettes automatisk,
og kolonnenavn gjenkjennes på både norsk og engelsk.

Det betyr at en ny bank kan tas i bruk uten kodeendring. Datoer leses som
`03.08.2026`, `2026-08-03` og `3/8-2026`; beløp som både `1.234,56` og
`1,234.56`.

## Merknader til regnskapsføreren

Steg 2 viser en «Verdt å sjekke»-liste når noe fortjener et blikk:

* **Linjer som ikke ble lest.** Parserne hopper over rader de ikke forstår.
  Antall datolinjer i filen sammenlignes med antall leste transaksjoner, så
  en tapt rad aldri forsvinner i stillhet.
* **Helt like poster** — samme dato, tekst og beløp.
* **Samme dato og beløp, ulik tekst.** Ser ut som dobbeltføring, er det
  sjelden. To Visa-trekk på 304 kr samme dag er som regel to kjøp.
* **Saldo etter import.** Banken oppgir inn- og utgående saldo, så siden
  sier hva konto 1920 skal stå i — en fasit å avstemme mot.
* **Årsskifte.** Et avsluttet regnskapsår tar ikke imot nye bilag.

## Kontrollsum

Flere banker skriver sine egne sluttsummer øverst i filen. Finnes de, leser
siden dem og kryssjekker mot det konverteringen faktisk fant:

* **Grønt** — identisk med bankens sluttsummer
* **Rødt** — avvik, med begge tallsett og beskjed om ikke å importere
* **Grått** — banken oppgir ingen sluttsummer, kan ikke kryssjekkes
