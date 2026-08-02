"""Knowledge base for the Blackmagic Camera (BMC) iOS app on iPhone.

This is the single source of truth for the AI assistant.

CRITICAL: this content mirrors the user's paid guide exactly.
The guide teaches a "set-and-forget" workflow optimized for casual creators
who want great-looking video without manual exposure work or color grading:
- Everything on Auto (Shutter / ISO / WB / Tint)
- HEVC H.265 + 4K
- FPS matched to electrical grid (50 or 60)
- Rec.709 color space (or Apple Log on 15 Pro+)
- Free LUTs from the @blackmagicamera Telegram channel applied as Monitor LUT

The AI must teach this same workflow — NOT a generic cinematography
180-degree-shutter / manual-exposure approach. If a user asks for advanced
cinema settings, the AI may explain them, but the DEFAULT advice always
matches the guide.
"""

BMC_OVERVIEW = """## OVERVIEW
Blackmagic Camera (BMC) is a free professional camera app from Blackmagic Design,
released August 2023. iOS only — no Android version. Free download from the
App Store.

## INTERFACE LAYOUT (memorize these element names — they appear all over)
- **Viewfinder (main screen)** — live preview with controls at the top:
    Shutter | ISO | WB | Tint | FPS | lens switcher
  Plus a **Stabilization** control on the viewfinder (also lives on this main
  screen, NOT in Settings).
  Tap any of those values to change them.
- **Lens switcher** — at the bottom of the viewfinder. Buttons like
    0.5× (ultrawide) | 1× (main) | 2× (telephoto) | 3× (telephoto)
  Available zoom levels depend on the device. You can switch lenses at any
  time, even while recording.
- **Settings (gear icon ⚙️) — bottom-right corner of the viewfinder.**
  Tap it to open the full settings menu (Codec, Resolution, Color Space,
  LUTs Manager, Save Clips to, Enable Vertical Video, etc.).
  IMPORTANT: Stabilization is NOT inside Settings — it's on the main
  viewfinder screen.
"""

BMC_DEFAULTS_CHEATSHEET = """## DEFAULT SETTINGS — the "set and forget" cheat sheet
These are the EXACT defaults from the paid guide. Recommend these for every
generic question unless the user specifies otherwise.

### On the viewfinder (main screen, top controls):
- **Shutter → Auto.** The lock icon next to Shutter must NOT be pressed.
  Its background should be transparent, NOT blue. If it's blue, tap the lock
  to deactivate it — only then does the shutter run automatically.
- **ISO → Auto.** Already on Auto by default — usually nothing to do.
- **WB → Auto.** Tap the WB value, choose Auto.
- **Tint → Auto.** Right next to WB. Tap it, choose Auto.
- **FPS → 50 or 60 depending on country:**
    * **50 fps** — Europe, Africa, Australia, most of Asia (50 Hz mains)
    * **60 fps** — USA, Canada, Mexico, Japan, Korea, Taiwan (60 Hz mains)
  This is critical under indoor lighting (LED, fluorescent). Wrong FPS =
  flickering bars on screen. Often invisible on phone, very visible on TV.
- **LENS** — pick 0.5× / 1× / 2× / 3× per shot. 1× is default.

### Inside Settings (gear icon, bottom-right):
- **Codec → HEVC H.265.** Best codec for iPhone — high quality, smaller files.
  Do NOT recommend ProRes for the default workflow.
- **Resolution → 4K (3840×2160).** Maximum quality for grading with LUTs.
- **Color Space**:
    * **Rec.709** — default for everyone. Image looks finished out of camera.
      Use Rec.709 LUTs for cinematic look.
    * **Apple Log** — only on iPhone 15 Pro / 16 Pro / 17 Pro (A17 Pro / A18 Pro
      / A19 Pro). On iPhone 17 Pro the option is labeled "Apple Log 2" in the
      dropdown. Apple Log gives more dynamic range but footage looks "flat"
      until a Log LUT is applied.
- **Enable Vertical Video → ON (checked).** Required for shooting 9:16
  vertical video for Reels / TikTok / Shorts.
- **Save Clips to → In-App and Photo Library.** So clips go straight into
  iPhone Photos and you can edit / share immediately.

### LUTs (cinematic look without grading):
Free LUT pack lives in Telegram: **@blackmagicamera** (https://t.me/blackmagicamera).
Download the .zip from the pinned post → Save to Files → unzip in Files app →
import via LUTs Manager (see LUTs section below).
"""

