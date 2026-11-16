"""Довгі тексти /luts англійською: описи паків, інструкції, юридичні сторінки.

Умови збігаються з умовами бота (texts/en.json → terms): поки покупка йде через Telegram, діють вони.
"""

PACK_COPY = {
    "apple_log_film": {
        "tagline": "Three film looks built straight on Apple Log.",
        "text": "Shoot Log in Blackmagic Camera, pick a look, done. No conversion LUT needed.",
        "pair": "s-beach",
        "tint": "tint-amber",
    },
    "rec709_collection": {
        "tagline": "Eight looks for normal iPhone video.",
        "text": "V1 to V8, from soft teal to amber shadows, for footage shot in the default Rec.709 mode. These eight are not sold anywhere else.",
        "pair": "s-forest",
        "tint": "tint-teal",
    },
    "cinematic_pro_15": {
        "tagline": "My main grading set.",
        "text": "Teal, film print, night city, warm skin. Thirteen looks, and every one of them is also sold on its own.",
        "pair": "s-sunset",
        "tint": "tint-rose",
    },
}
HERO_PAIR = "s-lift"

GUIDES = {
    "blackmagic-camera": {
        "title": "How to install LUTs in Blackmagic Camera",
        "desc": "Step by step: import .cube LUTs into the Blackmagic Camera app on iPhone and apply one while you film.",
        "intro": "Blackmagic Camera reads .cube files. Import them once and they stay in the app.",
        "steps": [
            ("Save the zip to Files", "Open the file in Telegram, tap Share, then Save to Files. Unzip it if iOS has not done it for you.", "01-guide-14-tg-download"),
            ("Open the LUTs Manager", "In Blackmagic Camera open the LUTs Manager.", "02-guide-15-lut-manager"),
            ("Tap Import LUT", "Choose Import LUT to open the file picker.", "03-guide-16-import-lut-btn"),
            ("Open the LUTs folder", "Go to the folder where you saved the files.", "04-guide-17-select-folder"),
            ("Select All, then Open", "The whole pack is imported in one go.", "05-guide-18-select-all"),
            ("Pick your look", "Tap the LUT button on the camera screen and choose a look. You film with the color already on screen.", "06-guide-19-apply-lut"),
        ],
        "tip": "Filming in Apple Log? Use the Apple Log version of a look. Normal video? Use Rec.709.",
    },
    "capcut": {
        "title": "How to use .cube LUTs in CapCut",
        "desc": "Add a .cube LUT to your clip in CapCut on iPhone.",
        "intro": "Menu names change between CapCut versions, but the idea is the same: import the file, then apply it as a filter.",
        "steps": [
            ("Save the file to Files", "Keep the .cube file where you can find it.", None),
            ("Open your project", "Select the clip, then open Filters or Adjust.", None),
            ("Import the LUT", "Look for the import option for LUTs or custom filters, then choose the .cube file.", None),
            ("Set the strength", "Lower the strength if the look feels too heavy for the shot.", None),
        ],
        "tip": "A LUT made for Rec.709 expects normal footage. Do not stack it on top of Log footage.",
    },
    "vn": {
        "title": "How to use .cube LUTs in VN",
        "desc": "Import a .cube LUT into VN video editor and apply it to a clip.",
        "intro": "VN imports .cube LUTs as filters. Menu names can differ slightly between versions.",
        "steps": [
            ("Save the file to Files", "Keep the .cube file where you can find it.", None),
            ("Open the clip", "Tap the clip in your project, then open Filter.", None),
            ("Import the LUT", "Use the import option for LUTs and pick the .cube file.", None),
            ("Adjust the strength", "Fine-tune the intensity so the look fits the shot.", None),
        ],
        "tip": "Use Rec.709 looks on normal footage and Apple Log looks on Apple Log footage.",
    },
    "lumafusion": {
        "title": "How to use .cube LUTs in LumaFusion",
        "desc": "Load a .cube LUT into LumaFusion and apply it to a clip.",
        "intro": "LumaFusion supports custom .cube LUTs. Menu names can differ slightly between versions.",
        "steps": [
            ("Save the file to Files", "Keep the .cube file where you can find it.", None),
            ("Open the clip's effects", "Select the clip, then open Effects.", None),
            ("Add the LUT", "Choose the LUT effect and load the .cube file from Files.", None),
            ("Check the look", "Scrub through the clip and lower the intensity if needed.", None),
        ],
        "tip": "Match the look to the footage: Rec.709 for normal video, Apple Log for Log.",
    },
}

