# Decision file

`current.json` is the file the GoldAIBridge EA polls.

- Schema and a full example: `../mql5/docs/decision.schema.json`, `../mql5/docs/decision.example.json`.
- Write / validate with: `python ../scripts/write_decision.py --help`
- The copy in this folder starts with `"bias": "NONE"` so the EA will not open a trade until a researched decision is published.
- For MT5 to read it over the internet, host this file at a public raw HTTPS URL (GitHub repo or gist recommended). See `../mql5/docs/SETUP.md`. The URL is a placeholder until that hosting is decided.
- For a first test without hosting, copy `current.json` into the terminal’s `MQL5/Files` folder and set `UseLocalFile=true` on the EA.