BMC_VIEWFINDER_DETAILS = """## VIEWFINDER CONTROLS — exact UI behavior
- **Shutter**: tap to open the shutter picker. There's a LOCK icon — when
  pressed (blue background), shutter is locked at a manual value. When NOT
  pressed (transparent background), shutter is Auto. Default = Auto.
- **ISO**: tap to open ISO picker. Same Auto/manual lock pattern. Default = Auto.
- **WB (white balance)**: tap to choose Auto, or pick a Kelvin preset / custom.
  Default = Auto.
- **Tint**: green/magenta shift. Right beside WB. Default = Auto.
- **FPS**: tap to pick 24 / 25 / 30 / 50 / 60 (and higher on Pro models).
  The guide picks 50 or 60 by region — see DEFAULTS.
- **Lens switcher (bottom)**: 0.5× ultrawide, 1× main, 2× / 3× telephoto.
  Available steps depend on device:
    * iPhone XR / 11 / 12 / 13 / 14 / 15 / 16 (non-Pro): 0.5× + 1× (some 14+ have 2× via crop)
    * iPhone XS / 11 Pro / 12 Pro / 13 Pro: 0.5× / 1× / 2×
    * iPhone 14 Pro+ / 15 Pro+ / 16 Pro+ / 17 Pro+: 0.5× / 1× / 2× / 3× (or 5× telephoto on 15 Pro Max+)
"""

BMC_SETTINGS_MENU = """## SETTINGS MENU (gear icon, bottom-right)
Opening the menu shows the full configuration. Important sections in order:

- **Codec**: HEVC H.265 (recommended), H.264, ProRes (Pro models only, 1080p
  internal max — needs USB-C SSD for 4K ProRes on 15 Pro / 16 Pro / 17 Pro).
- **Resolution**: 1080p HD, 4K (3840×2160) recommended.
- **Frame Rate**: 24 / 25 / 30 / 50 / 60 (higher on Pro). The guide recommends
  50 or 60 by mains frequency.
- **Color Space**: Rec.709, HLG, Dolby Vision (some devices), Apple Log
  (15 Pro / 16 Pro), Apple Log 2 (17 Pro). Guide default = Rec.709, or Apple
  Log on Pro models with A17 Pro / A18 Pro / A19 Pro.
- **Enable Vertical Video**: toggle on for 9:16 capture.
- **Save Clips to**: choose "In-App and Photo Library" so clips are saved
  to the iPhone Photos app automatically (not only inside the BMC app).
- **LUTs Manager**: where you import and activate LUT files (see LUTs section).
- **Slate / Project metadata**: project name, scene/take/reel for organized
  multi-cam shoots. GPS toggle lives here.
- **Audio**: input source (built-in / external USB-C / 3.5mm headset),
  channels, sample rate (default 48 kHz), input gain.
- **Storage**: internal vs external SSD (USB-C on 15 Pro+ / 16 Pro / 17 Pro).
  Format external drive option.

NOTE: There is NO "Wind Reduction" toggle in BMC. For windy outdoor audio,
recommend a physical windscreen (foam / dead-cat) on the mic, or post-cleanup
in DaVinci Resolve voice isolation.
"""

