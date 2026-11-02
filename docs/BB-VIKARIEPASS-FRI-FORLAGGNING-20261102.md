# BB – överlämning till motor/Codex/Cursor: fri förläggning av vikariepass

**Besluts-ID:** `BB-VIKARIEPASS-FRI-FORLAGGNING-20261102-v1`  
**Styrande källa:** [Bemanningsbibeln v16.20, 2 november 2026](https://github.com/Svarsfrekvens/balansera-bemanning/blob/main/docs/BEMANNINGSBIBELN.md), avsnitt 8c och 8d, acceptansfallen A34–A36, källnot K17.

## Aktuell samordning

Den ursprungliga vikariepassregeln från v16.18 gäller oförändrat. V16.19 tillför exakt tid och gemensamma tidsbegrepp i avsnitt 20 samt A37–A42. [Gemensam arbetsorder till C och L](https://github.com/Svarsfrekvens/balansera-bemanning/blob/main/docs/BB_NASTA_LEVERANS_20261102.md) och [huvudärende 22](https://github.com/Svarsfrekvens/balansera-bemanning/issues/22) samlar leveransen. [Motorärende 1](https://github.com/Svarsfrekvens/bemanningsbalans-motor/issues/1) länkar till faktisk motorgren; skapa inte en andra implementation här.

Fortsätt senaste lokala arbete enligt användarens senaste uttryckliga uppdrag om fördjupad analys. Återanvänd rättade begränsningar och bevara bästa kandidat som reserv. Den tidigare arbetsorderns begränsning till en avslutande sökomgång hindrar inte det senare uppdraget; följ den gemensamma arbetsorderns uppdaterade C-avsnitt. Samordna exportformat, tidsenheter, saknade värden, versionshantering och syntetiska kontraktsprov med L. Verkliga schemafiler, personuppgifter och lokala beslut stannar i skyddade underlag.

## Medicinering: precisering i v16.20

Bibelns avsnitt 2 och K19 styr `BB-MEDICINERING-INTERVALL-20261102-v1`. Medicinering med angivet utförandeintervall får planeras inom intervallet med hela varaktigheten bevarad. Uttryckliga fasta tider och individuella ordinationsvillkor gäller fortsatt. Ingen påtvingad start vid första intervallgränsen, inga konstruerade intervall och ingen generell fem-/tiominutersförkortning. Kontrollera samma regel i faktisk motor, oberoende validator och överföring till appen enligt A43–A46. Dokumentkrav och genomförda prov redovisas separat.

## Regel

När BB skapar ett **nytt grundschema** får vikariepass läggas **var som helst i vald planeringsperiod där ett styrkt kund- eller bemanningsbehov finns**. Historiska vikariepass, deras tidigare dagar, start- och sluttider, längder, tilldelade personer och tidigare passmallar är **inte hårda sökbegränsningar**. Historiken är jämförelseunderlag.

Motorn ska kunna flytta, förkorta, förlänga, ersätta och ta bort gamla vikariepass och skapa nya. Ett gammalt pass får delas i flera separata pass **endast om varje nytt sammanhängande pass** och alla andra villkor är tillåtna. Minst 4 timmar per helt arbetstillfälle gäller också vikarier. Känd frånvaro, verklig tillgänglighet, kompetens, dygnsvila, veckovila, fridagar, natt-/jourbegränsningar, periodgränser och verksamhetsspecifika regler gäller utan undantag. Saknad tillgänglighet får inte antas vara styrkt.

Först prövas om kundernas behov kan täckas med tillgänglig ordinarie personal enligt SSG och andra hårda villkor. Därefter får vikarier placeras enligt det kvarstående behovet. Minskad vikarietid får aldrig försämra behovstäckning eller bryta hårda regler, och får inte felaktigt beskrivas som samma sak som minskad total tid eller realiserad besparing.

## För Codex/Cursor – verifiera faktisk motorbindning

1. Identifiera vilken kodgren, tjänst och profil som **faktiskt används** av körningen. Detta repository kan vara en äldre motorimplementation. Anta **inte** att det är den aktuella produktionsmotorn bara för att README beskriver en solver.
2. Undersök exakt om schemakandidater hämtas uteslutande från `godkända passmallar`, ursprungspass eller historiska personkopplingar. En sådan begränsning är en **möjlig motsägelse** mot beslutet. Redovisa koden och de testfall som bevisar eller motbevisar det.
3. Planera minsta verksamhetssäkra korrigering så att nya pass kan genereras över hela den aktuella perioden enligt behov och hårda villkor. Håll ordinarie och vikarier, historiskt schema och nytt schema åtskilda.
4. Kör **syntetiska tester A34–A36** och regressionstester för Flora, Galaxen och Vintergatan samt fristående validator. Kontrollera att nya pass kan ligga på andra dagar/klockslag än originalet, att varje pass är giltigt och att frånvaro/okänd tillgänglighet inte blir fri kapacitet.
5. Redovisa före/efter antal vikariepass och timmar, ordinarie tid, total aktiv tid, behovstäckning och samtliga tillämpliga kontroller. Skilj **regel dokumenterad**, **regel implementerad**, **test PASS** och **verifierad verklig körning**.

**Skydd:** Bevara originaldata, sparade baser och aktiv drift. Redan auktoriserat isolerat testarbete fortsätter inom sitt mandat; denna dokumentuppdatering startar ingen solver eller driftinstallation. Befintliga operativa motorrepon/arbetsgrenar ska identifieras innan implementation så att aktiva tester inte påverkas av en parallell ändring.

**Obs:** Den gamla formuleringen i `README.md` om att välja pass från godkända passmallar är ett äldre implementationspåstående och får **inte** begränsa det nya generella verksamhetsbeslutet.
