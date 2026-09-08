# Truth Trace Project Context

## 1. Project identity

**Truth Trace** is a digital-media provenance and forensic-analysis MVP. It combines:

1. A simulated social-media internet layer:
   - InstaMock
   - XMock
   - FaceMock
   - MediaModifier
   - Propagation Simulator
2. A provenance pipeline that collects, fingerprints, compares, and reports media lineage.
3. A FastAPI + browser dashboard for one-click image/video analysis.

The product goal is not only to classify media as real or AI-generated. It traces how media moves through simulated platforms and presents evidence about source, reposting, transformations, metadata, similarity, and AI-generation signals.

The project is an MVP/prototype. AI classification, face detection, copy-move detection, temporal screening, and source inference are forensic signals and must not be presented as legal proof without human review.

---

## 2. Repository structure

```text
internet/
  facemock/
    backend/
      main.py
      database.py
      models.py
      schemas.py
      requirements.txt
    frontend/
    media/
    database/faceworld.db
  instamock/
    backend/
    frontend/
    media/
    database/instamock.db
  xmock/
    backend/
    frontend/
    media/
    database/xmock.db
  mediaModifier/
    image_modifier.py
    video_modifier.py
    modifier.py
    input/
    output/
  propagation_simulator/
    platform_client.py
    scenario_engine.py
    simulator.py
    manifest_tracker.py
    web_api.py
    frontend/

provenance/
  collector/
    collector.py
    platform_source.py
    artifact_store.py
    outputs/
  preproccessing/
    processor.py
    outputs/
  media_dna/
    media_features.py
    dna_extractor.py
    image_forensics.py
    image_ai_assessment.py
    image_embeddings.py
    outputs/
  similarity/
    similarity_engine.py
    outputs/
  lineage/
    lineage_engine.py
    outputs/
  reporting/
    report_generator.py
    outputs/
  pipeline.py
  accuracy_eval.py
  accuracy_manifest.example.json
  web_api.py
  frontend/
    index.html
    app.js
    style.css
  requirements.txt
  web_uploads/

context.md
```

The repository contains generated media, SQLite databases, cached model files, reports, and `__pycache__` files. Do not treat generated output as source code.

---

## 3. Internet layer

### 3.1 Platform responsibilities

Each mock platform has its own FastAPI backend, SQLite database, media directory, and frontend. Posts store user information, text/caption, media filename, MIME/media type, and timestamp.

All three platforms accept both image and video media. Media is saved under a UUID filename and served through `/media/<filename>`.

| Platform | Backend port | Backend module | Browser frontend |
|---|---:|---|---|
| InstaMock | `8000` | `internet/instamock/backend/main.py` | `http://127.0.0.1:8000` or static frontend |
| XMock | `8001` | `internet/xmock/backend/main.py` | `http://127.0.0.1:8001` or static frontend |
| FaceMock | `8002` | `internet/facemock/backend/main.py` | `http://127.0.0.1:8002` or static frontend |

Typical backend commands, run from the relevant backend directory:

```powershell
cd internet\instamock\backend
python -m uvicorn main:app --reload --port 8000

cd internet\xmock\backend
python -m uvicorn main:app --reload --port 8001

cd internet\facemock\backend
python -m uvicorn main:app --reload --port 8002
```

The exact frontend-serving setup depends on how the frontend is being demonstrated. The existing mock frontends use JavaScript `fetch` calls to their platform API.

### 3.2 Common platform endpoints

All three mock APIs expose the following general endpoints:

```text
GET  /
POST /api/users
GET  /api/users
POST /api/posts
GET  /api/posts
GET  /media/<filename>
```

The post field names are platform-specific:

- InstaMock and FaceMock use `caption`.
- XMock uses `text`.
- All accept a multipart `media` upload.

### 3.3 MediaModifier

`internet/mediaModifier/` applies controlled transformations used to create provenance chains:

- Image resize/compression/crop/conversion operations.
- Video resize/compression/crop/conversion operations using FFmpeg.
- Outputs are written to `internet/mediaModifier/output/`.
- Inputs are stored in `internet/mediaModifier/input/`.