BMC_STABILIZATION = """## STABILIZATION (on the MAIN viewfinder screen — NOT in Settings)
The Stabilization control lives on the main viewfinder screen (the camera
preview), NOT inside the Settings menu. Tap the Stabilization control on
the viewfinder to pick the mode.

Modes:
- **Off** — no stabilization. Use this on a tripod or gimbal — adding software
  stabilization on top of mechanical stabilization causes drifting / "swimming"
  artifacts.
- **Standard** — balanced crop and quality. Reasonable default for general
  handheld.
- **Cinematic** — light smoothing with minimal crop. Best for traveling shots,
  vlog handheld, walking — keeps the motion organic.
- **Extreme** — maximum gimbal-like wobble removal, but applies a heavy crop
  and can introduce jelly / warp artifacts on fast pans. Use for action
  handheld where stability beats minor visual cost.

Quick rule of thumb:
- Tripod / gimbal → Off
- Vlog / walking → Cinematic
- Running / action → Extreme
- Casual handheld where you just want it steady → Standard

Note: this is BMC's IN-APP stabilization, separate from iPhone's hardware
Sensor-Shift OIS (which works passively on Pro / Pro Max from iPhone 12 onward).
The two stack — using a Pro Max with OIS + Cinematic Stabilization gives
the smoothest result without an external gimbal.
"""

BMC_LUTS = """## LUTS — IMPORT AND APPLY (exact guide workflow)

### Step 1 — Get LUTs
The user gets free LUTs from the **@blackmagicamera** Telegram channel
(https://t.me/blackmagicamera). The pinned post contains a .zip file:
1. Tap the .zip in the Telegram post.
2. Save to Files → On My iPhone (or iCloud Drive).
3. Open the Files app, tap the .zip → iOS unzips it into a folder.

Each post in the Telegram channel says whether the LUT pack is for
**Rec.709** or **Apple Log** — the user must match this with their
Color Space setting.

### Step 2 — Import LUTs in BMC
1. Open Settings (gear icon, bottom-right of viewfinder).
2. Tap **LUTs Manager**. ← Note the exact name: "LUTs Manager", not "LUTS tab".
3. Scroll to the bottom of the LUT list.
4. Tap **Import LUT**.
5. iOS Files picker opens. Navigate to the folder where the LUTs were unzipped.
6. Tap **Select** (top-right) → **Select All** to mark all .cube files.
7. Tap **Open** — all LUTs are imported.

### Step 3 — Activate a LUT
In LUTs Manager:
1. Tap a LUT name in the list. You'll see a preview through the viewfinder.
2. **ON button (right side)** — tap it. Background turns BLUE = LUT is now
   showing on screen (Monitor LUT).
3. **Recording icon (left side, next to ON)** — tap it. Background turns BLUE
   = LUT is also baked into the recorded file.
   - Both buttons blue → preview AND recording use the LUT.
   - Only ON blue → preview only; recorded file stays untouched.

### Tip — preview LUTs live
You can tap any LUT name in LUTs Manager to preview it through the viewfinder
in real time, without leaving the app. Pick the one that fits the lighting.
"""

BMC_COLOR_SPACE_LOGIC = """## CHOOSING COLOR SPACE + LUT
This is the most-asked question after "what FPS?". Logic:

- **Rec.709 + Rec.709 LUT** (default for non-Pro / older Pro models):
  Image looks ready out of camera. LUT adds cinematic color. No grading needed.
  Works on EVERY iPhone in the device list.

- **Apple Log + Log LUT** (only on 15 Pro / 16 Pro / 17 Pro):
  Wider dynamic range — recovers more shadows and highlights. Footage looks
  "flat" / "washed out" until a Log LUT is applied. Once the LUT lands, the
  image is rich and cinematic. Apple Log only works on iPhones with
  A17 Pro / A18 Pro / A19 Pro chips. On 17 Pro the dropdown labels it
  "Apple Log 2".

The match between Color Space and LUT is critical:
- Rec.709 footage + Rec.709 LUT = correct.
- Apple Log footage + Log LUT = correct.
- Mismatch = colors look wrong (washed out or oversaturated).
The Telegram channel's post description always specifies which profile each
LUT pack is for.
"""

