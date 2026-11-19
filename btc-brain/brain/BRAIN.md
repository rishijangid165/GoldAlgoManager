# BTC Monitor brain / dimaag

**English:** This is the entry point of the trader brain. Read it, then run the context command, before any paper-trade decision.

**Hinglish:** Ye BTC Monitor ka dimaag hai. Koi bhi paper trade se pehle pehle yahan se context lo, phir faisla karo.

This is **not** a real human mind, and it does **not** predict the future. It is a memory: rules, past trades, lessons with evidence, similar old situations, and mood. **Koi edge abhi saabit nahi. Live trading on hold. Real order sirf Rishi ke "haan" par.**

This GitHub repo is **PUBLIC**. Never store tokens, passwords, chat IDs, or account numbers here.

## Decision procedure (har faisle se pehle)

1. Kabhi bhi core rules mat todo. Wo `habits/core_rules.md` mein hain (aur `../rules/` mein detail mein).
2. Paper trade se **pehle** ye command chalao, aur uska output padho:

   ```bash
   python3 brain/brain.py context
   ```

   (btc-brain folder se. Agar data fetch na ho to output mein "data nahi hai" aayega — andaza mat lagao.)
3. Context mein lessons, purani similar situations, aur paper equity dikhegi. Lessons **warning** hain, naya trading rule apne aap nahi bante.
4. **Simons rule:** koi naya rule tabhi rule bane jab pehle backtest, phir walk-forward, phir paper test ho, saath mein numbers. Ek-do loss ya ek lesson ki strength se rule mat badlo.
5. Setup A ya A+ na ho, ya rule mana kare, to **NO TRADE**.

## Other commands

```bash
python3 brain/brain.py add-episode --trade-id N   # paper trade #N ki yaad + lesson evidence
python3 brain/brain.py mood --note "..."          # market mood snapshot
python3 brain/brain.py reflect --daily            # aaj ki reflection file
python3 brain/patterns/build_patterns.py          # purani 1H situations dubara banao
python3 brain/patterns/find_similar.py            # abhi jaisi 10 purani situations
```

## Folder map

| Path | Kya hai / What it is |
|---|---|
| `habits/core_rules.md` | Jo rules kabhi nahi tootenge |
| `lessons/lessons.json` | Sabak, evidence, strength, status (active / weak/untested / forgotten) |
| `memory/episodes/NNNN.md` and `memory/episodes.jsonl` | Har paper trade ki kahani |
| `patterns/situations.csv.gz` | Purani 1H situations + agle 24h kya hua (history, not a forecast) |
| `patterns/build_patterns.py` | Uska builder |
| `patterns/find_similar.py` | Abhi se milti-julti purani situations |
| `mood/mood_log.jsonl` | Market mood snapshots (price, F&G, regime, note) |
| `reflections/daily/` and `weekly/` | Roz aur Ravivaar ka chintan |
| `brain.py` | `context`, `add-episode`, `mood`, `reflect` |
