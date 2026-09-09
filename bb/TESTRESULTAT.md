# Testresultat

Kontrollerat den 8 september 2026.

- 12 regel- och validatortester godkända.
- Pythonfilerna syntaxkontrollerade.
- 9 solvertester finns men kunde inte köras i denna arbetsmiljö eftersom Google OR-Tools saknas.
- 2 API-tester finns men kunde inte köras här eftersom FastAPI och HTTPX saknas.

När `pip install -r requirements.txt` har körts ska hela testsviten köras igen:

```bash
python -m unittest discover -s tests -v
```

Motorn ska inte anslutas till pilotappen förrän solver- och API-testerna är godkända i den miljö där tjänsten ska köras.
