const input = document.querySelector("#media");
const button = document.querySelector("#analyze");
const status = document.querySelector("#status");
const report = document.querySelector("#report");
const summary = document.querySelector("#summary");
const preview = document.querySelector("#preview");
const filename = document.querySelector("#filename");
const dropzone = document.querySelector("#dropzone");
const imageUrl = document.querySelector("#image-url");
const useUrl = document.querySelector("#use-url");
const reset = document.querySelector("#reset");
const steps = document.querySelectorAll(".step");
const investigationState = document.querySelector("#investigation-state");
const story = document.querySelector("#story");
const timeline = document.querySelector("#timeline");
const matches = document.querySelector("#matches");
let previewUrl;
let analysisController;
let analysisGeneration = 0;

function clearResults() {
  summary.classList.add("hidden");
  story.classList.add("hidden");
  timeline.innerHTML = "";
  matches.innerHTML = "";
  report.innerHTML =
    "<h3>Investigation evidence</h3><p>Analysis findings will appear here.</p>";
}

function invalidateAnalysis() {
  analysisGeneration += 1;
  if (analysisController) {
    analysisController.abort();
    analysisController = undefined;
  }
}

steps.forEach((step) => {
  step.addEventListener("click", () => {
    steps.forEach((item) => item.classList.remove("active"));
    step.classList.add("active");
    document
      .querySelector(
        `#${step.dataset.view === "upload" ? "dropzone" : step.dataset.view}`,
      )
      .scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

useUrl.addEventListener("click", () => {
  const value = imageUrl.value.trim();
  if (!value) {
    status.textContent = "Paste a public image URL first.";
    return;
  }
  invalidateAnalysis();
  clearResults();
  status.textContent = "Online image selected. Click Analyze evidence.";
  investigationState.textContent = "Online image selected";
  filename.textContent = value;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = undefined;
  preview.innerHTML = `<h3>Evidence preview</h3><img class="preview-media" src="${escapeHtml(value)}" alt="Online evidence preview" onerror="this.replaceWith(Object.assign(document.createElement('p'),{textContent:'Preview unavailable. The public URL can still be investigated.'}))">`;
  dropzone.classList.remove("selected");
});

input.addEventListener("change", () => {
  const file = input.files[0];
  if (!file) return;
  invalidateAnalysis();
  clearResults();
  status.textContent = "";
  investigationState.textContent = "Evidence selected";
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  filename.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  previewUrl = URL.createObjectURL(file);
  preview.innerHTML = `<h3>Evidence preview</h3>`;
  const element = file.type.startsWith("video/")
    ? document.createElement("video")
    : document.createElement("img");
  element.src = previewUrl;
  element.controls = file.type.startsWith("video/");
  element.className = "preview-media";
  preview.appendChild(element);
  dropzone.classList.add("selected");
});

button.addEventListener("click", async () => {
  const urlValue = imageUrl.value.trim();
  const hasFile = input.files.length > 0;
  if (!hasFile && !urlValue) {
    status.textContent =
      "Select an image/video or paste a public image URL first.";
    return;
  }
  const form = new FormData();
  const endpoint = hasFile ? "/api/analyze" : "/api/analyze-url";
  if (hasFile) form.append("media", input.files[0]);
  else form.append("image_url", urlValue);
  invalidateAnalysis();
  const requestGeneration = analysisGeneration;
  analysisController = new AbortController();
  status.textContent = "Analyzing...";
  investigationState.textContent = "Analysis in progress";
  report.innerHTML =
    "<h3>Investigation evidence</h3><p>Running forensic analysis...</p>";
  let response;
  let body;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      body: form,
      signal: analysisController.signal,
    });
    body = await response.json();
  } catch (error) {
    if (error.name === "AbortError" || requestGeneration !== analysisGeneration)
      return;
    status.textContent = `Analysis failed: ${error.message}`;
    return;
  }
  if (requestGeneration !== analysisGeneration) return;
  if (!response.ok) {
    status.textContent = body.detail || "Analysis failed.";
    return;
  }
  status.textContent = "Analysis complete.";
  investigationState.textContent = "Evidence ready";
  steps.forEach((step) =>
    step.classList.toggle("active", step.dataset.view === "report"),
  );
  renderResults(body);
  analysisController = undefined;
  input.value = "";
  imageUrl.value = "";
});

reset.addEventListener("click", () => {
  invalidateAnalysis();
  input.value = "";
  imageUrl.value = "";
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = undefined;
  filename.textContent = "No evidence selected";
  dropzone.classList.remove("selected");
  clearResults();
  status.textContent = "";
  investigationState.textContent = "Waiting for evidence";
  steps.forEach((step) =>
    step.classList.toggle("active", step.dataset.view === "upload"),
  );
  preview.innerHTML =
    "<h3>Evidence preview</h3><p>Select a file to preview it here.</p>";
});

function renderResults(data) {
  const ai = data.ai_assessment || data.video_analysis?.ai_assessment;
  const aiConfidence = ai?.confidence ?? ai?.artificial_score ?? 0;
  const faces =
    data.face_analysis?.face_count ??
    data.video_analysis?.face_summary?.max_faces ??
    0;
  const semantic = data.image_embedding?.vector ? "Available" : "Unavailable";
  summary.classList.remove("hidden");
  story.classList.remove("hidden");
  summary.innerHTML = [
    ["Media", data.media_type.toUpperCase(), "type"],
    [
      "AI assessment",
      ai?.label || "unknown",
      `${Math.round(aiConfidence * 100)}% model score`,
    ],
    ["Faces", faces, "detected"],
    ["Semantic DNA", semantic, "CLIP embedding"],
  ]
    .map(
      ([title, value, note]) =>
        `<article class="metric"><small>${title}</small><strong>${value}</strong><span>${note}</span></article>`,
    )
    .join("");
  const web = summarizeWebTrace(data.web_trace);
  const sections =
    data.media_type === "video"
      ? {
          "Video analysis": data.video_analysis,
          "AI evidence": {
            model_score: `${Math.round(aiConfidence * 100)}%`,
            frame_consensus:
              ai?.ai_frame_consensus === undefined
                ? "Unavailable"
                : `${Math.round(ai.ai_frame_consensus * 100)}%`,
          },
          "Public web provenance": web.summary,
          "Propagation trace": summarizeTrace(data.platform_trace),
          Metadata: {
            codec: data.codec,
            duration_seconds: data.duration_seconds,
            dimensions: `${data.width} × ${data.height}`,
          },
          "Media DNA": { sha256: data.sha256, embedding: semantic },
        }
      : {
          "AI assessment": data.ai_assessment,
          "Face analysis": data.face_analysis,
          "Forgery analysis": data.forgery_analysis,
          Metadata: data.metadata,
          Transformation: data.transformation_analysis,
          "Public web provenance": web.summary,
          "Propagation trace": summarizeTrace(data.platform_trace),
          "Media DNA": {
            sha256: data.sha256,
            perceptual_hash: data.perceptual_hash,
            embedding: semantic,
          },
        };
  const finalReport = data.final_report || {};
  report.innerHTML =
    renderFinalReport(finalReport) +
    `<h3>Investigation evidence</h3><div class="findings">${Object.entries(
      sections,
    )
      .map(
        ([title, value]) =>
          `<details open><summary>${title}</summary>${renderValue(value)}</details>`,
      )
      .join("")}</div>${renderWebSources(data.web_trace)}`;
  renderStory(data);
}

function renderStory(data) {
  const frames = data.video_analysis ? data.sampled_frames || [] : [];
  const platforms = data.platform_trace?.platforms || [];
  const allPosts = platforms.flatMap((platform) =>
    (platform.posts || []).map((post) => ({
      ...post,
      platform: platform.platform,
    })),
  );
  const exactPosts = allPosts.filter((post) => post.exact_hash_match);
  const relevantPosts = exactPosts;
  const platformEvents = relevantPosts.map((post) => ({
    label: post.platform,
    detail: `${post.created_at || "timestamp unavailable"} · ${post.username || "unknown user"} · ${post.exact_hash_match ? "exact hash match" : "same media type"}`,
  }));
  const history = data.final_report?.source_history || [];
  const historyItems = history.map((event) => ({
    label: event.source || event.source_type || "Source",
    detail: `${event.date || "date unavailable"} · ${event.match_type || "observed match"}${event.accessible === false ? " · page inaccessible" : ""}`,
  }));
  const timelineItems = historyItems.length
    ? historyItems
    : platformEvents.length
      ? platformEvents
      : frames.length
        ? frames.map((frame, index) => ({
            label: `Frame ${index + 1}`,
            detail: `${Number(frame.timestamp_seconds).toFixed(2)} seconds · ${frame.ai_assessment?.label || "screened"}`,
          }))
        : [
            {
              label: "Uploaded evidence",
              detail: `${data.media_type?.toUpperCase() || "MEDIA"} · ${data.format || "format unavailable"}`,
            },
          ];
  timeline.innerHTML = `<p class="eyebrow">STORY TIMELINE</p><h2>Evidence sequence</h2><div class="timeline">${timelineItems.map((item) => `<div class="timeline-item"><span class="timeline-dot"></span><div><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.detail)}</p></div></div>`).join("")}</div>`;

  const observedPlatforms = (data.platform_trace?.platforms || []).filter(
    (platform) => platform.status === "available",
  ).length;
  const exactMatches = (data.platform_trace?.platforms || [])
    .flatMap((platform) => platform.posts)
    .filter((post) => post.exact_hash_match).length;
  const webSummary = summarizeWebTrace(data.web_trace);
  const matchSignals = [
    ["SHA-256 identity", data.sha256 ? "Available" : "Unavailable"],
    [
      "Perceptual fingerprints",
      data.perceptual_hash ? "Available" : "Unavailable",
    ],
    [
      "Semantic embedding",
      data.image_embedding?.vector?.length
        ? `${data.image_embedding.vector.length} dimensions`
        : "Unavailable",
    ],
    ["Platforms checked", `${observedPlatforms}/3`],
    ["Exact platform matches", String(exactMatches)],
    ["Public-web sources", String(webSummary.sources_found)],
    ["Public-web exact matches", String(webSummary.exact_matches)],
  ];
  matches.innerHTML = `<p class="eyebrow">MATCHES & SOURCES</p><h2>Propagation trace</h2><div class="match-list">${matchSignals.map(([label, value]) => `<div class="match-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div><p class="panel-note">The trace checks the simulated InstaMock, XMock and FaceMock feeds plus public-web reverse-image evidence when SERPAPI_KEY is configured.</p>`;
  matches.innerHTML += `<div class="lineage"><p class="eyebrow">MEDIA LINEAGE</p><div class="lineage-grid"><article class="lineage-card original"><span class="lineage-kind">ORIGINAL UPLOAD</span><strong>${escapeHtml(data.uploaded_filename || "Uploaded evidence")}</strong><p>Analyzed reference media</p></article>${
    relevantPosts
      .slice(0, 6)
      .map((post) => renderMatchedMedia(post, data.media_type))
      .join("") ||
    `<p class="empty-value">No matching platform media found.</p>`
  }</div></div>`;
  renderLineageGraph(data.platform_trace?.lineage);
}

