# MQL5 — GoldAI Bridge

The MetaTrader 5 half of the gold system.

- `Experts/GoldAIBridge.mq5` — EA that polls the AI decision file and trades only inside the given zone.
- `Include/` — JSON parser, decision struct, helpers, CSV journal. Copy these into `MQL5/Include/`.
- `docs/SETUP.md` — install steps (English, simple wording).
- `docs/decision.example.json` and `docs/decision.schema.json` — the file the EA expects.

The living decision file lives at `../decisions/current.json`. It is written with `../scripts/write_decision.py` and must be hosted at a public raw HTTPS URL (or copied into `MQL5/Files` for a local test).

Start with `docs/SETUP.md`. Always attach this EA to a DEMO gold chart first.
