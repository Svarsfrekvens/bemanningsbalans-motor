# Koppla motorn till Lovable

Motorn är en separat Python-tjänst. Lovable skickar grunddatan till `POST /api/optimize` och får tillbaka ett schemaförslag med status och valideringsresultat.

## Anrop från Lovable

```ts
const response = await fetch(`${OPTIMIZER_URL}/api/optimize`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${OPTIMIZER_TOKEN}`,
  },
  body: JSON.stringify({ data: bemanningsbalansState, seconds: 30 }),
});

const result = await response.json();

if (!response.ok) throw new Error(result.detail ?? "Optimeringen misslyckades");

// Visa result.schedule som ett förslag. Ersätt aldrig det befintliga schemat
// förrän verksamhetschefen uttryckligen godkänner förslaget.
```

`OPTIMIZER_TOKEN` ska ligga i en serverfunktion eller annan skyddad hemlighet. Lägg aldrig token i webbläsarkoden.

## Miljövariabler vid drift

- `BB_API_TOKEN`: en lång slumpmässig hemlighet.
- `BB_ALLOWED_ORIGINS`: Lovable-appens adress. Flera adresser separeras med kommatecken.

Exempel:

```text
BB_API_TOKEN=byt-till-en-lång-hemlighet
BB_ALLOWED_ORIGINS=https://din-app.lovable.app
```

Lovable bör anropa motorn via en serverfunktion. Då exponeras inte motorns token för användaren.

## Status som gränssnittet ska visa

- `OPTIMAL`: bevisat optimal inom modellens passmallar, tidssteg och mål.
- `FEASIBLE`: giltig lösning, men inte bevisat optimal inom tidsgränsen.
- `INFEASIBLE`: ingen lösning uppfyller alla hårda villkor.
- `UNKNOWN`: tiden tog slut utan att en lösning hittades.
- `MODEL_INVALID`: förslaget stoppades av den oberoende validatorn.

Motorn lättar aldrig tyst på de hårda reglerna.

## Obemannat behov

Täckning är ett tungt viktat mål, inte ett hårt villkor. Motorn bemannar så många
insatser som reglerna tillåter och redovisar resten i `schedule.uncovered`:

```json
{ "occurrenceId": "i12@2026-08-05", "name": "Morgonhjälp", "date": "2026-08-05", "minutes": 30, "count": 1 }
```

Gränssnittet ska visa dessa rader. Validatorn godkänner bara obemannat behov som
är öppet redovisat på det här sättet; odeklarerad brist är fortfarande ett fel.
