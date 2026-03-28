# VioTrack — AI-Powered Workplace Safety Compliance Platform

> **Automatically detect PPE violations. Track every worker. Review every incident. Make every worksite safer.**

---

## Table of Contents

1. [What is VioTrack?](#what-is-viotrack)
2. [The Problem We Solve](#the-problem-we-solve)
3. [Key Features at a Glance](#key-features-at-a-glance)
4. [How It Works — The AI Pipeline](#how-it-works--the-ai-pipeline)
5. [Violation Types Detected](#violation-types-detected)
6. [System Architecture](#system-architecture)
7. [Tech Stack](#tech-stack)
8. [The Dashboard](#the-dashboard)
9. [Video Processing & Management](#video-processing--management)
10. [Live Webcam Monitoring](#live-webcam-monitoring)
11. [Individual Tracking & Profiling](#individual-tracking--profiling)
12. [Admin Review Workflow](#admin-review-workflow)
13. [Date & Shift Search](#date--shift-search)
14. [AI Chat — Ask Your Safety Data](#ai-chat--ask-your-safety-data)
15. [Equipment Monitoring](#equipment-monitoring)
16. [Privacy & Ethical Design](#privacy--ethical-design)
17. [Multilingual & Theme Support](#multilingual--theme-support)
18. [Database & Data Model](#database--data-model)



---

## What is VioTrack?

**VioTrack** is an end-to-end, AI-powered **workplace safety compliance monitoring platform** built for construction sites and industrial workplaces. It ingests surveillance video footage or live webcam feeds, automatically detects workers violating Personal Protective Equipment (PPE) rules, tracks each worker as a unique anonymous individual across video frames, and presents everything to a safety administrator through a rich analytics dashboard — complete with incident review tools, natural-language data queries, and shift-based search.

The core philosophy: **let the AI do the watching, and let humans make the final decisions.**

---

## Who Is VioTrack For?

| Role                       | How VioTrack Helps                                                               |
| -------------------------- | -------------------------------------------------------------------------------- |
| **Safety Officers**        | Automated 24/7 monitoring instead of manual CCTV review                          |
| **Site Supervisors**       | Daily shift-based violation reports and repeat offender alerts                   |
| **Compliance Managers**    | Trend analytics, date-searchable compliance records, exportable data             |
| **HR / Legal Teams**       | Documented violation evidence with timestamps, snapshots, and admin review trail |
| **Construction Companies** | Reduce liability, improve safety culture, meet regulatory requirements           |

---

_VioTrack — Because every worker deserves to go home safe._

## The Problem We Solve

Every year, thousands of workers on construction and industrial sites are injured or killed due to PPE non-compliance — not wearing hard hats, safety vests, gloves, or boots in hazardous zones. Traditional monitoring methods rely on:

- Human supervisors physically patrolling large sites
- Periodic manual audits of CCTV footage
- Paper-based incident logs

These methods are slow, inconsistent, prone to human error, and expensive to scale. **Important incidents often go unnoticed until it's too late.**

**VioTrack changes this** by:

| Before VioTrack                    | With VioTrack                                               |
| ---------------------------------- | ----------------------------------------------------------- |
| Manual CCTV review (hours per day) | Automated AI analysis in minutes                            |
| Violations frequently missed       | Every frame analyzed, every worker tracked                  |
| No per-individual incident history | Full per-person violation timeline and risk score           |
| Reactive safety management         | Proactive compliance trend monitoring                       |
| No shift-wise breakdown            | Morning / Evening / Night shift analytics                   |
| No natural-language reporting      | Ask questions like "Who had the most violations last week?" |

---

## Key Features at a Glance

| Feature                    | Description                                                                                                            |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **YOLOv8 PPE Detection**   | State-of-the-art object detection model detects missing PPE with ≥40% confidence threshold                             |
| **Custom Person Tracker**  | IOU-based tracker with EMA smoothing, velocity prediction, and Hungarian matching — tracks each worker individually    |
| **Violation Aggregation**  | Per-person profiles with violation counts, frequency, risk score (0–1.0), and worn-equipment lists                     |
| **Admin Review Workflow**  | Confirm or reject each flagged violation with notes; bulk actions for efficiency                                       |
| **Live Webcam Monitoring** | Real-time WebSocket-powered frame streaming with live annotation and session saving                                    |
| **Shift Tracking**         | Automatic or manual Morning / Evening / Night shift tagging on all video sessions                                      |
| **Dashboard Analytics**    | KPI cards, compliance rate, violation trends, PPE breakdown charts, crowd correlation, and repeat offender leaderboard |
| **Date & Shift Search**    | Search reviewed footage by date, shift, and violation type — grouped and easy to navigate                              |
| **AI Chat (Text-to-SQL)**  | Ask natural language questions about your safety data; Claude AI translates them to SQL and streams results            |
| **Snapshot Images**        | Every violation captures a cropped, padded JPEG image for evidence                                                     |
| **Video Snippets**         | Optional 5-second video clips around each violation timestamp                                                          |
| **Privacy-First Design**   | No facial recognition, no biometrics — session-scoped integer IDs only, with full cascade deletion                     |
| **Multilingual UI**        | Full English and Hindi translations built in                                                                           |
| **Dark / Light Theme**     | System-wide dark/light theme toggle                                                                                    |
| **Annotated Video Output** | Bounding boxes and labels overlaid on output video, re-encoded for browser playback                                    |

---

## How It Works — The AI Pipeline

### Uploaded Video Flow

```
Video Upload (MP4 / AVI / MOV / MKV)
         │
         ▼
  Frame Extraction (OpenCV)
  Every 3rd frame processed for performance
         │
         ▼
  YOLOv8 Inference  (conf ≥ 0.40, IOU = 0.45)
  GPU-accelerated when available
  Detects: persons, PPE items, and violations
         │
         ▼
  Custom IOU Person Tracker
  ┌─────────────────────────────────┐
  │  EMA bounding box smoothing     │
  │  Velocity-based prediction      │
  │  Combined score:                │
  │   0.4 × IoU                     │
  │   0.35 × center distance        │
  │   0.25 × size similarity        │
  │  Tracks survive 150 missing     │
  │  frames before deletion         │
  └─────────────────────────────────┘
         │
         ▼
  Violation → Person Association
  IoU matching of violation bbox to person bbox
  2-second cooldown per violation type per person
  Body-part inference:
    face region  → No Face Mask
    foot region  → No Safety Boots
    hand region  → No Gloves
         │
         ▼
  Violation Aggregator
  Per-person profile:
    ▪ Violation list and timestamps
    ▪ Risk Score = 0.6×(count/10) + 0.4×(freq/5), capped at 1.0
    ▪ Worn PPE set (what they ARE wearing)
         │
         ▼
  Annotated Video Output
  Bounding boxes + labels + person IDs via OpenCV
  H.264 re-encoding for browser compatibility
         │
         ▼
  Database Persistence
  TrackedIndividual rows + Violation rows (status: pending)
  Snapshot JPEGs saved to /violation_images/
  Video status updated → "completed"
```

### Live Webcam Flow

```
Browser Camera
    │   (base64 JPEG frames over WebSocket)
    ▼
WebSocket Server
    │  Same pipeline: YOLO + Tracker
    ▼
Annotated Frame returned (base64)
    + Live stats (frame #, persons, violations)
    + Per-person PPE map (what each person has/lacks)
    │
    ▼  (on session end)
Admin Review Interface
    │  Confirm / reject each violation
    ▼
POST /api/webcam/save-session
    │
    ▼
Database (Video, Individuals, Violations)
```

---

## Violation Types Detected

VioTrack detects the following PPE violations out of the box:

| #   | Violation Type                  | Description                                      |
| --- | ------------------------------- | ------------------------------------------------ |
| 1   | **No Helmet / Hard Hat**        | Worker detected without head protection          |
| 2   | **No Safety Vest**              | Worker missing high-visibility vest              |
| 3   | **No Gloves**                   | Hands visible without protective gloves          |
| 4   | **No Safety Boots / Shoes**     | Feet without protective footwear                 |
| 5   | **No Face Mask**                | Face visible without required mask or respirator |
| 6   | **No Goggles / Eye Protection** | Eye area without safety glasses or goggles       |
| 7   | **Restricted Zone Entry**       | Person detected entering a prohibited area       |

The system also tracks what PPE each worker **is** wearing (helmet, vest, boots, mask, gloves, goggles) to build a complete compliance profile.

---

## System Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React 18 + Vite)                │
│  Landing │ Dashboard │ Videos │ Violations │ Individuals │ Search  │
│  Webcam  │ Equipment │ VideoDetail │ Chat Assistant               │
└───────────────────────────┬───────────────────────────────────────┘
                            │  HTTP / WebSocket / SSE
┌───────────────────────────▼───────────────────────────────────────┐
│                       BACKEND (FastAPI + Uvicorn)                  │
│                                                                    │
│   Routers: videos │ violations │ individuals │ dashboard           │
│            equipment │ webcam │ search │ chat                      │
│                                                                    │
│   Services: video_service │ chat_engine │ llm_client               │
│             snippet_service │ chat_prompts                         │
│                                                                    │
│   AI Layer:  detector (YOLOv8) │ tracker (IOU) │ aggregator        │
│              pipeline (orchestrator)                               │
└──────────────┬──────────────────────────────┬─────────────────────┘
               │                              │
   ┌───────────▼──────────┐     ┌─────────────▼─────────────┐
   │  SQLite Database     │     │  Anthropic Claude API      │
   │  (violation_         │     │  Haiku (simple queries)    │
   │   tracking.db)       │     │  Sonnet (complex analysis) │
   └──────────────────────┘     └───────────────────────────┘
               │
   ┌───────────▼──────────┐
   │  File Storage        │
   │  /uploads/           │
   │  /violation_images/  │
   │  /snippets/          │
   └──────────────────────┘
```

---

## Tech Stack

### Backend

| Component         | Technology                             |
| ----------------- | -------------------------------------- |
| Web Framework     | **FastAPI** (async Python 3.11+)       |
| ASGI Server       | **Uvicorn**                            |
| Database          | **SQLite** via `aiosqlite`             |
| ORM               | **SQLAlchemy 2.0** (async)             |
| Object Detection  | **Ultralytics YOLOv8**                 |
| Person Tracking   | Custom IOU Tracker (EMA + velocity)    |
| Computer Vision   | **OpenCV** (`cv2`)                     |
| Video Encoding    | **ffmpeg-python**                      |
| AI / LLM          | **Anthropic Claude** (Haiku + Sonnet)  |
| Async File I/O    | **aiofiles**                           |
| Schema Validation | **Pydantic v2**                        |
| Config Management | **Pydantic-settings** (`.env` support) |

### Frontend

| Component            | Technology                                    |
| -------------------- | --------------------------------------------- |
| UI Framework         | **React 18**                                  |
| Build Tool           | **Vite 7**                                    |
| Routing              | **React Router DOM v6**                       |
| HTTP Client          | **Axios**                                     |
| Charts               | **Recharts** (Pie, Line, Area, Bar, Composed) |
| Icons                | **Lucide React**                              |
| Real-time            | Native **WebSocket API** (webcam)             |
| Streaming            | **Fetch SSE** (chat assistant)                |
| Internationalization | Custom `LanguageContext`                      |
| Theming              | Custom `ThemeContext`                         |

---

## The Dashboard

The Dashboard is the central command center for safety administrators. It auto-refreshes every **30 seconds** and displays:

### KPI Cards

- **Total People Detected** — across all processed videos
- **Compliance Rate %** — percentage of individuals with zero confirmed violations
- **Total Violations** — with a breakdown of pending/confirmed/rejected
- **Violation Rate %** — violations per person tracked

### Charts & Analytics

| Chart                            | Description                                                                                       |
| -------------------------------- | ------------------------------------------------------------------------------------------------- |
| **PPE Violation Breakdown**      | Pie chart showing proportion of each violation type (No Helmet, No Vest, etc.)                    |
| **Violations by Shift**          | Bar chart comparing morning, evening, and night shift incident counts                             |
| **7-Day Violation Trend**        | Line/area chart showing daily violation counts over the past week                                 |
| **Review Status Summary**        | Confirmed vs. Rejected vs. Pending counts with quick-filter links                                 |
| **Crowd vs. Safety Correlation** | Scatter/composed chart correlating worker count to violation count per video                      |
| **Missing PPE Trends (30 Days)** | Multi-line chart tracking each PPE type's absence trend over the past month                       |
| **Recent Events Feed**           | Live feed of the latest violation detections with snapshot thumbnails                             |
| **Top 5 Repeat Offenders**       | Ranked table of workers with the most violations, including risk score and most common infraction |

> **Note:** Violation type and shift breakdowns only count data from **reviewed and approved videos**, ensuring analytics reflect validated incidents only.

---

## Video Processing & Management

### Uploading a Video

1. Drag-and-drop or browse for a video file (MP4, AVI, MOV, MKV — up to 500MB)
2. Select the **shift** (Morning / Evening / Night) before confirming
3. The system saves the file, creates a database record, and begins **background AI processing**
4. A live progress bar shows processing status (0–100%), polling every 2 seconds
5. Once complete, the annotated output video is available for playback

### Video List

Videos are listed grouped by upload date (collapsible sections). Each entry shows:

- Status badge (`pending` / `processing` / `completed` / `failed`)
- Processing progress bar
- FPS, duration, resolution metadata
- Individual count and violation count
- In-list **annotated video player** (modal overlay)
- Delete button (removes all associated data)

### Video Detail Page

- Full video metadata and stats
- **Mark as Reviewed** button — only reviewed videos appear in the Search page
- Annotated video player
- Breakdown of individuals tracked and violations found
- Links to per-video Individuals page and filtered Violations page

### Key Processing Parameters

| Parameter            | Value           | Purpose                                            |
| -------------------- | --------------- | -------------------------------------------------- |
| Frame Skip           | Every 3rd frame | Balances accuracy vs. performance                  |
| Detection Confidence | 0.40            | Minimum YOLO detection threshold                   |
| Display Confidence   | 0.60            | Only show high-confidence violations in UI         |
| IOU Threshold        | 0.45            | YOLO NMS suppression                               |
| Track Persistence    | 150 frames      | How long a person ID survives without re-detection |
| Violation Cooldown   | 2 seconds       | Prevents duplicate records for the same infraction |
| Snapshot Padding     | 50%             | Extra context around bounding box in saved images  |

---

## Live Webcam Monitoring

VioTrack supports **real-time live monitoring** through any browser-connected camera:

1. Navigate to the **Webcam** page and grant camera permission
2. Click **Start Monitoring** — frames stream to the server over WebSocket at ~30fps
3. The server runs the full AI pipeline on each frame and returns:
   - **Annotated frame** (bounding boxes, person IDs, violation labels)
   - **Live stats** (current frame, persons in frame, total violations this session)
   - **Per-person PPE panel** (what each visible worker has and lacks in real-time)
4. Click **Stop** to end the session
5. A **Session Review Interface** appears with two tabs:
   - **Violations tab**: Review each detected violation, view snapshot, confirm or reject
   - **Individuals tab**: Per-person summary with worn PPE list
6. Click **Save & Finish** to persist the session to the database

The system auto-determines the shift based on local time:

- Morning: 6:00 — 14:00
- Evening: 14:00 — 22:00
- Night: 22:00 — 6:00

---

## Individual Tracking & Profiling

Every person detected in a video receives a **temporary, anonymous integer ID** (Person 1, Person 2, etc.) that is unique within that video session. The system builds a full profile for each:

### What's Tracked Per Individual

| Data Point               | Description                                                                    |
| ------------------------ | ------------------------------------------------------------------------------ |
| **Track ID**             | Session-scoped integer (resets per video)                                      |
| **First / Last Seen**    | Frame number and timestamp (seconds from video start)                          |
| **Total Frames Tracked** | How many frames this person appeared in                                        |
| **Total Violations**     | All violations detected by the AI                                              |
| **Confirmed Violations** | Admin-confirmed after review                                                   |
| **Rejected Violations**  | False positives rejected by admin                                              |
| **Risk Score**           | 0.0 (safe) → 1.0 (high risk), computed as `0.6×(count/10) + 0.4×(frequency/5)` |
| **Worn Equipment**       | List of PPE detected ON this person (helmet, vest, boots, etc.)                |

### Individual Profile Page

- Left panel: sortable list of all persons in a video (most violations first)
- Right panel: detailed view of selected person
  - Violation timeline
  - Per-type violation breakdown
  - Pattern analysis: violations per minute, most common infraction, **repeat offender flag**, risk level (Low / Medium / High)
- Supports `?track_id=N` to deep-link to a specific person

---

## Admin Review Workflow

VioTrack is built around a **human-in-the-loop** philosophy. The AI flags potential violations, but a human administrator makes the final determination.

### Per-Violation Review

Each violation record starts with status **`pending`**. The admin can:

- **Confirm** — the violation is real and valid
- **Reject** — the detection was a false positive
- Add **notes** for documentation
- Re-review (change decision) at any time

### Bulk Actions

On the Violations page, admins can:

- Select multiple violations via checkboxes
- Apply **Confirm All** or **Reject All** in one click

### Video Review Gate

After reviewing the violations in a video, the admin clicks **Mark as Reviewed** on the Video Detail page. This gates the video for the **Search** page — only reviewed videos appear in search results, ensuring only validated data enters the compliance record.

### Violations Page Features

- Paginated table (20 per page)
- Filters by: review status, violation type, video ID (stored in URL params)
- Snapshot image thumbnail per row (click to expand in lightbox)
- Violation type badge, confidence %, timestamp, person ID, video name

---

## Date & Shift Search

The **Search** page lets administrators quickly find all violations from a specific date and shift:

1. Pick a **date** (defaults to today)
2. Optionally filter by **shift** (Morning / Evening / Night) and/or **violation type**
3. Results are grouped first by **date**, then by **shift** — with color-coded headers
4. Each video card shows: filename, duration, FPS, shift icon, and a list of violations with snapshot images
5. Click the video to play the **annotated output** in-page
6. A **floating AI Chat button** opens the Chat Assistant for instant data queries

Only **reviewed + completed** videos appear in search results.

---

## AI Chat — Ask Your Safety Data

VioTrack includes a **natural-language chat interface** powered by Anthropic's Claude AI that lets administrators ask questions about their safety data in plain English.

### How It Works

1. Admin types a question (e.g., _"Which shift had the most No Helmet violations last week?"_)
2. The chat engine **auto-routes** to the appropriate model:
   - **Claude Haiku** — fast, for simple lookups
   - **Claude Sonnet** — powerful, for complex analysis (trends, correlations, comparisons)
3. The model generates a **SQL query** against the safety database
4. Results stream back progressively as **Server-Sent Events (SSE)**:

```
status → model selected → thought process → SQL query → data table → follow-up suggestions → summary → done
```

5. Each response includes:
   - The **generated SQL** (transparent and auditable)
   - A **data table** of results
   - **3 suggested follow-up questions**
   - A **one-sentence business insight** summary
6. Chat history is saved to `localStorage` for continuity

### Safety Guardrails

- All SQL is **read-only** — `DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, and `CREATE` are blocked before execution
- Non-aggregated queries are capped at **20 rows** automatically
- On LLM failure: auto-retries up to **3 times** with the more capable Sonnet model

### Example Questions You Can Ask

- _"Show me all violations from the night shift this week"_
- _"Which person had the highest risk score in the last month?"_
- _"Compare helmet violations between morning and evening shifts"_
- _"How many videos were reviewed but have unconfirmed violations?"_
- _"What is the trend in safety boot violations over the past 30 days?"_

---

## Equipment Monitoring

The **Equipment** page provides a dedicated view of all PPE items **detected as present** on the worksite:

- Lists every detected piece of equipment (helmets, glasses, masks, boots, vests, gloves)
- Filter by equipment type and/or video
- Paginated table with snapshot image and bounding box coordinates
- Confidence score per detection
- Frame number and timestamp

This is useful for confirming that PPE is physically present on-site, as opposed to the Violations page which shows where PPE was **absent**.

---

## Privacy & Ethical Design

VioTrack was built from the ground up with worker privacy as a core design principle, not an afterthought.

### What VioTrack Does NOT Do

- **No facial recognition** — faces are not matched, identified, or stored as biometric data
- **No face embeddings** — no deep learning features are extracted from faces
- **No cross-video identity linking** — a worker who appears in two different videos gets two different, unrelated IDs
- **No gait or behavioral biometrics** — tracking is purely positional (bounding box IOU + size/distance)
- **No voice recording** — only video frames are processed
- **No persistent individual profiles** — identities are completely reset per video session

### What VioTrack DOES Do

- Assigns session-scoped **integer IDs** (Person 1, 2, 3…) that expire when the video ends
- Stores only: violation type, timestamp, bounding box coordinates, and confidence score
- Supports **full cascade deletion** — deleting a video removes all associated individuals, violations, reviews, and images
- Enforces **read-only access** to the database via the chat API (DML/DDL blocked)
- Restricts API access via **CORS** to `localhost:5173` and `localhost:3000`

### GDPR Alignment

VioTrack's design aligns with key GDPR principles:

| Principle              | VioTrack Implementation                                               |
| ---------------------- | --------------------------------------------------------------------- |
| **Data Minimization**  | Only stores violation metadata, not raw video frames or identity data |
| **Purpose Limitation** | Data used solely for PPE compliance monitoring                        |
| **Storage Limitation** | Cascade delete on video deletion removes all derived data             |
| **Right to Erasure**   | Delete video → all data permanently removed                           |

> **Note:** Production deployments should add authentication, role-based access control, audit logging, and posted notices in monitored areas.

---

## Multilingual & Theme Support

### Languages

VioTrack ships with full **English** and **Hindi** translations for all UI text, managed through a custom `LanguageContext`. Users can switch languages on the fly without refreshing the page.

### Themes

A custom **`ThemeContext`** provides system-wide **Dark** and **Light** mode support. The theme preference is persisted across sessions.

---

## Database & Data Model

VioTrack uses **SQLite** (auto-created as `violation_tracking.db`) with async access via `aiosqlite` and **SQLAlchemy 2.0**.

### Entity Relationship

```
videos (1) ────────< tracked_individuals (N) ────────< violations (N)
                                                              │
                                                              └──< violation_reviews (1:1)

videos (1) ────────< ppe_equipment (N)
```

### `videos`

Stores video metadata, processing status, shift assignment, annotated output path, total counts, and review status.

### `tracked_individuals`

One row per person per video. Stores track ID, frame range, violation counts (total / confirmed / rejected), risk score, and worn equipment list.

### `violations`

One row per detected violation event. Stores type, class ID, confidence, frame number, timestamp, bounding box, snapshot image path, and review status (pending / confirmed / rejected).

### `violation_reviews`

One-to-one with violations. Stores admin decision (confirmed boolean), notes, reviewer name, and review timestamp.

### `ppe_equipment`

Stores detected PPE items (per frame) — equipment type, confidence, bounding box, image path.