Video operations require FFmpeg. The code attempts to discover FFmpeg from `PATH` and the Windows WinGet installation directory under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\`.

### 3.4 Propagation Simulator

The simulator uploads one input media file and propagates it through all three platforms.

Control API:

```text
GET  /
POST /api/users
POST /api/propagate
GET  /frontend/
```

Default platform targets configured in `internet/propagation_simulator/web_api.py`:

```text
InstaMock -> http://127.0.0.1:8000
XMock     -> http://127.0.0.1:8001
FaceMock  -> http://127.0.0.1:8002
```

Run it from `internet/propagation_simulator/`:

```powershell
python -m uvicorn web_api:app --port 5500
```

Dashboard:

```text
http://127.0.0.1:5500/frontend/
```

The three platform servers must already be running before propagation.

---

## 4. Provenance pipeline

### 4.1 Pipeline order

`provenance/pipeline.py` runs the stages in this order:

```text
collector
  -> preproccessing
  -> media_dna
  -> similarity
  -> lineage
  -> reporting
```

Run from the repository root:

```powershell
python provenance\pipeline.py
```

Skip collection when an existing collector investigation should be reused:

```powershell
python provenance\pipeline.py --skip-collector
```

The spelling `preproccessing` is an existing directory name and is intentionally retained for compatibility.

### 4.2 Collector

The collector reads posts/media from the three mock platforms, downloads media and records platform context such as:

- platform name
- post/user identity
- post URL or media URL
- timestamp
- caption/text
- downloaded source file

Collector outputs are stored under:

```text
provenance/collector/outputs/<investigation_id>/
```

The artifact index is generally `artifacts.json`.

### 4.3 Preprocessing

Preprocessing normalizes collected artifacts and builds the investigation artifact set consumed by later stages. Its output is stored under:

```text
provenance/preproccessing/outputs/<investigation_id>/
```

### 4.4 Media DNA

`provenance/media_dna/media_features.py` is the unified image/video analyzer. `dna_extractor.py` applies it to every artifact and writes `media_dna.json`.

#### Image signals

- SHA-256 file hash.
- File format, mode, dimensions, aspect ratio, file size.
- pHash, dHash, average hash.
- Normalized color histogram.
- EXIF metadata, including camera/software/timestamp signals.
- OpenCV Haar-cascade face detection and face boxes.
- Pixel statistics.
- JPEG/WEBP ELA screening; PNG may report ELA unavailable.
- ORB copy-move screening with spatial-offset grouping.
- AI-image classification.
- Optional CLIP image embedding.

#### Video signals

- FFprobe format and stream metadata.
- Codec.
- Duration.
- Frame rate.
- Width/height/aspect ratio.
- Container-reported frame count when available.
- Three sampled frames: start, middle, and conservatively before the end.
- pHash/dHash/average hash and color histogram per sampled frame.
- Per-frame face analysis.
- Per-frame AI-image detector result.
- Per-frame CLIP embedding.
- Mean normalized frame embedding.
- Adjacent-frame pHash temporal consistency.
- AI artificial score and frame consensus.

Video frame extraction uses FFmpeg and writes temporary PNG frames. PNG is used instead of JPEG because the installed FFmpeg build can fail to initialize its MJPEG encoder for some H.264 inputs.

If a non-first sample fails, the analyzer records an extraction error and continues when at least one valid frame exists. If no frame can be extracted, analysis fails explicitly.

### 4.5 AI assessment semantics

`image_ai_assessment.py` uses:

```text
umm-maybe/AI-image-detector
```

The model output is probabilistic. Labels are normalized to:

```text
ai_generated
authentic_unknown
```

For images:

```text
confidence = model probability for the selected prediction
```

For videos:

```text
artificial_score = mean artificial score across analyzed frames
ai_frame_consensus = fraction of analyzed frames with artificial score >= 0.5
label = ai_generated when mean artificial score >= 0.5
```

The dashboard intentionally uses the video `artificial_score` as the primary model score. Frame consensus is supporting evidence, not a replacement for the model score.

Correct interpretation example:

```text
Verdict: AI Generated
Model score: 58.77%
Frame consensus: 100% (3/3 frames)
```

This does **not** mean the detector has established legal certainty. It means all sampled frames crossed the configured screening threshold while the average model probability was approximately 0.5877.

Optional environment variable for another compatible detector:

```powershell
$env:TRUTH_TRACE_IMAGE_AI_MODEL = "model-name"
```

### 4.6 Embeddings

`image_embeddings.py` uses:

```text
openai/clip-vit-base-patch32
```

The expected embedding dimension is 512. Embeddings are normalized before storage/use. Transformers compatibility is handled through the model output's pooled representation.

### 4.7 Similarity

`provenance/similarity/similarity_engine.py` compares media using:

- exact SHA-256 evidence
- perceptual hashes
- color histogram similarity
- dimensions/aspect ratio
- semantic embedding similarity when available

Similarity scores are evidence for possible reposting/transformation. Exact hash equality indicates byte-identical content; it does not by itself prove authorship or earliest origin.

### 4.8 Lineage and reporting

The lineage stage turns artifact comparisons and platform metadata into a provenance graph with confidence levels and likely relationships such as repost, transformed copy, or related media.

The reporting stage produces text and JSON reports under:

```text
provenance/reporting/outputs/<investigation_id>/
```

Reports include verdict summaries, evidence, comparison confidence, timeline/platform context, and lineage/provenance information.

---

## 5. Provenance web dashboard

### 5.1 Start the dashboard

From the repository root:

```powershell
python -m uvicorn provenance.web_api:app --port 8020
```

Open:

```text
http://127.0.0.1:8020/frontend/
```

The dashboard is served by the same FastAPI origin as the analysis API. The frontend uses a relative API URL, so it should normally be opened through this server rather than directly from a file.

### 5.2 API

`provenance/web_api.py` exposes:

```text
GET /
POST /api/analyze
GET /frontend/
```

`POST /api/analyze` expects multipart form data:

```text
media=<image or video file>
```

Allowed extensions:

```text
.jpg .jpeg .png .webp
.mp4 .mov .m4v .webm .avi .mkv
```

The endpoint saves the upload under `provenance/web_uploads/`, runs unified analysis, and returns the structured analysis object.

### 5.3 Frontend behavior

The dashboard:

- previews selected images/videos.
- sends media to `/api/analyze`.
- displays summary cards.
- displays readable evidence rows rather than nested JSON.
- displays video model score and frame consensus separately.
- supports reset/re-upload, including selecting the same file again.
- revokes old preview object URLs.
- displays request and backend errors.

After frontend changes, use a hard refresh:

```text
Ctrl + F5
```

The script query version in `provenance/frontend/index.html` is used to avoid stale browser JavaScript caching.

---

## 6. Installation

Use the repository's provenance requirements:

```powershell
python -m pip install -r provenance\requirements.txt
```

Each mock platform has its own requirements file:

```powershell
python -m pip install -r internet\facemock\backend\requirements.txt
python -m pip install -r internet\instamock\backend\requirements.txt
python -m pip install -r internet\xmock\backend\requirements.txt
```

Required external/runtime tools:

- Python 3.10+ recommended.
- FFmpeg and FFprobe for video operations and analysis.
- A working PyTorch installation compatible with the local Python version.
- Internet access for the first Hugging Face model download, unless models are already cached.

Hugging Face may print an unauthenticated-request warning. This is not a functional failure; `HF_TOKEN` can be configured for higher download limits.

---

## 7. Testing and verification

### Syntax checks

```powershell
python -m py_compile provenance\media_dna\media_features.py provenance\web_api.py
node --check provenance\frontend\app.js
git --no-pager diff --check
```

### API smoke test

Use the dashboard or a multipart client against:

```text
POST http://127.0.0.1:8020/api/analyze
```

Verify:

- image returns HTTP 200 and `media_type: "image"`.
- video returns HTTP 200 and `media_type: "video"`.
- video has at least one sampled frame.
- `video_analysis.frame_extraction_errors` is empty for a healthy video.
- video `image_embedding` has 512 dimensions when the CLIP model is available.

### Internet-layer test order

1. Start InstaMock, XMock, and FaceMock.
2. Check each root endpoint.
3. Create users.
4. Upload image and video posts.
5. Confirm posts/feed and `/media/<filename>`.
6. Start Propagation Simulator.
7. Upload media through `/api/propagate`.
8. Confirm propagated posts on all three platforms.
9. Run provenance collection/pipeline.
10. Open the generated report and compare platform timestamps/media hashes.

### Representative fixture files

Existing repository fixtures include:

```text
internet/mediaModifier/input/image.png
internet/mediaModifier/input/edited-copy.png
```

Use repository videos or generated media under the internet/provenance directories for video checks. Do not assume every generated artifact is a clean test fixture.

---

## 8. Important implementation rules

- Do not modify the separate `ai-detection` folder unless explicitly requested.
- Preserve the existing `preproccessing` directory spelling because pipeline stages depend on it.
- Prefer `pathlib.Path` and existing repository helpers.
- Keep image and video behavior consistent where possible.
- Do not treat AI scores as ground truth.
- Do not turn frame consensus into model confidence.
- Keep FFmpeg stderr available when diagnosing video failures.
- Avoid broad exception handling that silently converts failed forensic operations into successful-looking results.
- Generated databases, media, reports, model caches, and `__pycache__` files should not be treated as source changes.
- When adding a new supported extension, update both validation and downstream handling.

---

## 9. Current known limitations

1. AI-image detection is probabilistic and model-dependent.
2. Video AI analysis samples three frames rather than analyzing every frame.
3. Face detection uses Haar cascades and is a screening signal, not a calibrated identity/confidence system.
4. Copy-move detection is ORB-based and screening-only.
5. ELA depends on image encoding and may be unavailable for PNG.
6. FFmpeg behavior can vary by installed build and codec/container.
7. Source discovery currently operates over the simulated social internet; it is not a general web search engine.
8. The web API stores uploads locally and has no authentication, quota, retention policy, or production deployment hardening.
9. CORS is intentionally permissive in some development APIs and must be restricted before deployment.
10. The dashboard is a demonstration UI, not a final evidentiary/legal reporting interface.

---

## 10. Recommended judge demonstration

1. Start all three mock platform APIs.
2. Open Propagation Simulator at `http://127.0.0.1:5500/frontend/`.
3. Create or use demo users.
4. Upload an image or video and propagate it.
5. Show the resulting posts and platform-specific media URLs.
6. Start the provenance API on port `8020`.
7. Upload the original or propagated media in Truth Trace.
8. Show:
   - media type and metadata
   - SHA-256 and perceptual identity
   - AI model score
   - frame consensus for video
   - faces and forensic signals
   - embeddings and temporal consistency
