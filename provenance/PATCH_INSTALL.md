# Truth Trace Complete Investigation Patch

This patch upgrades the provenance application so a single `/api/analyze` investigation returns:

- Image AI-generation detection (not only video-frame detection)
- Existing forensic/Media DNA analysis
- SerpApi Google Lens public-web reverse search
- Video-to-frame reverse search
- Public page accessibility and publication-date signals
- Simulated InstaMock/XMock/FaceMock exact propagation evidence
- Unified source history and propagation timeline
- Earliest observed public source (not claimed as original author)
- Final evidence-based verdict/report
- Updated frontend showing all of the above

## Install

From the project root with the existing virtual environment activated:

```powershell
pip install -r provenance\requirements.txt
```

Create `provenance\.env` from `.env.example` and set:

```env
SERPAPI_KEY=YOUR_KEY
```

Keep `provenance\.env` out of Git.

## Run

```powershell
python -m uvicorn provenance.web_api:app --host 127.0.0.1 --port 8020
```

Open:

`http://127.0.0.1:8020/frontend/`

## Files changed by this patch

- `provenance/media_dna/media_features.py` — runs image AI detection.
- `provenance/web_api.py` — attaches the unified final report to every analysis.
- `provenance/investigation_report.py` — source history, propagation aggregation and verdict engine.
- `provenance/frontend/app.js` — complete investigation/report UI.
- `provenance/frontend/style.css` — report/source cards.
- `provenance/.env.example` — configuration template.
- `.gitignore` — protects the SerpApi key.

## Evidence semantics

"Earliest observed source" means the earliest dated public evidence returned/verified by the available search and page metadata. It is not proof of authorship. Private/login-only/blocked pages are not bypassed. AI detection is probabilistic.