BMC_TROUBLESHOOTING = """## TROUBLESHOOTING — symptom → fix (matches guide reality)

- **"Shutter is locked / I can't change it / image is too dark or bright"**
  → Tap the **lock icon** next to Shutter on the viewfinder. If its background
  is BLUE, the shutter is manually locked. Tap to make the background
  transparent — shutter goes back to Auto.

- **"Banding / flickering bars under indoor lights"**
  → Wrong FPS for the country's electrical grid.
  - 50 Hz countries (EU / UA / Africa / Australia / most Asia) → set FPS = 50
  - 60 Hz countries (US / Canada / Mexico / Japan / Korea / Taiwan) → set FPS = 60
  Tap FPS on the viewfinder, pick the right value.

- **"Image is shaky when I walk / handheld footage is wobbly"**
  → First check BMC's built-in Stabilization on the main viewfinder screen
  (NOT in Settings — it lives on the main camera preview):
    1. On the main viewfinder, tap the **Stabilization** control.
    2. Pick **Cinematic** for vlog / walking, or **Extreme** for action / running.
    3. Off / Standard usually leave too much wobble for handheld.
  → Then physical fixes that stack:
    1. Hold the phone with both hands, elbows tucked.
    2. For long walking shots, a smartphone gimbal (DJI Osmo Mobile, Insta360
       Flow) gives the smoothest result.
    3. iPhone Sensor-Shift OIS (on Pro Max from iPhone 12 onward) works
       passively in the background — combine with Cinematic stabilization.

- **"My video is being saved only inside the app, not in Photos"**
  → Settings (gear, bottom-right) → **Save Clips to** → set to
  **In-App and Photo Library**. New clips will go to Photos automatically.
  Older clips stay where they were saved.

- **"I can't shoot vertical 9:16 video"**
  → Settings → toggle **Enable Vertical Video** ON (checked).

- **"I don't see the Apple Log option in Color Space"**
  → Apple Log is only on iPhone 15 Pro / 15 Pro Max / 16 Pro / 16 Pro Max /
  17 Pro / 17 Pro Max. On iPhone 17 Pro the option is named "Apple Log 2".
  If your device is non-Pro or older, stay on Rec.709 — the Telegram LUT
  pack has Rec.709 LUTs that look just as cinematic.

- **"I don't see ProRes in Codec"**
  → ProRes is only on Pro / Pro Max from iPhone 14 onward, and the guide
  doesn't recommend ProRes anyway — HEVC H.265 is the recommended codec
  for casual creators (smaller files, great quality). Stick with HEVC unless
  you have a specific Resolve color-grading workflow.

- **"My LUT won't import"**
  → File must be a `.cube` (lowercase extension). Must be reachable from
  Files app (iCloud Drive, On My iPhone, Downloads). LUTs Manager →
  scroll to the bottom of the list → Import LUT → navigate → Select All → Open.

- **"My LUT looks weird / colors are washed out / oversaturated"**
  → Color Space and LUT type don't match. Rec.709 footage needs a Rec.709
  LUT. Apple Log footage needs a Log LUT. Check the Telegram post — it says
  which profile the pack is for, then set Color Space accordingly.

- **"Storage is filling up too fast"**
  → HEVC 4K is already efficient (~0.4 GB/min at 4K30). Options:
    * Lower Resolution to 1080p
    * Lower FPS to 30 (if not for slow-mo)
    * Offload clips to iCloud / external SSD and delete from device
    * For Pro models with ProRes enabled — switch back to HEVC

- **"WB Auto guesses wrong (footage too yellow / too blue)"**
  → Auto WB usually works. If a specific scene fools it, tap WB on the
  viewfinder, switch to manual, pick a Kelvin preset (Daylight / Cloudy /
  Tungsten) or a custom value. Reset to Auto when done.

- **"Audio is clipping / distorted"**
  → Open Settings → Audio. Lower the input level until peaks sit between
  -12 dB and -6 dB on the audio meter. For wind noise: BMC has no wind
  reduction, use a physical windscreen on the mic or clean up in
  post (DaVinci Resolve voice isolation).
"""

