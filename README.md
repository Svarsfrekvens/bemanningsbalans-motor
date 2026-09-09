# Bemanningsbalans optimeringsmotor

En fristående optimeringstjänst för Bemanningsbalans. Motorn använder Google OR-Tools CP-SAT och kan kopplas till ett gränssnitt byggt i Lovable.

## Det motorn gör

- väljer arbetspass från verksamhetens godkända passmallar;
- placerar fasta insatser på angiven tid;
- flyttar flexibla insatser inom deras tillåtna tidsfönster;
- kräver en eller två olika medarbetare vid enkel- respektive dubbelbemanning;
- kontrollerar kompetens, nattbehörighet, frånvaro, dygnsvila och arbetstidsgränser;
- minimerar personalkostnad och väger även in kontinuitet och jämn arbetsbelastning;
- lämnar det befintliga schemat orört och returnerar ett separat förslag;
- granskar varje förslag med en fristående validator innan det skickas tillbaka.

## Starta lokalt

Windows: dubbelklicka på `starta-windows.bat`.

Mac/Linux:

```bash
chmod +x starta-mac-linux.sh
./starta-mac-linux.sh
```

Öppna `http://127.0.0.1:8000/docs` för att prova API:t.

## API

- `GET /api/health` visar om OR-Tools är installerat.
- `POST /api/optimize` räknar fram ett schemaförslag.
- `POST /api/validate` granskar ett befintligt eller manuellt ändrat schema.

Läs `LOVABLE-INTEGRATION.md` för kopplingen till Lovable.

## Vad som behöver göras före pilot

Modellen måste provas mot verkliga men avidentifierade scheman och SeKoia-underlag. Frösunda behöver fastställa alla regler, passmallar och prioriteringar. Regler som nio fridagar, helgtjänstgöring, lokala avtal och individuella villkor behöver läggas till och testas om de ska styra pilotens schema.

Motorn garanterar att ett returnerat förslag följer de regler som faktiskt finns i koden och passerar validatorn. Den kan inte garantera att alla verksamhetsregler är rätt beskrivna eller fullständiga utan verksamhetens granskning.