COMPARE = {
    "title": "Rec.709 or Apple Log: which LUT should I use?",
    "desc": "A short guide to picking the right version of a LUT for your iPhone footage.",
    "blocks": [
        ("Short answer", "Pick the version that matches how you filmed. Normal iPhone video is Rec.709. Footage recorded in Apple Log needs an Apple Log look."),
        ("Rec.709", "This is what the iPhone records by default. The colors are already baked in, so a Rec.709 look goes on top and is ready at once. It works on every iPhone and in every editor."),
        ("Apple Log", "Apple Log is a flat recording with more room in the highlights and shadows. It looks washed out until a LUT is applied. You need an iPhone 15 Pro or newer. The extra room is why many people grade Log."),
        ("Not sure?", "Look at the footage. If it already looks normal, it is Rec.709. If it looks grey and flat, it is Log. Never put a Rec.709 look on Log footage, or the other way around."),
    ],
}

LEGAL = {
    "terms": {
        "title": "Terms and license",
        "body": [
            ("1", "You get digital LUT files (.cube) in the Telegram chat right after payment in Telegram Stars."),
            ("2", "Use them in your own photos and videos, including commercial work. Do not share or resell the files."),
            ("3", "If a file does not work on your phone, write to /paysupport in the bot. You get another version or a refund of your Stars. You also get one no-questions refund per account within 7 days, for single LUTs and packs. A refund ends the license."),
            ("4", "Free Starter looks are CC0 works of their authors."),
            ("5", "The English version prevails."),
        ],
    },
    "privacy": {
        "title": "Privacy",
        "body": [
            ("Telegram", "In the bot we store your Telegram ID, name, language, the link you came from, your purchases and support messages. We use them only to deliver files and help you. We do not share them. Payments are processed by Telegram. Send /deletedata in the bot to delete your data."),
            ("This site", "The site sets two small first-party cookies: one remembers where you came from, the other is a random visitor id. They count visits and clicks to the bot. They hold no name, email or other personal data, and we keep the counts for 90 days. There are no ad trackers."),
        ],
    },
    "refund": {
        "title": "Refunds",
        "body": [
            ("If a file does not work", "Write to /paysupport in the bot. You get another version or your Stars back."),
            ("No-questions refund", "One per account, within 7 days of purchase, for single LUTs and packs. A refund ends the license for that product."),
            ("How", "Purchases are made in Telegram, so refunds are made there too, in Telegram Stars."),
        ],
    },
    "license": {
        "title": "License",
        "body": [
            ("You may", "Use the LUTs in your own photos and videos, including paid client work and monetised channels."),
            ("You may not", "Share the files, resell them, or put them in your own pack or preset bundle."),
            ("Credits", "Free Starter looks are CC0 works of their authors. Paid LUTs are my own work."),
            ("Personal copy", "Each file you receive carries a license code tied to your purchase."),
        ],
    },
}

SHOT_SIZE = {
    "01-guide-14-tg-download": (540, 197), "02-guide-15-lut-manager": (540, 158), "03-guide-16-import-lut-btn": (540, 216),
    "04-guide-17-select-folder": (540, 235), "05-guide-18-select-all": (540, 249), "06-guide-19-apply-lut": (540, 218),
}


def _merge_pairs(base: list, over: list | None) -> list:
    """Список пар [заголовок, текст]: переклад береться, лише якщо збігається довжина (інакше — англійська)."""
    return [tuple(x) for x in over] if over and len(over) == len(base) else base


def for_lang(lang: str) -> dict:
    """Описи паків, інструкції, порівняння й юридичні сторінки мовою lang (відсутнє — англійською)."""
    from luts_text import load

    tr = load(lang)
    packs = {slug: {**copy, **(tr.get("packs", {}).get(slug) or {})} for slug, copy in PACK_COPY.items()}
    guides = {}
    for name, g in GUIDES.items():
        t = tr.get("guides", {}).get(name) or {}
        steps = g["steps"]
        if len(t.get("steps", [])) == len(steps):
            steps = [(ts[0], ts[1], g["steps"][i][2]) for i, ts in enumerate(t["steps"])]
        guides[name] = {**g, **{k: t[k] for k in ("title", "desc", "intro", "tip") if k in t}, "steps": steps}
    tc = tr.get("compare") or {}
    compare = {**COMPARE, **{k: tc[k] for k in ("title", "desc") if k in tc},
               "blocks": _merge_pairs(COMPARE["blocks"], tc.get("blocks"))}
    legal = {}
    for name, page in LEGAL.items():
        t = tr.get("legal", {}).get(name) or {}
        legal[name] = {"title": t.get("title", page["title"]), "body": _merge_pairs(page["body"], t.get("body"))}
    return {"packs": packs, "guides": guides, "compare": compare, "legal": legal}