BMC_DEVICE_QUIRKS = """## DEVICE-SPECIFIC FACTS
- **No iPhone has a built-in ND filter.** All ND is external (clip-on /
  MagSafe). Only relevant in extreme bright daylight when even Auto Shutter
  can't compensate — a rare edge case for casual users.
- **Camera Control button**: only iPhone 16 Pro / 17 Pro. Acts as a hardware
  shutter / setting wheel.
- **4-mic Spatial Audio array**: iPhone 16 Pro+.
- **Sensor-Shift OIS**: iPhone 12 Pro Max, then all Pro models from 13
  onward — passively stabilizes handheld shots.
- **ProRes (codec)**: only Pro / Pro Max from iPhone 14 onward. Internal
  ProRes capped at 1080p on every device. ProRes 4K always requires a USB-C
  SSD on 15 Pro / 16 Pro / 17 Pro. Guide does NOT recommend ProRes by default.
- **Apple Log (Color Space)**: iPhone 15 Pro / 15 Pro Max / 16 Pro / 16 Pro Max
  (A17 Pro / A18 Pro). On iPhone 17 Pro / 17 Pro Max the option is labeled
  **Apple Log 2** (A19 Pro).
- **High frame rates**: 4K120 only on iPhone 16 Pro / 17 Pro with external SSD.
- **5× telephoto lens**: iPhone 15 Pro Max / 16 Pro Max / 17 Pro Max only.
"""

BMC_SCENE_PRESETS = """## SCENE PRESETS — copy these almost verbatim when the user describes a scene

For each preset, the user keeps everything from the DEFAULTS cheat sheet
(Shutter / ISO / WB / Tint = Auto, HEVC H.265, 4K, region-correct FPS,
LUT from @blackmagicamera) and only tweaks the listed items.

### Vlog / talking head outdoors (walking, daylight)
- Stabilization: **Cinematic** (on the viewfinder)
- Lens: **1×** main camera
- LUT: any cinematic Rec.709 from the Telegram pack
- Tip: avoid harsh midday sun on face — use shade / open shade

### Vlog / talking head indoors (room, mixed light)
- Stabilization: **Standard** if seated, **Cinematic** if walking
- LUT: warm Rec.709 LUT from the pack
- Tip: face a window or soft lamp; avoid backlighting (window behind you)

### Sunset / golden hour
- LUT: warm cinematic LUT from the pack
- Tip: shoot 5–10 min before AND after the sun crosses the horizon —
  the best color is in the "blue hour" right after sunset

### Night street / city
- Stabilization: **Cinematic**
- LUT: cool / cyan-shadows LUT for city neon
- Tip: lean against a wall or pole for stability; ISO Auto will go higher
  but HEVC handles low-light noise reasonably

### Indoor interview (one person, two-shot setup)
- Stabilization: **Off** (you're on a tripod or fixed stand)
- Lens: **1×** main, or **2×** for tight framing
- LUT: skin-tone-friendly Rec.709 LUT
- Tip: key light at 45°, fill light or reflector on the opposite side;
  background slightly darker than face

### Sports / action / running
- Stabilization: **Extreme** (heavy crop, OK for action)
- Lens: pick before the action starts — switching mid-shot loses framing
- LUT: punchy / contrasty Rec.709 LUT
- Tip: pre-focus on where the action will happen; tap to focus there

### Product / food (close-up)
- Stabilization: **Off** (tripod or table)
- Lens: **1×** main; for very close subjects, the main camera focuses closer
  than ultrawide on most iPhones
- Tip: side light for texture; avoid flat front-on light

### Concert / club / live music
- Stabilization: **Extreme** if you're moving in the crowd
- Lens: **1×** or **2×** depending on distance from stage
- Tip: WB Auto handles colored stage lights well; if it gets confused
  (too magenta or too green), tap WB and pick a manual Kelvin like 4000 K

### Wedding / event handheld
- Stabilization: **Cinematic**
- Lens: **1×** main; switch to **0.5×** for wide reception shots,
  **2×/3×** for close moments without intruding
- Tip: shoot extra B-roll (rings, decor, hands, food) — easy LUT-friendly
  cinematic look
"""

