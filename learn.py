"""Free keyword-targeted articles served at /learn and /learn/<slug>.

These exist to earn search traffic on a *.vercel.app subdomain that carries no
domain authority: every article answers a question people actually type, and
every article links into the paid guides.

Facts here must match bmc_knowledge.py — that module is the source of truth for
the paid guide and the AI assistant, and a public page contradicting it would be
worse than no page at all. Two rules worth restating, because they are the ones
easiest to get wrong:

  * Apple Log exists only on 15 Pro / 15 Pro Max / 16 Pro / 16 Pro Max, and on
    17 Pro / 17 Pro Max where the menu calls it "Apple Log 2". Not on any
    non-Pro model.
  * iPhone does not record BRAW. BRAW is Blackmagic hardware only; iPhone Pro
    models record Apple ProRes.

Quality gate: an article is only linked and submitted to search engines once it
has real substance (MIN_WORDS) and at least one link into a device guide.
`review()` returns the reason it failed, so a thin page is visible rather than
silently dropped.
"""

MIN_WORDS = 800
TELEGRAM_URL = "https://t.me/blackmagicamera"

ARTICLES = [
    {
        "slug": "how-to-import-luts-blackmagic-camera-iphone",
        "title": "How to import LUTs into Blackmagic Camera on iPhone",
        "meta_title": "How to Import LUTs into Blackmagic Camera on iPhone",
        "description": "Step-by-step: download a LUT pack, unzip it in Files, import it through LUTs Manager, and choose whether the look is only previewed or baked into the recording.",
        "updated": "2026-09-16",
        "lede": "A LUT is what turns a correct-but-plain iPhone clip into something that looks graded, without you learning to grade. Blackmagic Camera can load your own .cube files and show them live through the viewfinder — but the import path is buried, and the difference between previewing a look and recording it is one button that nobody explains. Here is the whole workflow.",
        "sections": [
            {
                "h": "What a LUT actually does in this app",
                "p": [
                    "A LUT (Look-Up Table) is a colour map. It takes every colour your sensor recorded and moves it somewhere else — lifting shadows, cooling skin tones, rolling off highlights — according to a recipe someone else already dialled in. In Blackmagic Camera a LUT is applied as a Monitor LUT, which means the app shows you the graded image live on the viewfinder while you shoot.",
                    "That live preview is the part that matters in practice. You are not guessing what the clip will look like after editing; you are framing and exposing against the finished look. If a LUT crushes the shadows in your scene, you see it before you press record, not two hours later.",
                ],
            },
            {
                "h": "Step 1 — get a LUT pack onto your iPhone",
                "p": [
                    "Free packs live in the @blackmagicamera Telegram channel. The pinned post holds a .zip file, and the post description tells you which colour profile the pack was built for — this matters more than which look you like, as the next section explains.",
                ],
                "steps": [
                    "Open the pinned post in the Telegram channel and tap the .zip file.",
                    "Choose Save to Files, then pick On My iPhone or iCloud Drive.",
                    "Open the Files app and tap the .zip once — iOS unzips it into a folder beside it.",
                ],
                "note": "Do not skip the unzip. The Files picker inside Blackmagic Camera can only select .cube files, so a still-zipped pack looks like an empty folder when you get there.",
            },
            {
                "h": "Step 2 — import through LUTs Manager",
                "p": [
                    "The importer is inside the app's settings, not on the viewfinder. The exact menu name is LUTs Manager.",
                ],
                "steps": [
                    "Open Settings — the gear icon in the bottom-right corner of the viewfinder.",
                    "Tap LUTs Manager.",
                    "Scroll to the very bottom of the LUT list.",
                    "Tap Import LUT. The iOS Files picker opens.",
                    "Navigate to the folder you unzipped in step 1.",
                    "Tap Select in the top-right, then Select All to mark every .cube file.",
                    "Tap Open. All of them are imported at once.",
                ],
            },
            {
                "h": "Step 3 — preview, then decide what gets recorded",
                "p": [
                    "Tap any LUT name in the list and the viewfinder immediately shows your scene through it. Cycle through the pack while pointing at the actual light you are about to shoot in — a look that sings outdoors often falls apart under warm indoor bulbs.",
                    "Each LUT row has two buttons, and they do different jobs:",
                ],
                "bullets": [
                    "ON (right side) — tap it and the background turns blue. The LUT is now your Monitor LUT: you see it on screen while recording.",
                    "The recording icon (left, next to ON) — tap it and it turns blue too. Now the look is baked into the recorded file itself.",
                ],
                "p2": [
                    "Both blue means preview and recording use the LUT. Only ON blue means you shoot the untouched image while monitoring the graded one — the safer option if you might want to grade properly later, because a baked-in LUT cannot be removed.",
                ],
            },
            {
                "h": "The mistake that makes everything look wrong",
                "p": [
                    "A LUT is built for a specific colour profile, and it only works on footage shot in that profile. Match them:",
                ],
                "bullets": [
                    "Rec.709 footage needs a Rec.709 LUT. This is the right path on every iPhone, and the default the guide recommends.",
                    "Apple Log footage needs a Log LUT. Apple Log is only available on iPhone 15 Pro, 15 Pro Max, 16 Pro and 16 Pro Max — and on 17 Pro and 17 Pro Max, where the menu calls it Apple Log 2.",
                ],
                "p2": [
                    "Mismatch them and the image looks obviously broken: a Log LUT on Rec.709 footage produces crushed, oversaturated colour, while a Rec.709 LUT on Log footage stays flat and washed out. If a look seems wildly wrong the instant you enable it, check Color Space in Settings before blaming the LUT.",
                ],
            },
            {
                "h": "Why your LUT list might look empty",
                "p": [
                    "Two things account for almost every failed import. The first is the unzip step above. The second is the Files picker: if you saved the pack to iCloud Drive and your phone has not finished downloading it, the .cube files appear greyed out with a cloud icon. Tap one in the Files app first to pull it down, then import.",
                    "If a LUT imports but does nothing on screen, check that you actually tapped ON rather than only selecting the LUT's name. Selecting previews it; ON commits it as the Monitor LUT.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does Blackmagic Camera come with LUTs built in?",
                "a": "It ships with a small set, but the free packs from the @blackmagicamera Telegram channel are built for iPhone footage specifically, and each post tells you whether the pack is for Rec.709 or Apple Log.",
            },
            {
                "q": "Can I remove a LUT after recording with it baked in?",
                "a": "No. If the recording icon was blue, the look is part of the file. Record with only ON enabled if you want the flexibility to grade later.",
            },
            {
                "q": "Do LUTs work on older iPhones?",
                "a": "Yes. Importing and applying LUTs works on every iPhone the app supports, back to iPhone XS. Only Apple Log is restricted to recent Pro models — on everything else you use Rec.709 footage with a Rec.709 LUT.",
            },
            {
                "q": "What file format do the LUTs need to be?",
                "a": ".cube files. The importer will not show other formats in the Files picker.",
            },
        ],
        "related": ["iphone-15-pro", "iphone-13", "iphone-xs"],
    },
    {
        "slug": "apple-log-iphone-which-models-support-it",
        "title": "Apple Log on iPhone: which models have it, and when it is worth using",
        "meta_title": "Apple Log on iPhone: Which Models Support It",
        "description": "Apple Log is limited to recent Pro iPhones, and it is not automatically the better choice. Which models have it, and when Rec.709 gives a better result.",
        "updated": "2026-09-16",
        "lede": "Apple Log gets talked about as the setting that separates amateur footage from professional footage. It is narrower than that: it is a recording profile available on a handful of Pro iPhones that trades a finished-looking image for latitude you only benefit from if you do something with it afterwards. Knowing whether your phone has it, and whether you should turn it on, saves a lot of disappointing clips.",
        "sections": [
            {
                "h": "Which iPhones actually support it",
                "p": [
                    "Apple Log requires an A17 Pro chip or newer, which in practice means the Pro line only:",
                ],
                "bullets": [
                    "iPhone 15 Pro and 15 Pro Max — A17 Pro, listed as Apple Log.",
                    "iPhone 16 Pro and 16 Pro Max — A18 Pro, listed as Apple Log.",
                    "iPhone 17 Pro and 17 Pro Max — A19 Pro, where the Color Space dropdown calls it Apple Log 2.",
                ],
                "p2": [
                    "No non-Pro iPhone has it. That includes recent ones: iPhone 15, 15 Plus, 16, 16 Plus and 17 record in Rec.709 (and Dolby Vision HDR on the models that support it), and no setting will add Log to them. If the option is missing from your Color Space list, your device is the reason — not a bug or a version problem.",
                ],
            },
            {
                "h": "What Log actually changes",
                "p": [
                    "A Log profile records a flatter, lower-contrast image on purpose. Instead of baking a pleasing contrast curve into the file, it spreads the sensor's range more evenly, keeping detail in bright windows and dark corners that a standard profile would clip to white or crush to black.",
                    "The cost is that the file looks wrong straight out of the phone: grey, washed out, undersaturated. That is not a fault. Log footage is an intermediate — it is meant to have a look applied to it, either a Log LUT in the app or a proper grade in editing software.",
                ],
            },
            {
                "h": "When Apple Log earns its place",
                "p": [
                    "Log pays off when the scene has range your phone would otherwise throw away, and when you intend to finish the footage rather than post it straight from Photos. Concretely:",
                ],
                "bullets": [
                    "High-contrast scenes — someone indoors against a bright window, or a face in shade under midday sun.",
                    "Sunsets and mixed lighting, where a standard profile clips the sky or smears the colour transition.",
                    "Work you will grade, or footage that has to intercut with another camera and match it.",
                ],
            },
            {
                "h": "When Rec.709 is the better answer",
                "p": [
                    "For most shooting, most of the time, Rec.709 with a Rec.709 LUT gets you a better result with less work. The image is finished in the camera, the LUT supplies the cinematic colour, and the clip is ready to post the moment you stop recording.",
                    "That is the workflow the device guides recommend by default, and it is not a compromise: even-light scenes — overcast days, interiors with controlled lighting, most talking-head and product shots — have nothing in the highlights or shadows for Log to rescue. You get the flat file and the extra step without the benefit.",
                ],
                "note": "If you shoot Log, you must pair it with a Log LUT. A Rec.709 LUT on Log footage stays flat and lifeless, which is the single most common reason people conclude that Log looks bad.",
            },
            {
                "h": "Turning it on, and what to change alongside it",
                "p": [
                    "Apple Log lives in Settings — the gear icon at the bottom-right of the viewfinder — under Color Space. Select Apple Log (or Apple Log 2 on 17 Pro) and the viewfinder immediately goes flat.",
                    "Before you shoot, go into LUTs Manager and enable a Log LUT with the ON button so the viewfinder shows a graded image again. Judging exposure on a raw Log preview is genuinely hard; monitoring through a LUT puts back the contrast your eye needs to tell whether the shot is right.",
                    "Leave the recording icon off unless you specifically want the look baked in. The whole point of shooting Log is to keep your options open, and baking a LUT into the file throws that away.",
                ],
            },
            {
                "h": "Log is not ProRes, and neither one requires the other",
                "p": [
                    "These two settings get conflated constantly because both live in the Pro-model conversation. They are independent: Color Space controls the tonal profile, Codec controls how the file is compressed. You can shoot Apple Log in HEVC H.265 and get the extra latitude without the enormous files ProRes produces — which, on a phone you also use for everything else, is usually the sensible combination.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does iPhone 16 support Apple Log?",
                "a": "Only the Pro models. iPhone 16 Pro and 16 Pro Max have Apple Log; iPhone 16 and 16 Plus do not.",
            },
            {
                "q": "Why does my Log footage look grey and washed out?",
                "a": "That is what Log looks like before a look is applied. Enable a Log LUT in LUTs Manager to monitor it properly, then apply a Log LUT or grade it when you edit.",
            },
            {
                "q": "Is Apple Log 2 different from Apple Log?",
                "a": "It is the newer version of the profile on iPhone 17 Pro and 17 Pro Max with the A19 Pro chip. The workflow is identical: shoot in it, then apply a Log LUT.",
            },
            {
                "q": "Should I use Apple Log for Reels and TikTok?",
                "a": "Usually not. Short social video rarely gets graded, and Rec.709 with a Rec.709 LUT is finished the moment you stop recording.",
            },
        ],
        "related": ["iphone-15-pro", "iphone-16-pro", "iphone-17-pro"],
    },
    {
        "slug": "prores-vs-hevc-iphone-which-codec",
        "title": "ProRes vs HEVC H.265 on iPhone: which codec should you record?",
        "meta_title": "ProRes vs HEVC H.265 on iPhone: Which to Record",
        "description": "ProRes is the professional option on Pro iPhones, but it is capped at 1080p internally and needs an external SSD for 4K. Here is when H.265 is the better choice.",
        "updated": "2026-09-16",
        "lede": "Codec is the setting people change first and understand last. The short version: HEVC H.265 is the right answer for nearly everyone, ProRes is a specialist tool with real storage consequences, and BRAW — despite the app's name — is not something an iPhone can record at all.",
        "sections": [
            {
                "h": "What each codec is for",
                "p": [
                    "HEVC H.265 is a delivery codec. It compresses hard and cleverly, producing files small enough to keep on a phone while holding up well to normal editing and posting. This is the default the device guides recommend, and on modern iPhones the quality is high enough that the compression is invisible in ordinary use.",
                    "ProRes is an intermediate codec. It compresses lightly, so each frame stays close to what the sensor captured and survives heavy colour work without falling apart. That fidelity comes at a price measured in gigabytes per minute rather than megabytes.",
                ],
            },
            {
                "h": "Which iPhones can record ProRes",
                "p": [
                    "ProRes is a Pro-model feature, from iPhone 14 Pro onward — 14 Pro and Pro Max, 15 Pro and Pro Max, 16 Pro and Pro Max, 17 Pro and Pro Max. No non-Pro iPhone offers it, and neither does any Pro model older than the 14.",
                    "There is a second limit that catches people out: internal ProRes recording is capped at 1080p on every device. Recording ProRes at 4K requires an external USB-C SSD connected to the phone. If you selected ProRes and found your resolution options collapsed, that is why.",
                ],
            },
            {
                "h": "The storage arithmetic",
                "p": [
                    "This is the part worth internalising before a shoot rather than during one. ProRes files are roughly an order of magnitude larger than H.265 files of the same length and resolution. A few minutes of 4K ProRes will consume storage that would have held an hour of H.265.",
                    "On a device that is also your phone — full of photos, apps and messages — that pressure is real. Running out of space mid-shoot is a far more common way to lose a shot than any amount of codec-related quality loss.",
                ],
                "note": "If you do shoot ProRes at 4K, test your SSD and cable before the day you need them. A drive that is too slow will drop frames or refuse to record, and that failure shows up at the worst moment.",
            },
            {
                "h": "So when is ProRes actually worth it",
                "p": [
                    "ProRes earns its cost in a narrow set of situations:",
                ],
                "bullets": [
                    "Footage that will be graded heavily, especially shot in Apple Log, where you are pushing colour and exposure well beyond what the file was captured at.",
                    "Work that has to intercut with a proper cinema camera and match it.",
                    "Paid work where the client expects a mastering-quality original, regardless of whether the difference survives to the final delivery.",
                ],
                "p2": [
                    "Outside those cases, H.265 at 4K gives you a file you can actually store, transfer and edit on the same phone — and for social video, which is recompressed aggressively by every platform anyway, the difference does not survive the upload.",
                ],
            },
            {
                "h": "A note on BRAW",
                "p": [
                    "Because the app is made by Blackmagic Design, people reasonably assume it records Blackmagic RAW. It does not. BRAW is a format for Blackmagic's own hardware cameras such as the URSA and Pocket Cinema line. On iPhone, the professional capture format is Apple ProRes, on the Pro models listed above.",
                ],
            },
            {
                "h": "Heat, battery and long takes",
                "p": [
                    "There is a practical cost to ProRes that specification sheets do not mention. Writing that much data continuously works the phone hard, and a sustained ProRes take heats an iPhone considerably faster than the same take in H.265. A hot phone throttles, and a sufficiently hot one stops recording and tells you to let it cool down.",
                    "Direct sun on a black phone, a thick case that traps heat, and simultaneous charging all compound the problem. If you are shooting a long interview or an event where stopping is not an option, H.265 is the safer format for reasons that have nothing to do with image quality — it simply survives longer takes.",
                ],
                "bullets": [
                    "Take the case off for long recordings, and keep the phone out of direct sun between takes.",
                    "Start with a full battery: high-bitrate recording drains it quickly, and a hot battery drains faster still.",
                    "Break long recordings into shorter takes where the edit allows it, which also protects you from losing everything to one failure.",
                ],
            },
            {
                "h": "Setting the codec",
                "p": [
                    "Codec lives in Settings — the gear icon at the bottom-right of the viewfinder — as the first item in the list. Set it to HEVC H.265 and Resolution to 4K for the default workflow the guides teach. H.264 also appears there; it exists for compatibility with older software and gives you larger files at lower quality than H.265, so there is rarely a reason to choose it.",
                    "One thing codec does not change is how your footage looks. Contrast and colour come from Color Space and any LUT you apply, not from the codec. Choosing ProRes will not make a clip more cinematic — it only makes it more editable.",
                ],
            },
        ],
        "faq": [
            {
                "q": "Does ProRes look better than H.265 on iPhone?",
                "a": "Only under heavy grading. Straight out of the camera and posted as-is, the two are visually indistinguishable — but ProRes files are roughly ten times larger.",
            },
            {
                "q": "Why can I only record ProRes at 1080p?",
                "a": "Internal ProRes is capped at 1080p on every iPhone. 4K ProRes requires recording to an external USB-C SSD.",
            },
            {
                "q": "Can iPhone record BRAW in Blackmagic Camera?",
                "a": "No. BRAW is exclusive to Blackmagic's hardware cameras. iPhone Pro models record Apple ProRes instead.",
            },
            {
                "q": "Which codec should I use for YouTube and Reels?",
                "a": "HEVC H.265 at 4K. Every platform recompresses what you upload, so the extra data in a ProRes file is discarded anyway.",
            },
        ],
        "related": ["iphone-14-pro", "iphone-16-pro", "iphone-15"],
    },
    {
        "slug": "iphone-video-flicker-indoors-50-or-60-fps",
        "title": "Why your indoor iPhone video flickers, and the frame rate that fixes it",
        "meta_title": "iPhone Video Flickers Indoors: 50 or 60 fps Fix",
        "description": "Rolling bands across indoor footage are a frame-rate mismatch with your mains electricity, not a camera fault. Pick 50 or 60 fps by country to fix it.",
        "updated": "2026-09-16",
        "lede": "You film something indoors, it looks fine on the phone, and then on a bigger screen there are dark bands rolling up through the frame. Nothing is broken. Your frame rate is fighting the electricity supply, and the fix is one setting you choose once based on the country you are in.",
        "sections": [
            {
                "h": "Where the bands come from",
                "p": [
                    "Mains electricity alternates, and most indoor lighting brightens and dims along with it — many LED and fluorescent fittings pulse rather than glowing steadily. The pulsing is far too fast for your eyes, which average it into constant light.",
                    "A camera does not average. It samples the scene once per frame, and if the sampling rate does not line up with the pulsing rate, successive frames catch the light at different points in its cycle. Some frames land bright, some dark, and because the sensor reads the image progressively from top to bottom, the mismatch shows up as bands drifting through the picture rather than the whole frame pulsing.",
                ],
            },
            {
                "h": "The fix: match the frame rate to the grid",
                "p": [
                    "When your frame rate divides evenly into the mains frequency, every frame samples the same part of the light cycle, and the flicker vanishes. Which number you need depends purely on where you are:",
                ],
                "bullets": [
                    "50 fps — countries on a 50 Hz grid: Europe, most of Africa, Australia, and most of Asia.",
                    "60 fps — countries on a 60 Hz grid: the USA, Canada, Mexico, Japan, South Korea and Taiwan.",
                ],
                "p2": [
                    "Set it on the viewfinder: tap the FPS value in the top row of controls and choose 50 or 60. It is worth setting once for where you live and leaving it there — this is the single most common cause of indoor footage that looks subtly wrong for no obvious reason.",
                ],
            },
            {
                "h": "Why 24 fps often makes it worse",
                "p": [
                    "Cinema shoots at 24 fps, so people reach for it expecting a filmic result. Under artificial light on either grid, 24 fps does not divide cleanly into the pulsing and is a reliable way to introduce flicker. Outdoors in daylight it is fine — daylight does not pulse — but indoors it fights the lights.",
                    "There is a second reason the guides steer away from it. The cinematic quality people associate with 24 fps comes mostly from lighting, lenses and composition, not the frame rate. A well-lit 50 fps clip reads as far more professional than a flickering 24 fps one.",
                ],
            },
            {
                "h": "When the flicker survives the fix",
                "p": [
                    "Occasionally a light still misbehaves after you have matched the frame rate. Cheap LED bulbs and dimmed fittings are the usual culprits: dimmers chop the waveform in ways that no longer track the grid frequency cleanly, and some inexpensive drivers pulse at their own rate entirely.",
                ],
                "bullets": [
                    "Undim the light if you can, or swap the bulb — a dimmed LED is the most common stubborn case.",
                    "Turn off one offending fixture and rely on the others, or move so the flickering source is out of frame.",
                    "Shoot near a window and let daylight dominate, since daylight cannot flicker.",
                ],
            },
            {
                "h": "Screens in the shot behave the same way",
                "p": [
                    "A television, computer monitor or laptop in frame has its own refresh rate, and it beats against your frame rate exactly as pulsing lights do. The symptom looks slightly different — the screen itself darkens, brightens or shows a band scrolling through it while everything around it looks fine.",
                    "Matching the mains frequency fixes most cases, because monitors in a given region are usually built around the same figure. When it does not, angle the shot so the screen sits outside the frame, or accept it and cut around the affected moments. This is worth checking deliberately whenever you film someone working at a desk.",
                ],
            },
            {
                "h": "Check it on the right screen",
                "p": [
                    "Flicker is frequently invisible on the phone during recording and obvious on a television or monitor. The phone's own display refresh can mask the banding, which is how people end up with an entire shoot ruined by a problem they never saw at the time.",
                    "Before a long take under unfamiliar lighting, record ten seconds, then watch it back full-screen. If bands are drifting through, change the frame rate and shoot the test again — it costs almost nothing compared with discovering it later.",
                ],
                "note": "The frame rate setting and shutter behaviour are separate things. The recommended workflow leaves Shutter on Auto — check that the lock icon beside the shutter value is transparent rather than blue — and fixes flicker with frame rate alone.",
            },
        ],
        "faq": [
            {
                "q": "Should I use 50 or 60 fps?",
                "a": "Pick by the mains frequency where you shoot: 50 fps on a 50 Hz grid (Europe, Australia, most of Asia and Africa), 60 fps on a 60 Hz grid (USA, Canada, Mexico, Japan, Korea, Taiwan).",
            },
            {
                "q": "Why does my footage flicker only indoors?",
                "a": "Daylight is continuous, while most indoor LED and fluorescent lighting pulses with the mains supply. Only the pulsing light can beat against your frame rate.",
            },
            {
                "q": "Does a higher frame rate look less cinematic?",
                "a": "Less so than flicker does. Lighting and composition carry the cinematic look far more than the frame rate, and you can always slow 50 or 60 fps footage down in editing.",
            },
            {
                "q": "Will changing the shutter speed fix flicker instead?",
                "a": "Matching the frame rate to the grid is the reliable fix, and it keeps the recommended Auto shutter workflow intact.",
            },
        ],
        "related": ["iphone-13", "iphone-15", "iphone-16-pro"],
    },
]

ARTICLE_MAP = {a["slug"]: a for a in ARTICLES}


def get_article(slug: str):
    return ARTICLE_MAP.get(slug)


def word_count(article: dict) -> int:
    parts = [article.get("lede", "")]
    for section in article.get("sections", []):
        parts.append(section.get("h", ""))
        parts += section.get("p", [])
        parts += section.get("p2", [])
        parts += section.get("steps", [])
        parts += section.get("bullets", [])
        if section.get("note"):
            parts.append(section["note"])
    for item in article.get("faq", []):
        parts += [item["q"], item["a"]]
    return len(" ".join(parts).split())


def review(article: dict):
    """Return None when the article may be indexed, else the reason it may not.

    A reason, not a silent False: a page dropped from the sitemap without
    explanation is the kind of thing that stays broken for months.
    """
    words = word_count(article)
    if words < MIN_WORDS:
        return f"too thin: {words} words, needs {MIN_WORDS}"
    if not article.get("related"):
        return "no link into a device guide"
    if not article.get("description"):
        return "no meta description"
    return None


def is_indexable(article: dict) -> bool:
    return review(article) is None


def indexable_articles() -> list:
    return [a for a in ARTICLES if is_indexable(a)]