function renderMatchedMedia(post, mediaType) {
  const isVideo = mediaType === "video";
  const preview = isVideo
    ? `<video src="${escapeHtml(post.media_url)}" controls preload="metadata"></video>`
    : `<img src="${escapeHtml(post.media_url)}" alt="Matched media from ${escapeHtml(post.platform)}">`;
  const kind = post.exact_hash_match
    ? "EXACT COPY"
    : "CANDIDATE TRANSFORMED COPY";
  return `<article class="lineage-card ${post.exact_hash_match ? "exact" : "candidate"}">${preview}<span class="lineage-kind">${kind}</span><strong>${escapeHtml(post.platform)}</strong><p>${escapeHtml(post.username || "Unknown user")} · ${escapeHtml(post.created_at || "Timestamp unavailable")}</p><small>${escapeHtml(post.caption || "No caption")}</small></article>`;
}

function summarizeWebTrace(trace) {
  const summary = trace?.summary || {};
  const configured = trace?.status !== "not_configured";
  return {
    status: trace?.status || "unavailable",
    sources_found: summary.sources_found ?? 0,
    unique_domains: summary.unique_domains ?? 0,
    exact_matches: summary.exact_matches ?? 0,
    accessible_pages: summary.accessible_pages ?? 0,
    blocked_pages: summary.blocked_pages ?? 0,
  };
}