BMC_FOCUS_AND_ZOOM = """## FOCUS AND ZOOM
- **Focus**: by default BMC autofocuses on the center / detected subject.
  Tap anywhere on the viewfinder to set focus point on that spot. Long-press
  to lock focus — the focus point stops re-adjusting until you tap again.
- **Manual focus** is available — tap the focus indicator on the viewfinder
  to switch to manual and use the slider. Useful for precise rack focus
  shots or when autofocus keeps hunting in low light.
- **Zoom**: only the **lens switcher** at the bottom of the viewfinder
  gives you optical-quality zoom (0.5× / 1× / 2× / 3× / 5× depending on
  device). Pinch-zoom on the screen IS available but it's digital zoom —
  you lose resolution. Always prefer the lens switcher for clean image.
"""

BMC_AUDIO_DETAILS = """## AUDIO IN DETAIL
- **Input priority**: when an external mic is connected, BMC routes audio
  from it automatically. Plug-in priority: USB-C external mic > 3.5mm via
  Lightning/USB-C adapter > built-in mic. Bluetooth mics work but introduce
  latency and lower bitrate — only acceptable for casual voice memos, not
  production.
- **Recommended mic types** for iPhone:
    * USB-C lavalier (DJI Mic Mini, Rode Wireless Go, Hollyland Lark M2)
    * Shotgun mic with USB-C adapter (Rode VideoMic NTG)
    * 3.5mm wired lav with TRRS-to-USB-C adapter
- **Levels**: in BMC Settings → Audio, lower the input gain so peaks sit
  between -12 dB and -6 dB on the meter. NEVER let peaks touch 0 dB —
  audio will clip and can't be repaired.
- **Headphone monitoring**: plug wired headphones into the USB-C / Lightning
  port (Bluetooth headphones add latency). Set the monitoring volume in
  Audio settings.
- **No Wind Reduction toggle in BMC** — use a physical windscreen / dead-cat
  on the mic, or clean up in DaVinci Resolve voice isolation in post.
"""

BMC_NOT_IN_APP = """## THINGS PEOPLE ASK FOR THAT ARE *NOT* IN BMC iOS
Use this list to give honest, accurate answers when a user asks about
something that doesn't exist in the app. Don't invent menu paths.

- **Wind Reduction** — no toggle. Use physical windscreen or post-cleanup.
- **Built-in ND filter** — no iPhone has internal ND. ND is external clip-on.
- **BRAW (Blackmagic RAW)** — only on Blackmagic hardware cameras (URSA,
  Pocket). iPhone records Apple ProRes (on Pro models), not BRAW.
- **Cinematic mode (Apple's portrait-style background blur for video)** —
  that's an Apple Camera app feature, NOT in BMC. BMC has its own
  "Cinematic" stabilization mode, which is unrelated.
- **Live filters / beauty filters** — BMC is a professional capture app,
  no Snapchat-style face filters or skin smoothing.
- **In-app trimming / editing** — BMC records, it doesn't edit. Use Photos,
  iMovie, LumaFusion, or DaVinci Resolve to cut clips after recording.
- **In-app sharing to Instagram / TikTok** — clips save to Photos (when
  Save Clips to → In-App and Photo Library is set), then share from there.
- **Slow motion above 4K120** — limited by hardware. iPhone 16 Pro / 17 Pro
  do 4K120 with external SSD; older devices cap at 4K60 or 1080p120.
- **Time-lapse mode** — BMC focuses on real-time video; for time-lapse use
  Apple Camera or a third-party app.
- **Photo capture (stills)** — BMC is video-only. Use Apple Camera for stills.
"""