9. Run the full pipeline when demonstrating lineage across multiple platform artifacts.
10. Explain clearly that the system produces transparent forensic evidence and screening scores, not an unconditional authenticity verdict.

---

## 11. Two-to-three-minute project setup and demo speech

Use this as a concise judge presentation after starting the services:

> **Good morning. Our project is Truth Trace.**
> The problem we address is not only “Is this image or video fake?” The more useful question is: **Where did it come from, what changes happened to it, and how did it spread?**
>
> Truth Trace has two connected layers. The first is a simulated internet layer with InstaMock, XMock, and FaceMock. MediaModifier applies realistic platform operations such as resizing, cropping, compression, format conversion, and video processing. The Propagation Simulator sends the media through these platforms and records every event in a ground-truth manifest.
>
> To run the project, we install the Python dependencies, make sure FFmpeg is available for video processing, and start the three platform APIs, the Propagation Simulator, and the Truth Trace API. Their browser frontends are available on ports 8000, 8001, 8002, 8010, and 8020. This makes the complete flow visible instead of hiding it behind a single result.
>
> Now I upload an original image or video into the Propagation Simulator. It is not simply copied. The simulator selects a propagation scenario, applies MediaModifier operations, chooses a platform order, creates simulated users, and publishes the transformed media. Each platform feed shows the resulting post, timestamp, media URL, and now provides download and delete controls for demonstration and data management.
>
> Next, I take a manipulated copy from one of the platform feeds and upload it to Truth Trace. Truth Trace first identifies the media type and calculates its SHA-256, perceptual hashes, metadata, embeddings, and forensic signals. For images it can screen faces, recompression and copy-move indicators. For videos it extracts metadata, samples frames, checks temporal fingerprints, and aggregates frame-level AI evidence.
>
> The provenance stage then checks all three simulated platforms. It downloads the observed media, hashes it, and compares it with the uploaded evidence. When there is an exact hash match, Truth Trace connects the matching post to the propagation manifest. This gives us the original source, platform order, timestamps, transformation operations, reposts, and a visual lineage graph.
>
> If I upload an unrelated file that was never propagated, the system does not invent a lineage. It shows zero exact matches and no propagation manifest. This is an important safeguard against false attribution. Reset also clears the current evidence, preview, timeline, report, and lineage state so a new investigation starts cleanly.
>
> The final output is therefore not an unexplained “real” or “fake” label. It is an auditable story: **origin, transformations, platform propagation, forensic evidence, and confidence signals in one workspace.** AI detection and forensic checks are probabilistic screening signals, so the system supports human investigators rather than claiming legal certainty. That combination of simulated spread, reproducible ground truth, and explainable provenance is the core value of Truth Trace.
