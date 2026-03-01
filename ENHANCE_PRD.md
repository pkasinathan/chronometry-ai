# Product Requirements Document

## Chronometry V2: Efficient Local Vision Logging

### Status

Draft for implementation

### Owner

Prabhu

### Target Platform

MacBook Pro M2 Pro, 16GB RAM, local Ollama endpoint

---

# 1. Problem Statement

Chronometry captures full-resolution Retina screenshots (3456×2234) and sends them to Qwen2.5-VL 7B via Ollama.

Observed issues:

* 15GB RAM usage
* 4GB memory compression
* 16M+ swapouts
* System UI freeze for up to 10 minutes
* Inference stalls when 2 images are sent

Root Cause:

* High-resolution images
* Vision encoder memory spike
* Context bloat
* Multiple images per request
* 16GB unified memory saturation

The system currently exceeds safe memory headroom, causing macOS swap thrashing.

---

# 2. Goals

1. Maintain smooth Mac responsiveness during logging.
2. Keep inference under 3–5 seconds per screenshot.
3. Avoid swap storms entirely.
4. Preserve extraction accuracy for:

   * Active application
   * File / URL
   * Code or SQL context
   * User intent
   * Suggested next step
5. Operate fully local.

---

# 3. Non-Goals

* Running large 35B multimodal models locally.
* Maintaining long chat history inside the VLM.
* Multi-image inference per request.
* High-resolution image preservation.

---

# 4. Functional Requirements

## 4.1 Screenshot Preprocessing

### FR-1: Automatic Downscale

Every screenshot must be resized before inference.

Command:

```
sips -Z 1280 input.png --setProperty format jpeg --setProperty formatOptions 80 --out output_1280.jpg
```

Constraints:

* Longest edge = 1280px max
* JPEG quality = 70–80
* No cropping
* No PNG for inference

---

## 4.2 Single Image Constraint

### FR-2: One Image per Inference

Chronometry must:

* Never send two images in a single model call.
* Serialize inference requests.
* Drop or delay new screenshots if a call is active.

---

## 4.3 Context Management

### FR-3: Stateless Inference

Each screenshot must be processed independently.

Allowed:

* Inject last 2–3 summaries as short bullet list.
* Max 500 tokens total input.

Disallowed:

* Full conversation threads.
* Growing context windows.

---

## 4.4 Model Strategy

### FR-4: Two-Stage Model Cascade

Stage A: Lightweight pass

* Prefer smaller VLM (3B class if available)
* Extract:

  * App name
  * Visible window title
  * Code/SQL detection
  * Confidence score

Stage B: Escalation pass
Triggered only if:

* Low confidence
* Complex UI
* Dense code block

Escalation model:

* Qwen2.5-VL 7B
* Single downscaled image
* Short prompt

---

## 4.5 Metadata Parallel Capture

### FR-5: OS Metadata Capture (Parallel)

While screenshot is processed, collect:

* Active app via AppleScript
* Front window title
* Chrome URL (if browser active)
* Timestamp
* Workspace path (if applicable)

LLM receives:

* Downscaled image
* Structured metadata block

This reduces need for pixel inference.

---

# 5. Performance Requirements

| Metric             | Target                     |
| ------------------ | -------------------------- |
| Memory Usage       | < 12GB total system usage  |
| Swap Activity      | Near zero during inference |
| Inference Time     | < 5 seconds                |
| Mac Responsiveness | No UI freeze               |
| Max Concurrency    | 1 inference                |

---

# 6. System Architecture

### Current (Problematic)

Screenshot
→ Full PNG
→ Qwen2.5-VL 7B
→ Long context
→ Swap storm

---

### V2 Architecture

Screenshot
→ Downscale (1280px JPEG)
→ Parallel metadata capture
→ Lightweight VLM pass
→ Escalate only if needed
→ Structured summary output
→ Append to journal

No multi-image.
No long history.
No parallel inference.

---

# 7. Prompt Design (Optimized for Low Memory)

Example prompt:

```
You are a productivity logger.

Extract:
1. Active application
2. What I am working on
3. Type of task (coding, analysis, browsing, meeting, etc.)
4. Specific artifact (file, repo, table, URL)
5. Intended next step (inferred)

Respond in compact JSON only.
```

Constraints:

* No chain-of-thought.
* No verbose explanation.
* Structured output only.

---

# 8. Risks

| Risk                   | Mitigation                     |
| ---------------------- | ------------------------------ |
| 7B still spikes memory | Use 3B default                 |
| Context creep          | Enforce hard input size limit  |
| Parallel requests      | Add inference lock             |
| Vision overuse         | Prioritize metadata extraction |

---

# 9. Explicit Decision: No 35B Upgrade

On M2 Pro 16GB:

* 35B MoE may compute fast
* But still requires large memory footprint
* Increases swap probability
* Not aligned with journaling workload

Decision:
Do not upgrade to 35B for Chronometry.

---

# 10. Success Criteria

After implementation:

* vm_stat shows minimal swapouts
* PhysMem unused > 1GB during inference
* ollama process stable < 10–12GB
* Mac remains fully responsive
* Accurate journaling entries

---

# 11. Future Enhancements

When hardware upgrades to 32GB+:

* Explore larger MoE models
* Enable longer rolling memory
* Add embedding-based retrieval for historical context
* Implement background batch refinement mode

---

# Final Recommendation

The issue is not model intelligence.
It is memory architecture + resolution + context management.

Chronometry must be designed for:

* Deterministic memory usage
* Small image footprint
* Strict inference serialization

With this architecture, your M2 Pro 16GB will feel real-time and stable.

---