BMC_RESPONSE_PHILOSOPHY = """## ANSWER STYLE — match the guide's philosophy

The paid guide is written for **casual creators** who want cinematic-looking
video WITHOUT learning manual exposure or grading. Default to that mindset.

### Lead with guide defaults
If someone asks "what settings for the beach?", lead with: Shutter Auto,
ISO Auto, WB Auto, Tint Auto, HEVC H.265, 4K, FPS 50 (or 60), Color Space
Rec.709 (or Apple Log on 15 Pro+), apply a LUT from the Telegram channel.

Only switch to manual settings if the user EXPLICITLY asks about motion
blur, 24fps cinematic look, ProRes, or color grading.

### Be terse
- 80–150 words is the sweet spot. Cut filler ("certainly", "I'd be happy
  to help", "as I mentioned earlier", "in conclusion").
- Use bullets or numbered steps — not prose paragraphs.
- One concrete tip is better than three vague tips.

### Format menu paths consistently
Use the arrow chain with bold UI labels:
- "On the **viewfinder**, tap **Stabilization** → **Cinematic**"
- "Open **Settings (gear, bottom-right)** → **LUTs Manager** → scroll to
  bottom → **Import LUT**"

### Personalize when relevant
If the device matters for the answer (Apple Log, ProRes, Camera Control
button, 4K120, telephoto lenses), name the user's device explicitly:
"On your **iPhone 15 Pro**, you can use Apple Log..."

### Anti-hallucination — the most important rule
If you don't actually know whether a feature / menu path exists in BMC,
DO NOT invent one. Either:
- Pick the closest known feature from this knowledge base, OR
- Say "I'm not 100% sure of the exact menu path — open **Settings** and
  scroll until you find [feature]; if it isn't there, the feature might
  not exist in the current BMC version."
Better to admit uncertainty than to mislead the user with a fake path.

### Always recommend the Telegram channel for LUTs
When LUTs come up, mention **@blackmagicamera**
(https://t.me/blackmagicamera) — that's where the user gets the free pack.

### Things that exist in BMC and you must NEVER deny
Stabilization (on viewfinder, modes Off/Standard/Cinematic/Extreme),
Codec (HEVC/H.264/ProRes), Resolution, FPS, Color Space, LUTs Manager,
Import LUT, ON button, recording-bake icon, Save Clips to, In-App and
Photo Library, Enable Vertical Video, Settings gear icon (bottom-right),
Shutter / ISO / WB / Tint / lens switcher controls on viewfinder,
manual focus, focus tap-to-set, audio source picker, audio levels,
slate / project metadata.
"""


def build_full_knowledge() -> str:
    """Returns one combined markdown string for injection into the AI system prompt."""
    sections = [
        BMC_OVERVIEW,
        BMC_DEFAULTS_CHEATSHEET,
        BMC_VIEWFINDER_DETAILS,
        BMC_SETTINGS_MENU,
        BMC_STABILIZATION,
        BMC_FOCUS_AND_ZOOM,
        BMC_AUDIO_DETAILS,
        BMC_LUTS,
        BMC_COLOR_SPACE_LOGIC,
        BMC_SCENE_PRESETS,
        BMC_TROUBLESHOOTING,
        BMC_DEVICE_QUIRKS,
        BMC_NOT_IN_APP,
        BMC_RESPONSE_PHILOSOPHY,
    ]
    return "\n".join(s.strip() for s in sections)
