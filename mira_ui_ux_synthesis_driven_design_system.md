# UI/UX Synthesis-Driven Design (UI-SDD) Playbook for Mira V0.03

## Why UI/UX Synthesis-Driven Design Beats Blank-Canvas Wireframing

Traditional UI/UX design fails for mental health apps because designers wireframe static screens in Figma while imagining a calm user sitting in a quiet room. When an 18–30-year-old user in Mumbai or Bengaluru opens **Mira V0.03** during a panic spike, a 3 AM overthinking loop, or a bed-rot procrastination spiral, they have zero cognitive bandwidth for multi-step forms, mood sliders, or clinical CBT worksheets.

**UI/UX Synthesis-Driven Design (UI-SDD)** treats top-grossing mental health apps and high-frequency consumer apps as an external R&D laboratory. Instead of inventing interactions from scratch, you systematically harvest proven micro-flows, deconstruct their spatial and sensory mechanics via multimodal AI, strip out the friction patterns identified in 2-star and 3-star user reviews, and fuse mental health psychology with consumer-app muscle memory into React Native code.

| Pipeline Stage | Core Objective | Input Artifacts | AI / Research Method | Output Artifact for Mira V0.03 |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Reference Flow Harvesting** | Capture raw visual, motion, and haptic micro-flows without reinventing UI patterns | [Mobbin](https://mobbin.com/explore/mobile), [Page Flows](https://pageflows.com/), [Appshots](https://appshots.design/), 60 FPS screen recordings | Triangulate 1 Mental Health App + 1 Consumer Muscle-Memory App + 1 Tactile/Game-Feel App per action | Grouped 4–6 frame screenshot strips + video clips per micro-intervention |
| **Stage 2: Multimodal UI Deconstruction** | Convert pixels and animations into machine-readable spatial, motion, and haptic specs | Keyframe sequences from [How We Feel](https://howwefeel.org/), [Finch](https://finchcare.com/), [Goblin Tools](https://goblin.tools/), [Endel](https://endel.io/), [Tiimo](https://www.tiimoapp.com/) | Vision-LLM structural extraction across 5 UI/UX layers (`360×800 dp` grid, spring physics, haptics, copy, voice sync) | Normalized `UI_Flow_Deconstruction.json` per donor app |
| **Stage 3: Friction & Anti-Pattern Mining** | Identify what makes distressed or shared-room users abandon mental health apps | 2-star & 3-star reviews from [Finch](https://finchcare.com/), [Headspace](https://www.headspace.com/), [Calm](https://www.calm.com/), [Daylio](https://daylio.net/) | LLM clustering of acute-episode drop-off triggers + Indian Gen-Z environmental constraints | **Mira Anti-Pattern Kill List** & Shared-Room Stealth Rules |
| **Stage 4: Cross-App Pattern Synthesis** | Fuse clinical psychological structure with zero-tutorial consumer muscle memory | Deconstructed JSON specs + Anti-Pattern Kill List + Mira's 9-Action Catalog | Multi-donor synthesis prompt (`Mental Health Donor + Consumer UX Donor − Friction = Mira Spec`) | Complete **9-Action UI/UX Synthesis Matrix** & unified state machines |
| **Stage 5: Persona & Hardware Stress-Test** | Audit every screen against mid-range Android limits and Indian shared-room privacy | Synthesized UI spec + `360×800 dp` viewport rules | 5-Gate Automated UI Critic Prompt (Thumb zone, Over-the-Shoulder Stealth, Silent Fallback, 60 FPS budget, Hinglish copy) | Validated, implementation-ready interaction specification |
| **Stage 6: Spec-to-Code Compilation** | Generate modular 60 FPS React Native + WebRTC co-pilot components | Validated JSON UI/UX spec | One-action-at-a-time AI coding prompt targeting [React Native Skia](https://docs.expo.dev/versions/latest/sdk/skia/), [Rive React Native](https://rive.app/docs/runtimes/react-native/react-native), [React Native Reanimated](https://docs.swmansion.com/react-native-reanimated/), and [Expo Haptics](https://docs.expo.dev/versions/latest/sdk/haptics/) | Production TypeScript component wired to FastAPI/WebRTC voice events |

---

## Stage 1: Reference App & Micro-Flow Harvesting ("The 3-Donor Triangulation Method")

Never copy a mental health app wholesale—most mental health apps suffer from slow onboarding, text-heavy cards, and Western clinical framing. Instead, for every Mira action, harvest references across **three distinct donor buckets** using [Mobbin](https://mobbin.com/explore/mobile), [Page Flows](https://pageflows.com/), and [Appshots](https://appshots.design/):

1. **Bucket A — Mental Health & Neurodivergent Apps (For Emotional Pacing & Grounding Structure):**
   * [How We Feel](https://howwefeel.org/): High-contrast, tactile 2D emotion geometry, color-coded shader gradients, and 1-tap check-in flows without clinical interrogation.
   * [Finch](https://finchcare.com/): "First Aid" acute crisis kit routing, low-stakes micro-goals ("Just survive the day"), and non-judgmental completion rewards.
   * [Goblin Tools](https://goblin.tools/): Zero-fluff neurodivergent task decomposition ("Magic ToDo" breaking overwhelming tasks into tiny steps with a "spiciness" slider).
   * [Tiimo](https://www.tiimoapp.com/): Visual countdown rings, perimeter progress bars, and AI brain-dump-to-checklist conversion built for executive dysfunction.
   * [Endel](https://endel.io/) & [Loóna](https://loona.app/): Generative reactive visuals paired with adaptive ambient soundscapes and low-lux bedtime wind-downs.
   * [Balance](https://themindcompany.com/apps/balance), [Headspace](https://www.headspace.com/), & [Calm](https://www.calm.com/): Audio-synchronized breathing orbs and guided sensory step-downs ([Calm 5-4-3-2-1 Guide](https://www.calm.com/blog/5-4-3-2-1-a-simple-exercise-to-calm-the-mind)).
   * [Opal](https://www.opal.so/blog/designing-for-wellbeing) & [Forest](https://forestapp.cc/): Commitment devices, tactile timer dials, and physical friction against doomscrolling.
   * [Daylio](https://daylio.net/): Zero-typing icon/chip logging for low-energy states.

2. **Bucket B — High-Frequency Indian Gen-Z Consumer Apps (For Zero-Tutorial Muscle Memory):**
   * [WhatsApp Voice Notes](https://faq.whatsapp.com/657157755756612): Press-and-slide-up to lock the microphone, live waveform feedback, and 1-tap cancel/send.
   * [Google Keep](https://www.androidpolice.com/google-keep-gemini-voice-checklist-notes/): Instant voice-to-checklist pills without folder hierarchy friction.
   * [Google Clock](https://9to5google.com/2026/09/03/google-clock-timers-redesign/): High-visibility pill controls and glanceable full-screen countdowns.
   * **Spotify Mobile**: Two-line real-time synced lyrics (ideal for Mira's live voice captions in a noisy room) and the persistent bottom mini-player pill.
   * **Instagram Reels**: Top segmented story progress bars (`Step 1 of 5`) and press-and-hold anywhere on the canvas to pause.
   * **PhonePe / Google Pay**: Instant bottom-sheet overlays and crisp haptic+audio completion receipts.

3. **Bucket C — Tactile & Game-Feel Benchmark Apps (For Visceral Physics & Reward Loops):**
   * [Duolingo](https://www.duolingo.com/mobile): Interactive [Rive React Native](https://rive.app/docs/runtimes/react-native/react-native) state machines, combo haptic pops, and sub-second celebratory feedback cards.

### Harvesting Protocol Checklist

* **Capture 5 Keyframes per Micro-Action:** For each target flow on [Mobbin](https://mobbin.com/explore/mobile) or [Page Flows](https://pageflows.com/), export:
  1. `Entry Card / Trigger State` (What makes the user tap it?)
  2. `Initial Active Canvas` (First 2 seconds after launch—where does the thumb rest?)
  3. `Peak Interaction / Gesture State` (What happens visually during a press-hold, swipe, or voice input?)
  4. `Step Transition State` (How does step 1 morph into step 2 without a page reload?)
  5. `Completion / Receipt State` (How does the exercise close and reward the user?)
* **Log the Frame-Timing & Audio Layer:** Record a 30-second screen capture with audio enabled to measure transition durations (`ms`) and sound-effect pitch progression.

---

## Stage 2: Multimodal UI/UX Deconstruction (Pixels to Spatial, Haptic & Voice Specs)

Drop your 4–6 harvested screenshots (or a screen-recording video clip) into a multimodal LLM (Gemini 2.5 Pro, Claude Sonnet, or GPT-4o) using the prompt below. Unlike generic screenshot-to-code prompts, this prompt extracts **spatial ergonomics for a `360×800 dp` Android viewport, gesture physics, haptic cadence, and voice co-pilot hooks**.

### Prompt 1: Multimodal UI/UX Flow Deconstructor

```markdown
### ROLE
You are a Staff Mobile UX Researcher, Game-Feel Physicist, and React Native Architecture Lead.

### INPUT
Attached is a sequence of screenshots (or screen recording) showing a micro-interaction flow from [APP NAME, e.g., How We Feel / Finch / Tiimo / Endel].

### OBJECTIVE
Deconstruct this visual flow into a strict, engineering-ready JSON specification that we can adapt for Mira V0.03 (a voice-first emotional support app running on a 360x800 dp mid-range Android viewport). Do NOT write generic prose descriptions. Extract the exact mechanics across 5 layers:

1. **Spatial & Ergonomic Grid (Normalized to 360x800 dp):**
   - Map every element into three vertical zones:
     - `Top Status & Progress Zone (y: 0–120 dp)`: Segmented bars, timer pills, exit triggers.
     - `Center Visual Stage (y: 120–440 dp)`: Ambient shaders, Rive state machines, 2-line voice captions.
     - `Primary Thumb Action Zone (y: 440–760 dp)`: All primary touch, hold, swipe, and mic controls.
   - Measure visual density (% of dark/open canvas vs. UI chrome) and maximum simultaneous text words on screen.

2. **State Machine & Transition Triggers:**
   - Enumerate every discrete UI state (`IDLE_PREVIEW` -> `ACTIVE_STEP_1` -> `GESTURE_HOLD` -> `STEP_COMPLETE` -> `RECEIPT`).
   - Identify the exact trigger for each transition (e.g., `onLongPress(5000ms)`, `onPanEnd(velocityX > 500)`, `onTimerTick`, `onVoiceVADEnd`).

3. **Physics, Motion & Shader Primitives:**
   - Specify spring parameters (`mass`, `damping`, `stiffness`), interpolation curves (`Easing.bezier`), particle/shader behaviors (e.g., radial expansion, ash disintegration, frosted glass blur radius), and frame-budget risks on a mid-range Snapdragon/Dimensity chip.

4. **Sensory & Haptic Choreography:**
   - Map where tactile pulses (`Light`, `Medium`, `Heavy`, `Selection`, `Success`) and micro-audio cues (marimba pop, sub-bass exhale, crisp snap) fire relative to user touch or voice input.

5. **Micro-Copy & Cognitive Load Audit:**
   - Extract exact prompt copy, word count per screen, reading grade level, and whether the screen passes the "Over-the-Shoulder Stealth Test" (would a flatmate or parent glancing at this screen know it is a mental health therapy app?).

### REQUIRED JSON OUTPUT SCHEMA
Output ONLY valid JSON matching this structure:
{
  "source_app": "string",
  "flow_name": "string",
  "psychological_mechanism": "string",
  "spatial_layout_360x800": {
    "top_zone_0_120dp": ["string"],
    "center_stage_120_440dp": ["string"],
    "thumb_zone_440_760dp": ["string"],
    "open_canvas_ratio_percent": 0,
    "max_words_on_screen": 0
  },
  "state_machine": [
    {
      "state_id": "string",
      "visual_state": "string",
      "user_input_verb": "TAP | HOLD | SWIPE | VOICE_VAD | ACCELEROMETER_FLIP | PASSIVE_TIMER",
      "input_friction_score_1_to_5": 1,
      "haptic_trigger": "Light | Medium | Heavy | Selection | Success | Pulsed_Interval",
      "audio_cue": "string",
      "next_state_trigger": "string"
    }
  ],
  "physics_and_rendering": {
    "recommended_rn_engine": "Skia | Rive | Reanimated",
    "spring_config": { "damping": 0, "stiffness": 0, "mass": 1 },
    "shader_or_vector_notes": "string"
  },
  "stealth_and_copy_audit": {
    "reading_grade_level": 0,
    "passes_over_the_shoulder_stealth": true,
    "cringe_or_clinical_jargon_detected": ["string"]
  }
}
```

---

## Stage 3: Negative-Review & Shared-Room Friction Mining ("The Anti-Pattern Filter")

In mental health UX, **what you remove matters more than what you add**. A feature that looks great in a product review often causes users to rage-quit when they are actively panicking, exhausted at 3 AM, or sitting in a crowded hostel room.

Export 150–200 recent **2-star and 3-star App Store / Google Play reviews** (plus Reddit threads from `r/mentalhealth`, `r/ADHD`, and `r/Indianostalgia` / `r/indiasocial`) for [Finch](https://finchcare.com/), [Headspace](https://www.headspace.com/), [Calm](https://www.calm.com/), [Daylio](https://daylio.net/), and [Tiimo](https://www.tiimoapp.com/), then run **Prompt 2**.

### Prompt 2: 2-Star/3-Star Review & Shared-Room Friction Miner

```markdown
### ROLE
You are a Behavioural Psychologist and Principal UX Researcher specializing in acute emotional states and Gen-Z mobile usage in urban India.

### INPUT DATA
Below is a dump of 2-star and 3-star user reviews and Reddit complaints for [Finch / Headspace / Calm / Daylio / Tiimo]:
"""
[PASTE 100-200 2-STAR & 3-STAR REVIEWS HERE]
"""

### OBJECTIVE
Analyze these reviews to identify the exact UX anti-patterns that cause users to feel overwhelmed, judged, annoyed, or exposed during a mental health moment. Cross-reference every complaint against Mira V0.03's target environment:
- 18–30-year-old student/young professional in urban India (shared bedroom, PG/hostel, noisy ceiling fan or commute).
- Mid-range Android phone (`360x800 dp`).
- High fear of someone glancing at their screen and seeing "THERAPY / ANXIETY / DEPRESSION".

### OUTPUT FORMAT
1. **Top 5 Acute-Episode UX Failures:** Rank the top 5 UI/UX mechanics that made users quit mid-exercise (quote verbatim review snippets as evidence).
2. **The "Do Not Build" Anti-Pattern Rulebook:** For each failure, write a strict engineering & UI constraint for Mira V0.03 (e.g., "NEVER require more than 1 tap before the grounding mechanic starts").
3. **Shared-Room & Noisy-Environment Failure Modes:** Identify where voice-only or audio-only flows fail in Indian households and specify the exact touch/visual fallback mechanic required.
4. **Toxic Positivity & Clinical Cringe Lexicon:** List exact words/phrases from these apps that users hated, paired with natural Indian Gen-Z / Hinglish-friendly replacements (Grade 4–6 English).
```

### Pre-Synthesized Anti-Pattern Kill List (What Mira V0.03 Explicitly Eliminates)

| Legacy Mental Health App Anti-Pattern | Why Users Hate It in 2–3 Star Reviews | Mira V0.03 Synthesized Counter-Rule |
| :--- | :--- | :--- |
| **Mood-Slider Gatekeeping Before Help** (e.g., logging 5 emotions + tags before opening a breathing tool) | When a user's chest is tight, answering a survey increases panic and cognitive load. | **Zero-Gate Launch:** Tapping `60s Breath Reset` or `5-4-3-2-1 Grounding` opens the active canvas in `<300ms` with Mira's voice co-piloting immediately. |
| **Multi-Box CBT Thought Record Tables** (e.g., typing "Automatic Thought", "Cognitive Distortion", "Rational Response" on a mobile keyboard) | Typing paragraphs on a `360×800 dp` screen feels like homework and triggers executive dysfunction. | **Speak-and-Shatter (`Overthinking Pop`):** User speaks the *"What-If"* in 10 seconds → traps inside a 2.5D glass sphere → 3 physical thumb taps shatter it into a 1-sentence grounded truth card. |
| **Streak Guilt & Pet Punishment** (e.g., losing a 40-day streak or disappointing a virtual pet after a depressive episode) | Users who miss a day due to burnout feel shamed by sad mascot animations and uninstall. | **Zero-Guilt Momentum:** Every action produces a standalonePhonePe-style completion card (`3 Small Wins` constellation or burned noise receipt) with zero punitive streak counters. |
| **"CLINICAL THERAPY" Screen Banners** (e.g., pastel illustrations with giant headers saying *Anxiety & Panic Relief*) | Impossible to use on the Mumbai Metro, in a college library, or next to a roommate without stigma. | **Over-the-Shoulder Stealth Aesthetic:** Dark stone/obsidian surfaces (`#121110` / `#1C1917`), abstract [React Native Skia](https://docs.expo.dev/versions/latest/sdk/skia/) shaders, and geometric orbs that look like a sleek music visualizer or focus utility. |
| **Audio-Only Guided Meditations** (e.g., 10-minute voice tracks with a static play/pause button) | Users zone out and keep doomscrolling while the audio plays, or cannot listen out loud in a shared room. | **Mandatory Hardware Verb + 2-Line Synced Captions:** Every action pairs Mira's WebRTC voice with a physical thumb/sensor mechanic *and* Spotify-style 2-line live captions so it works at 0% volume or on earpiece routing. |

---

## Stage 4: Cross-App Synthesis Matrix (Mapping Best-of-Breed UX to Mira's 9 Actions)

Instead of designing 9 screens from scratch, every action in Mira V0.03 is synthesized by combining **one gold-standard psychological/mental-health flow** with **one high-frequency consumer or game-feel flow**, minus the **anti-patterns** identified in Stage 3.

### Master UI/UX Synthesis Matrix for Mira's 9 Actions

| # | Mira Action Title | Mental Health UX Donor (Psychological Pacing) | Consumer / Game-Feel UX Donor (Muscle Memory) | Synthesized Mira V0.03 UI/UX & Hardware Mechanic |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Brain Dump ("Our Do")** | [Goblin Tools](https://goblin.tools/) (*Magic ToDo* AI task splitter) + [Tiimo](https://www.tiimoapp.com/) (brain-dump to visual checklist) | [WhatsApp Voice Notes](https://faq.whatsapp.com/657157755756612) (swipe-up mic lock) + [Google Keep](https://www.androidpolice.com/google-keep-gemini-voice-checklist-notes/) + Tinder card physics | **Lock Mic & Rant → Swipe Right to "Do" / Hold to Burn:** Slide thumb up to lock mic and rant in Hinglish; live phrases float up as pills; AI splits into `Do's` (swipe right to snap into checklist) vs. `Noise` (long-press to incinerate in a [React Native Skia](https://docs.expo.dev/versions/latest/sdk/skia/) ash shader). |
| **2** | **60s Breath Reset** | [Balance](https://themindcompany.com/apps/balance) + [Headspace](https://www.headspace.com/) (paced breathing orb) + [Stanford Cyclic Sighing](https://med.stanford.edu/news/insights/2023/02/cyclic-sighing-can-help-breathe-away-anxiety.html) | Instagram Reels (hold-canvas interaction) + [Endel](https://endel.io/) (reactive fluid shaders) | **Thumb-Hold Charge & Release:** User holds thumb on the lower orb (`y = 460–700 dp`) to expand a liquid Skia sphere with double-inhale [Expo Haptics](https://docs.expo.dev/versions/latest/sdk/haptics/) heartbeat pulses; lifting thumb (or blowing into mic) scatters stardust particles across 4 cycles (`60s`). |
| **3** | **5-4-3-2-1 Grounding** | [Calm 5-4-3-2-1 Guide](https://www.calm.com/blog/5-4-3-2-1-a-simple-exercise-to-calm-the-mind) + [Finch](https://finchcare.com/) (*First Aid* sensory step-down) | [Duolingo](https://www.duolingo.com/mobile) (tactile node bursts + ascending pitch marimba pops) | **Tactile 5→4→3→2→1 Step-Down Counter:** 5 translucent glass orbs in the thumb zone; each spoken item (detected via WebRTC VAD) or thumb tap pops an orb with an ascending marimba note and `Light` haptic impact down to 1 central anchor ripple. |
| **4** | **2-Min Task Reset ("Just Start")** | [Tiimo](https://www.tiimoapp.com/) (visual countdown timer) + [Goblin Tools](https://goblin.tools/) (micro-step reducer) | [Google Clock](https://9to5google.com/2026/09/03/google-clock-timers-redesign/) + PhonePe slide-to-pay confirmation | **Slide-to-Ignite Perimeter Fuse + Live Body Double:** Pick 1 tiny 2-minute action with Mira → slide the bottom ignition pill to light a golden Skia perimeter fuse around the `360×800 dp` screen edges with a lo-fi beat while Mira stays silently on the call. |
| **5** | **Mobile Detox ("Flip the Vault")** | [Opal](https://www.opal.so/blog/designing-for-wellbeing) (focus commitment blocks) + [Forest](https://forestapp.cc/) (abandonment penalty) | Apple Watch / Android rotary alarm dial + `expo-sensors` accelerometer | **180° Physical Phone Flip Lock:** Spin a tactile haptic dial (`10m / 20m / 30m`) → countdown **only activates when the phone is physically flipped face-down** (`z > 0.85g`). Picking the phone up early triggers a private earpiece whisper from Mira (*"Still 6 minutes left—flip me back over"*). |
| **6** | **Overthinking Pop ("Kill the What-If")** | [How We Feel](https://howwefeel.org/) (high-contrast emotional framing) + ACT Cognitive Defusion | Mobile brick-breaker / glass-shatter physics ([React Native Reanimated](https://docs.swmansion.com/react-native-reanimated/) + Skia) | **3-Tap Glass Bubble Shatter:** Speak the catastrophic *"What-If"* aloud → text traps inside a vibrating 2.5D frosted glass sphere → tap 3 times with rising `Medium -> Heavy` haptics to fracture and shatter the glass, revealing a calm, grounded 1-line truth card underneath. |
| **7** | **Tension Drop ("Squeeze & Release")** | [Jacobson's PMR](https://www.healthline.com/health/progressive-muscle-relaxation) + [Balance](https://themindcompany.com/apps/balance) body scan | Racing game throttle hold (`Gesture.LongPress` charge + release wave) | **5-Second Hard Press → Instant Gravity Wave:** Across 3 zones (`Shoulders`, `Jaw`, `Hands`), user presses and holds the screen for 5s while clenching muscles (Skia ring contracts to amber + accelerating `150ms` haptic pulse) → lifting thumb unleashes a downward gravity wave shader and sub-bass exhale chord. |
| **8** | **3 Small Wins ("Mood Shift")** | [UC Berkeley Three Good Things](https://ggia.berkeley.edu/practice/three-good-things) + [Daylio](https://daylio.net/) (1-tap micro-chips) | Sky: Children of the Light / [Duolingo](https://www.duolingo.com/mobile) star-node constellation snap | **3-Star Constellation Snap:** Night-sky canvas with 3 unlit star sockets (*1 Tiny Win, 1 Comfort, 1 Person/Vibe*). Speaking a 4-word answer or tapping a quick Hinglish/English chip ignites each [Rive React Native](https://rive.app/docs/runtimes/react-native/react-native) star node and draws glowing Skia constellation lines into a shareable/saveable 3-point card. |
| **9** | **3 AM Sleep Drift ("Cognitive Shuffle")** | [Loóna](https://loona.app/) (sleepscape wind-down) + [Endel](https://endel.io/) (circadian soundscape fade) | OLED Always-On Display auto-dimmer + Spotify sleep timer auto-hangup | **Progressive 0-Lux Blackout + Slow Sensory Stream:** Screen luminance smoothly steps down (`#1C1917 → #0A0908 → #030303`) with zero bright buttons while Mira whispers disconnected cozy imagery every 10s over monsoon rain and automatically terminates the WebRTC call when breathing slows or timer ends. |

### Prompt 3: Cross-App UI/UX Synthesizer Prompt (Copy-Pasteable)

Use this prompt to synthesize any new action or refine one of the 9 catalog actions by feeding in two Stage 2 JSON deconstructions and your Stage 3 friction rules:

```markdown
### ROLE
You are a Principal Mobile Game Designer, Staff React Native Architect, and Voice-First UX Lead for Mira V0.03.

### INPUT ARTIFACTS
1. **Target Mira Action:** [e.g., Action #1: Brain Dump ("Our Do") / Action #6: Overthinking Pop]
2. **Donor Flow A (Mental Health / Psychological Structure JSON):**
   [PASTE STAGE 2 JSON FROM HOW WE FEEL / FINCH / GOBLIN TOOLS / TIIMO]
3. **Donor Flow B (Consumer Muscle Memory / Game-Feel JSON):**
   [PASTE STAGE 2 JSON FROM WHATSAPP / SPOTIFY / DUOLINGO / GOOGLE KEEP]
4. **Mira V0.03 Anti-Pattern Constraints:**
   - Viewport: `360x800 dp` Android, all primary interactions inside `y = 440–760 dp` thumb zone.
   - Paradigm: "Session, not chat." Mira's WebRTC voice co-pilots every state transition.
   - Zero multi-box text forms, zero clinical jargon, max 18 words on screen at any moment.
   - Must work both with voice aloud AND silent thumb-tap fallback (for shared Indian bedrooms/PGs).

### TASK: SYNTHESIZE THE OPTIMAL MIRA V0.03 MICRO-INTERVENTION UX
Combine the psychological pacing of Donor A with the zero-tutorial muscle memory of Donor B to output a unified Mira V0.03 Action Specification:

1. **The Living Card Preview (Actions Deck State):**
   - Specify the exact looping 60 FPS [Rive](https://rive.app/docs/runtimes/react-native/react-native) or [React Native Skia](https://docs.expo.dev/versions/latest/sdk/skia/) micro-animation that runs inside the `160x200 dp` card on the Actions Deck before the user taps it.
2. **Spatial Wireframe (`360x800 dp` Coordinate Map):**
   - Exact `x, y, width, height` bounds for:
     - Top segmented progress bar & WebRTC live-call mini-pill (`y: 0–110 dp`)
     - Center visual stage & 2-line Spotify-style synced voice caption (`y: 110–440 dp`)
     - Thumb interaction zone & silent-mode quick chips (`y: 440–760 dp`)
3. **Second-by-Second Dual-Modality Choreography (`0s` to `90s`):**
   - Create a synchronized timeline table with 5 columns: `Time Window`, `Mira Voice Cue (English/Hinglish)`, `User Physical Verb (Voice Mode)`, `User Physical Verb (Silent Shared-Room Mode)`, and `Visual + Haptic Response`.
4. **Unified Finite State Machine (FSM) & WebRTC Event Contract:**
   - Define every state, transition event (`VAD_SPEECH_START`, `INTERIM_ASR_PARTIAL`, `MIRA_TTS_DONE`, `GESTURE_HOLD_COMPLETE`, `ACCEL_FACE_DOWN`), and payload sent to/from the FastAPI backend.
```

---

## Stage 5: Mid-Range Android & Shared-Room Stress-Test Rubric (The 5-Gate UI Audit)

Before passing any synthesized UI specification to a coding agent, run it through this **5-Gate Stress-Test Prompt**. This prevents AI coding tools from generating heavy DOM/view trees that drop below 30 FPS on a ₹15,000 Android phone or screens that embarrass a student in a shared room.

### Prompt 4: The 5-Gate UI/UX Stress-Test & Revision Prompt

```markdown
### ROLE
You are a Ruthless Android Performance Engineer and Indian Gen-Z UX Critic.

### INPUT
Review the synthesized UI/UX specification below for Mira V0.03:
"""
[PASTE SYNTHESIZED UI SPEC FROM STAGE 4]
"""

### AUDIT RUBRIC (SCORE EACH GATE PASS / FAIL WITH EXACT FIXES)

1. **Gate 1: One-Handed `360x800 dp` Thumb Ergonomics**
   - Are 100% of primary interactive targets (hold orbs, swipe cards, mic lock, quick chips) positioned within `y = 440–760 dp` with a minimum touch target of `48x48 dp`?
   - If any primary button is above `y = 400 dp` (except the top-right close/minimize pill), FAIL and relocate it.

2. **Gate 2: "Over-the-Shoulder Stealth" Privacy Check**
   - If a roommate, parent, or metro passenger glances at this `360x800 dp` screen from 1 meter away, does it look like a sleek music player, ambient timer, or geometric mini-game—or does it scream "MENTAL HEALTH THERAPY / PANIC ATTACK"?
   - Strip out any clinical headers, crying emojis, or diagnostic labels.

3. **Gate 3: Shared-Room Silent Fallback & Ceiling-Fan Noise Resilience**
   - Can the user complete 100% of this activity at 0% speaker volume without speaking a single word aloud (using thumb taps, press-holds, swipes, or quick chips)?
   - If the user *is* speaking in a room with a loud ceiling fan, how does the UI confirm voice capture without relying solely on accurate full-sentence ASR (e.g., using WebRTC microphone RMS amplitude to drive orb glow + tappable fallback chips)?

4. **Gate 4: 60 FPS Mid-Range Android Render Budget (6GB RAM, Snapdragon 695 / Dimensity 6080)**
   - Are animations running entirely on the UI thread via [React Native Reanimated](https://docs.swmansion.com/react-native-reanimated/) `useSharedValue` worklets and single-canvas [React Native Skia](https://docs.expo.dev/versions/latest/sdk/skia/) shaders?
   - Flag and eliminate any React state (`useState`) updates inside `60Hz` gesture/audio loops, heavy multi-layer blurred React `<View>` trees, or unthrottled sensor listeners (`Accelerometer.setUpdateInterval` must be `>= 32ms` or `100ms` depending on the mechanic).

5. **Gate 5: Zero-Jargon Grade-4 Hinglish/English Micro-Copy**
   - Is every on-screen text string `<= 12 words`?
   - Rewrite any stiff clinical copy into warm, grounded peer language (e.g., replace *"Identify three cognitive gratitude anchors"* with *"3 small things that didn't suck today"*).

### OUTPUT
Output a revised, 100% compliant specification with all failed gates corrected.
```

---

## Stage 6: Spec-to-Code Generation Pipeline (JSON Spec to React Native + Skia/Rive/WebRTC)

Never ask an AI coding agent (Cursor, Windsurf, or Claude Code) to *"build the Mira Actions page."* Feed it **one synthesized action state machine at a time** alongside a strict architectural harness so every action plugs into Mira's active WebRTC voice session cleanly.

### Standard TypeScript Interface Contract for All 9 Mira Actions

Every generated action component in Mira V0.03 adheres to a single shared contract so the **Actions Deck** and the **Live Call Bottom Sheet** can mount any of the 9 activities interchangeably:

```typescript
export type MiraActionId =
  | 'brain_dump_our_do'
  | 'breath_reset_60s'
  | 'grounding_54321'
  | 'task_reset_2min'
  | 'mobile_detox_flip'
  | 'overthinking_pop'
  | 'tension_drop_pmr'
  | 'three_small_wins'
  | 'sleep_drift_3am';

export interface MiraWebRTCCoPilotBridge {
  /** Current live caption line spoken by Mira (max 2 lines, Spotify-style) */
  miraCaption: string;
  /** Real-time microphone RMS amplitude (0.0 to 1.0) driven on UI thread */
  userMicAmplitudeSV: SharedValue<number>;
  /** Latest interim or final spoken phrase from user (English/Hinglish) */
  latestUserUtterance: string | null;
  /** Whether the user is in Silent/Shared-Room Mode (earpiece or muted mic) */
  isSilentSharedRoomMode: boolean;
  /** Emit a structured state transition event to the FastAPI + WebRTC voice agent */
  sendActionEventToMira: (
    event:
      | 'ACTION_STARTED'
      | 'STEP_COMPLETED'
      | 'USER_SPOKE_ITEM'
      | 'USER_TAPPED_CHIP'
      | 'PHONE_FLIPPED_DOWN'
      | 'PHONE_PICKED_UP_EARLY'
      | 'ACTION_COMPLETED',
    payload?: Record<string, unknown>
  ) => void;
}
```

### Prompt 5: Spec-to-React-Native Component Generator (Cursor / Claude Code / Windsurf)

```markdown
### ROLE
You are a Staff React Native Graphics & Audio Engineer.

### CONTEXT & TECH STACK
We are building a single self-contained micro-intervention screen for **Mira V0.03** on a `360x800 dp` Android viewport:
- **Animation & Graphics:** `@shopify/react-native-skia`, `@rive-app/react-native`, `react-native-reanimated` (v3 worklets), `react-native-gesture-handler` (v2 `Gesture.Pan`, `Gesture.Tap`, `Gesture.LongPress`).
- **Sensors & Haptics:** `expo-haptics`, `expo-sensors` (`Accelerometer`).
- **Voice Co-Pilot Integration:** Connects to an active WebRTC voice call via the `MiraWebRTCCoPilotBridge` prop interface.

### INPUT SPECIFICATION
Here is the synthesized, Gate-Audited UI/UX & State Machine specification for Action #[X]:
"""
[PASTE VALIDATED SPEC FROM STAGE 5]
"""

### STRICT IMPLEMENTATION RULES
1. **Zero Main-Thread Frame Drops:** Drive all continuous animations (orb expansion, tension rings, perimeter fuses, particle scatter, glass fracture) via Reanimated `useSharedValue` and `useDerivedValue` wired directly into `<Canvas>` (`@shopify/react-native-skia`) or `<Rive>` inputs. Never call `setState` inside a gesture frame or audio-amplitude tick.
2. **Strict `360x800 dp` Ergonomic Zoning:**
   - Top Bar (`0–110 dp`): Segmented progress pills + Mira active voice waveform indicator + minimize-to-call button.
   - Center Stage (`110–440 dp`): Primary Skia/Rive visual canvas + 2-line high-contrast synced caption (`#F5F5F4` on `#121110` background).
   - Thumb Zone (`440–760 dp`): Primary physical hardware verb target (`GestureDetector`) + 1-tap silent fallback chips for shared-room use.
3. **Synchronized Haptics:** Trigger `Haptics.impactAsync` or `Haptics.notificationAsync` via `runOnJS` at exact state transitions, threshold crossings, and completion snaps.
4. **WebRTC Co-Pilot Reactivity:** Automatically advance or pulse the current state when `latestUserUtterance` updates OR when the user performs the touch/sensor gesture, firing `sendActionEventToMira` on each transition so Mira's voice responds in real time.

### DELIVERABLE
Output the complete, production-ready TypeScript file `Action[Name]Screen.tsx` plus its companion `Action[Name]CardPreview.tsx` (the looping living card component for the Actions Deck) with zero TODO placeholders.
```

---

## Worked End-to-End Example: Running Action #6 ("Overthinking Pop") Through the 6-Stage Pipeline

To see how the entire system operates in practice, here is the condensed trace for **Action #6: Overthinking Pop ("Kill the What-If")**:

1. **Stage 1 (Harvest):**
   * *Mental Health Donor:* [How We Feel](https://howwefeel.org/) (high-contrast dark canvas + single-emotion focus) and traditional CBT Thought Defusion tools.
   * *Consumer/Game Donor:* Mobile glass-shatter / bubble-pop physics games + [WhatsApp Voice Notes](https://faq.whatsapp.com/657157755756612) hold-to-speak.
2. **Stage 2 (Deconstruct):**
   * Extracted the 4-state loop: `CAPTURE_THOUGHT` → `CONTAIN_IN_OBJECT` → `PHYSICAL_DESTRUCTION_VERB` → `GROUNDED_REFRAME_CARD`.
3. **Stage 3 (Friction Mine):**
   * 2-star reviews of CBT apps show users despise typing out "Cognitive Distortions" on a keyboard when anxious about a text message or exam result.
   * *Fix:* Replace typing with a 5-second voice rant (or 1-tap preset chip like *"They're mad at me"* / *"I'm gonna fail"*) that visually traps the worry inside a vibrating 2.5D frosted glass sphere.
4. **Stage 4 (Synthesize):**
   * **State 1 (`TRAP`):** User speaks or taps the *"What-If"*. The phrase appears trapped inside a taut, vibrating Skia frosted glass orb in the thumb zone (`y = 460–680 dp`). Mira says: *"Okay, see that 'what-if' floating there? It's just a loud thought, not a fact. Tap the glass three times to crack it."*
   * **State 2 (`CRACK_1` & `CRACK_2`):** Thumb Tap 1 draws a glowing Voronoi fracture line across the orb + `Haptics.impactAsync(Medium)`. Thumb Tap 2 deepens the fracture lines + `Haptics.impactAsync(Heavy)` + amber internal glow.
   * **State 3 (`SHATTER_AND_REFRAME`):** Thumb Tap 3 shatters the orb into 24 Skia glass shards with outward velocity and `Haptics.notificationAsync(Success)`, revealing a warm, grounded card underneath with Mira's 1-sentence reality check (*"One awkward reply doesn't erase a whole friendship. Breathe."*).
5. **Stage 5 (5-Gate Audit):**
   * Passes Stealth Check (looks like an abstract geometric glass puzzle, zero clinical headers), works 100% silently via preset chips + 3 thumb taps, and runs in a single `<Canvas>` with 24 pre-allocated shard vectors (`60 FPS` on mid-range Android).
6. **Stage 6 (Spec-to-Code):**
   * Compiled directly into `ActionOverthinkingPopScreen.tsx` + `OverthinkingPopCardPreview.tsx` via **Prompt 5**.
