# Gemini evaluation

Place eight short, owned or royalty-free WAV clips and two overhead table JPEGs at the paths in `cases.json`. The files are intentionally not committed; keep local music and photo assets out of version control.

For live requests, install the official `google-genai` SDK (`python -m pip install google-genai`) and set `GEMINI_API_KEY` in the environment.

From the repository root, run all cases three times:

```powershell
python scripts/gemini_eval.py
```

Run only the first two songs for a quick check:

```powershell
python scripts/gemini_eval.py --limit 2
```

The script writes `eval/report-YYYY-MM-DD.md` with latency, guard pass rate, setting and role columns. A song is flagged when its setting differs across any repeated clip/photo run. Missing inputs and request failures are recorded as failed attempts so the report remains useful.