function renderWebSources(trace) {
  const results = trace?.results || [];
  const frames = trace?.frames || [];
  if (trace?.status === "not_configured") {
    return `<div class="web-sources"><p class="eyebrow">PUBLIC WEB PROVENANCE</p><p class="panel-note">Reverse image search is not configured. Set <code>SERPAPI_KEY</code> on the backend to enable it.</p></div>`;
  }
  if (!results.length) {
    return `<div class="web-sources"><p class="eyebrow">PUBLIC WEB PROVENANCE</p><p class="empty-value">No public-web matches were returned.</p></div>`;
  }

  const frameNote = frames.length
    ? `<p class="panel-note">${frames.length} video frames were sampled and searched. Frame timestamps are evidence locations, not publication dates.</p>`
    : "";

  const cards = results
    .slice(0, 20)
    .map((item) => {
      const page = item.page || {};
      const date =
        page.published_date || item.date_from_search || "Date not established";
      const access =
        page.status === "blocked"
          ? "Public page could not be accessed"
          : page.status === "accessible"
            ? "Public page accessible"
            : "Access status unavailable";
      const frame =
        item.timestamp_seconds !== undefined
          ? ` · video frame ${item.frame_index} @ ${Number(item.timestamp_seconds).toFixed(2)}s`
          : "";
      const link = item.url
        ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || item.url)}</a>`
        : escapeHtml(item.title || "Untitled result");
      return `<article class="source-card">
      <div class="source-card-top"><span class="source-type">${escapeHtml(item.match_type || "match")}</span><span>${escapeHtml(item.source || "Unknown source")}</span></div>
      <strong>${link}</strong>
      <p>${escapeHtml(item.snippet || "No snippet returned.")}</p>
      <small>Date: ${escapeHtml(String(date))} · ${escapeHtml(access)}${frame}</small>
    </article>`;
    })
    .join("");

  return `<div class="web-sources"><p class="eyebrow">PUBLIC WEB PROVENANCE</p><h3>Reverse-search sources</h3>${frameNote}<div class="source-list">${cards}</div><p class="panel-note">Only publicly reachable evidence is reported. Login-only, private, or blocked pages are not bypassed.</p></div>`;
}

function renderFinalReport(reportData) {
  if (!reportData || !reportData.verdict) return "";
  const confidence = Math.round((reportData.confidence || 0) * 100);
  const reasons = (reportData.evidence_reasons || [])
    .map((x) => `<li>${escapeHtml(x)}</li>`)
    .join("");
  const earliest = reportData.earliest_observed_source;
  return `<section class="final-report"><p class="eyebrow">FINAL REPORT / VERDICT</p><h2>${escapeHtml(reportData.verdict)}</h2><div class="verdict-score">Evidence confidence: <strong>${confidence}%</strong></div>${earliest ? `<p><strong>Earliest observed source:</strong> ${escapeHtml(earliest.source || "Unknown")} · ${escapeHtml(String(earliest.date || "Date unavailable"))}</p>` : ""}<h3>Why</h3><ul>${reasons || "<li>No supporting reasons recorded.</li>"}</ul><p class="panel-note">This is an evidence-based screening result, not proof of original authorship. AI classification is probabilistic and public-web coverage is limited to indexed/accessible evidence.</p></section>`;
}

function summarizeTrace(trace) {
  const platforms = trace?.platforms || [];
  return {
    platforms_checked: `${platforms.filter((platform) => platform.status === "available").length}/3`,
    exact_matches: platforms.reduce(
      (total, platform) =>
        total +
        (platform.posts || []).filter((post) => post.exact_hash_match).length,
      0,
    ),
    matched_platforms: platforms
      .filter((platform) =>
        (platform.posts || []).some((post) => post.exact_hash_match),
      )
      .map((platform) => platform.platform),
  };
}

function renderLineageGraph(lineage) {
  if (!lineage || !lineage.events?.length) {
    matches.innerHTML += `<div class="lineage-graph"><p class="eyebrow">LINEAGE GRAPH</p><p class="empty-value">No propagation manifest matched these platform posts.</p></div>`;
    return;
  }
  const nodes = [
    {
      label: "Origin",
      detail: lineage.origin?.file || "Original media",
      kind: "origin",
    },
    ...lineage.events.map((event) => ({
      label: event.platform,
      detail: `${event.timestamp || "time unavailable"} · ${event.operations?.map((operation) => operation.type).join(", ") || "repost"}`,
      kind: "event",
    })),
  ];
  matches.innerHTML += `<div class="lineage-graph"><p class="eyebrow">LINEAGE GRAPH</p><div class="graph-track">${nodes.map((node, index) => `${index ? '<span class="graph-arrow">→</span>' : ""}<div class="graph-node ${node.kind}"><strong>${escapeHtml(node.label)}</strong><small>${escapeHtml(node.detail)}</small></div>`).join("")}</div><p class="panel-note">Origin and transformation order come from the propagation ground-truth manifest.</p></div>`;
}

function renderValue(value) {
  if (value === null || value === undefined || value === "") {
    return `<span class="empty-value">Unavailable</span>`;
  }
  if (Array.isArray(value)) {
    return value.length
      ? `<ul class="value-list">${value.map((item) => `<li>${renderValue(item)}</li>`).join("")}</ul>`
      : `<span class="empty-value">None</span>`;
  }
  if (typeof value !== "object") {
    return `<strong>${escapeHtml(String(value))}</strong>`;
  }
  return `<div class="facts">${Object.entries(value)
    .map(
      ([key, item]) =>
        `<div class="fact"><span>${formatLabel(key)}</span><div class="fact-value">${renderValue(item)}</div></div>`,
    )
    .join("")}</div>`;
}

function formatLabel(key) {
  return escapeHtml(
    key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
  );
}

function escapeHtml(value) {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character],
  );
}
