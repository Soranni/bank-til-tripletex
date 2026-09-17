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
python3 lag-testfiler.py
```

Åpne så `index.html` og dra inn hver testfil:

| Fil | Forventet resultat |
|---|---|
| `demo-sparebank1-gyldig.csv` | ✅ Grønt banner, 12 transaksjoner |
| `test-1-ukjent-bank.csv` | ⚠️ Fant ingen transaksjoner — format ikke gjenkjent |
| `test-2-ingen-transaksjoner.csv` | ⚠️ Fant ingen transaksjoner — men format *gjenkjent* |
| `test-3-excel-odelagt.csv` | ⚠️ Fant ingen transaksjoner (lagret på nytt i Excel) |
| `test-4-nytt-kolonnenavn.csv` | ⚠️ Fant ingen transaksjoner (banken døpte om kolonnen) |
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
