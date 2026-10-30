import re

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
BRAND_WORDS = {
    "شاومي": "xiaomi", "ريدمي": "redmi", "ردمي": "redmi", "بوكو": "poco",
    "اوبو": "oppo", "رينو": "reno", "فايند": "find",
    "ريلمي": "realme", "ريالمي": "realme", "نارزو": "narzo",
    "هونر": "honor", "هونور": "honor", "اونر": "honor", "ماجيك": "magic",
    "انفينكس": "infinix", "انفنكس": "infinix",
    "فيفو": "vivo", "هواوي": "huawei", "نوفا": "nova",
    "موتورولا": "motorola", "موتو": "moto", "ريزر": "razr",
    "ون بلس": "oneplus", "وان بلس": "oneplus", "ونبلس": "oneplus", "نورد": "nord",
    "تكنو": "tecno", "سبارك": "spark", "كامون": "camon", "فانتوم": "phantom", "بوفا": "pova",
    "ايتل": "itel", "جوجل": "google", "بيكسل": "pixel", "سوني": "sony",
    "اكسبيريا": "xperia", "اكسبريا": "xperia", "نوكيا": "nokia", "لينوفو": "lenovo",
    "انفنيكس": "infinix", "نوبيا": "nubia", "بورا": "pura", "ستايلس": "stylus",
    "رازر": "razr", "بكسل": "pixel",
}

SERIES_WORDS = {
    "برو": "pro", "بلس": "plus", "الترا": "ultra", "ماكس": "max", "لايت": "lite",
    "نوت": "note", "ميني": "mini", "فولد": "fold", "فليب": "flip",
    "بلاي": "play", "برايم": "prime",
    "هوت": "hot", "سمارت": "smart", "ايدج": "edge",
}

ARABIC_RANGE = "\u0600-\u06FF"


def prepare_text(title, letters=None, aliases=None, pre=None):
    text = str(title).lower().translate(ARABIC_DIGITS)
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    for ch in "أإآ":
        text = text.replace(ch, "ا")
    text = text.replace("ى", "ي")
    text = text.replace("+", " plus ").replace("_", " ")
    text = re.sub(r"[^\w\s\.]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    text = re.sub(
        rf"(?<=[{ARABIC_RANGE}])(?=[a-z0-9])|(?<=[a-z0-9])(?=[{ARABIC_RANGE}])",
        " ", text
    )

    all_brand_words = {**BRAND_WORDS, **(aliases or {})}
    for old in sorted(all_brand_words, key=len, reverse=True):
        text = text.replace(old, f" {all_brand_words[old]} ")

    for old, new in SERIES_WORDS.items():
        text = re.sub(rf"(?<![{ARABIC_RANGE}]){old}(?![{ARABIC_RANGE}])", f" {new} ", text)

    text = re.sub(r"\s+", " ", text).strip()

    text = re.sub(r"\bnot\s*(?=\d)", "note ", text)                      # not 10 -> note 10
    text = re.sub(r"(?<=\d)(pro|max|plus|ultra|lite|mini)\b", r" \1", text)  # 14pro -> 14 pro
    text = re.sub(r"(?<=\d)bro\b", " pro", text)                           # x3bro -> x3 pro
    text = re.sub(r"(?<=[a-z])5g\b", " 5g", text)                          # 50s5g -> 50s 5g

    for pattern, repl in (pre or []):
        text = re.sub(pattern, repl, text)

    for old, new in (letters or {}).items():
        text = re.sub(rf"(?<!\S){old}\s*(?=\d)", f" {new} ", text)
        text = re.sub(rf"(?<=\d)\s*{old}(?![{ARABIC_RANGE}])", f"{new} ", text)

    return re.sub(r"\s+", " ", text).strip()


BRAND_CONFIG = {}


def _prediction_result(model_key, match_rule, with_rule):
    """Optionally return the matched rule together with the model key."""
    if with_rule:
        return model_key, match_rule
    return model_key


def extract_brand_model(title, brand, with_rule=False):
    brand = str(brand).strip().lower()
    if brand not in BRAND_CONFIG:
        return _prediction_result("unknown", f"{brand}:unknown_brand", with_rule)

    cfg = BRAND_CONFIG[brand]
    raw = str(title).lower()
    if len(brand) >= 4:
        raw = re.sub(rf"({brand})(?=[a-z0-9])", r"\1 ", raw)
    text = prepare_text(raw, cfg.get("letters"), cfg.get("aliases"), cfg.get("pre"))

    # Number the ordered rules so we can record which one matched.
    for rule_number, (pattern, template) in enumerate(cfg["rules"], start=1):
        match = re.search(pattern, text)
        if match:
            groups = [group or "" for group in match.groups()]
            model = template.format("", *groups)
            model = re.sub(r"\s+", " ", model).strip()
            model = re.sub(r"\b(pro|max|plus|ultra|lite|mini)\b", r"\1", model)

            model_key = f"{brand} {model}".strip()
            match_rule = f"{brand}:rule_{rule_number:02d}"
            return _prediction_result(model_key, match_rule, with_rule)

    return _prediction_result("unknown", f"{brand}:no_match", with_rule)

def extract_iphone_model(title, with_rule=False):
    text = re.sub(r"\s+", " ", str(title).lower().translate(ARABIC_DIGITS)).strip()
    # Multiple alternative models in one title are not a single listing model.
    if re.search(
        r"(?:iphone|i\s*phone|ايفون|آيفون)\s*\d{1,2}.*?(?:\bor\b|او).*?\d{1,2}",
        text,
    ):
        return _prediction_result("unknown", "apple:ambiguous_models", with_rule)

    special_cases = [
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(?:air|اير)\b", "iphone air"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*4\s*(?:s|اس|أس)\b", "iphone 4s"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*6\s*(?:s|اس|أس)\s*(?:plus|بلس)\b", "iphone 6s plus"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*x\s*(?:s|اس|أس)\s*(?:max|ماكس)\b", "iphone xs max"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*x\s*(?:max|ماكس)\b", "iphone x max"),
        (r"ip+h+o+n+e+\s*17\s+pro+m+a+x+", "iphone 17 pro max"),
        (r"ايفون+ن?\s*17\s*برماكس", "iphone 17 pro max"),
        (r"iphoneee?\s*17\s*pro+\s*ma+x+", "iphone 17 pro max"),
        (r"iphone+\s*17\s*pro+\s*ma+x+", "iphone 17 pro max"),
        (r"ايفون\s*17\s*برو+ما+كس", "iphone 17 pro max"),
        (r"ايفون\s*17\s*برماكس", "iphone 17 pro max"),
        (r"iphone\s*pro\s*max\s*17", "iphone 17 pro max"),
        (r"ايفون\s*pro\s*max\s*17", "iphone 17 pro max"),
        (r"iphone\s*3g\b", "iphone 3g"),
        (r"ايفون\s*3g\b", "iphone 3g"),
        (r"ايفون\s*6اس\b", "iphone 6s"),
        (r"ايفون\s*8بلص\b", "iphone 8 plus"),
        (r"ايفون\s*i\s*phone\s*plus\s*7", "iphone 7 plus"),
    ]

    for rule_number, (pattern, model) in enumerate(special_cases, start=1):
        if re.search(pattern, text):
            match_rule = f"apple:special_case_{rule_number:02d}"
            return _prediction_result(model, match_rule, with_rule)
    special_models = [
        (r"\bxs\s*max\b|\bاكس\s*اس\s*ماكس\b", "iphone xs max"),
        (r"\bxs\b|\bاكس\s*اس\b", "iphone xs"),
        (r"\bxr\b|\bاكس\s*ار\b", "iphone xr"),
        (r"\bx\b|\bاكس\b", "iphone x"),
        (r"\b(?:iphone|i\s*phone)\s*se\b", "iphone se"),
        (r"\bايفون\s*اس\s*اي\b", "iphone se"),
        (r"\bايفون\s*اكس\s*اس\s*ماكس\b", "iphone xs max"),
        (r"\bايفون\s*اكس\s*ار\b", "iphone xr"),
        (r"\bايفون\s*اكس\s*اس\b", "iphone xs"),
        (r"\bايفون\s*اكس\b", "iphone x"),
        (r"\b(?:iphone|i\s*phone)\s*xs\s*max\b", "iphone xs max"),
        (r"\b(?:iphone|i\s*phone)\s*xr\b", "iphone xr"),
        (r"\b(?:iphone|i\s*phone)\s*xs\b", "iphone xs"),
        (r"\b(?:iphone|i\s*phone)\s*x\b", "iphone x"),
    ]

    for rule_number, (pattern, model) in enumerate(special_models, start=1):
        if re.search(pattern, text):
            match_rule = f"apple:special_model_{rule_number:02d}"
            return _prediction_result(model, match_rule, with_rule)

    model_patterns = [
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*pro\s*max\b", "pro max"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*برو\s*ماكس\b", "pro max"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*plus\b", "plus"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*بلس\b", "plus"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*ميني\b", "mini"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*pro\b", "pro"),
        (r"(?:iphone|i\s*phone|ايفون|آيفون)\s*(\d{1,2})\s*برو\b", "pro"),
    ]

    for rule_number, (pattern, version) in enumerate(model_patterns, start=1):
        match = re.search(pattern, text)
        if match:
            model_key = f"iphone {match.group(1)} {version}"
            match_rule = f"apple:model_pattern_{rule_number:02d}"
            return _prediction_result(model_key, match_rule, with_rule)

    numeric_pattern = re.compile(
        r"(?:\biphone\s*|\bi\s*phone\s*|ايفون\s*)"
        r"(\d{1,2})\s*(s|e)?\s*"
        r"(pro\s*max|promax|pro|max|plus|mini|air)?\b"
    )

    match = numeric_pattern.search(text)

    if match:
        number = match.group(1)
        suffix = match.group(2) or ""
        version = re.sub(r"\s+", " ", (match.group(3) or "").strip())

        if version == "promax":
            version = "pro max"

        model = f"iphone {number}{suffix}"
        model_key = f"{model} {version}" if version else model
        return _prediction_result(model_key, "apple:numeric_pattern", with_rule)

    match = re.search(
        r"ايفون\s+(pro|max|plus|برو|ماكس|بلس)\s*(\d{1,2})",
        text
    )

    if match:
        version = {
            "برو": "pro",
            "ماكس": "max",
            "بلس": "plus"
        }.get(match.group(1), match.group(1))

        model_key = f"iphone {match.group(2)} {version}"
        return _prediction_result(model_key, "apple:reversed_pattern", with_rule)

    pattern = re.compile(
        r"\b(?:iphone\s*)?(\d{1,2})\s*"
        r"(pro\s*max|pro|max|plus|mini|air|e)?\b"
        r"|ايفون\s*(\d{1,2})\s*"
        r"(برو\s*ماكس|برو|ماكس|بلس|ميني|اير|e)?"
    )

    match = pattern.search(text)

    if not match:
        return _prediction_result("unknown", "apple:no_match", with_rule)

    number = match.group(1) or match.group(3)
    version = (match.group(2) or match.group(4) or "").strip()

    version = {
        "برو ماكس": "pro max",
        "برو": "pro",
        "ماكس": "max",
        "بلس": "plus",
        "ميني": "mini",
        "اير": "air"
    }.get(version, version)

    model_key = f"iphone {number} {version}".strip()
    return _prediction_result(model_key, "apple:fallback_pattern", with_rule)

BRAND_CONFIG["samsung"] = {
    "letters": {
        "ايه": "a",
        "اس": "s",
        "ام": "m",
        "اف": "f",
        "جيه": "j", "جي": "j", "چي": "j",
        "زد": "z",
    },

    "aliases": {
        "جالكسي": "galaxy", "جلاكسي": "galaxy", "جالاكسي": "galaxy",
        "سامسونج": "samsung",
        "جراند": "grand",
    },

    "pre": [
        (r"galaxy(?=[a-z0-9])", "galaxy "),
        (r"(?<![\u0600-\u06FF])اف\s*اي(?![\u0600-\u06FF])", " fe "),
        (r"a⁰", " "),
        (r"[⁰⁵⁷]", lambda m: {"⁰": "0", "⁵": "5", "⁷": "7"}[m.group()]),
        (r"(?<![\u0600-\u06FF])اي\s*(?=\d)", " a "),
        (r"(?<!\d)5\s*(?:g|جي)\b", " "),
    ],

    "rules": [
        (r"tri\s*fold|ترايفولد", "z trifold"),
        (r"\bz\s*fold\s*(\d+)\b", "z fold{1}"),
        (r"\bz\s*flip\s*(\d+)\b", "z flip{1}"),
        (r"\bfold\s*(\d+)\b", "z fold{1}"),
        (r"\bflip\s*(\d+)\b", "z flip{1}"),
        (r"\bx\s*cover\s*(\d+)\s*(pro)?\b", "xcover{1} {2}"),
        (r"\b26\s*ultra\b", "s26 ultra"),
        (r"\ba\s*03\s*core\b", "a03 core"),
        (r"\ba\s*04e\b", "a04e"),
        (r"\bgrand\s*prime\s*pro\b", "grand prime pro"),
        (r"\bgrand\s*prime\b", "grand prime"),
        (r"\bmega\b", "mega"),
        (r"\bnote\s*(\d+)\s*(ultra|plus)?\b", "note{1} {2}"),
        (r"\bs\s*(\d+)\s*(ultra|plus|fe)?\b", "s{1} {2}"),
        (r"\ba\s*(\d{1,3})\s*s\b", "a{1}s"),
        (r"\ba\s*(\d{1,3})\s*(ultra|plus)?\b", "a{1} {2}"),
        (r"\bf\s*(\d{1,3})\b", "f{1}"),
        (r"\bm\s*(\d{1,3})\s*s\b", "m{1}s"),
        (r"\bm\s*(\d{1,3})\s*(ultra|plus)?\b", "m{1} {2}"),
        (r"\bj\s*(\d{1,2})\sprime\s(\d)\b", "j{1} prime {2}"),
        (r"\bj\s*(\d{1,2})\s*(prime|plus|pro)\b", "j{1} {2}"),   # لاحقة في أي مكان (J7 ... J7 prime)
        (r"\bj\s*(\d{1,2})\b", "j{1}"),
        (r"\b(\d{1,2})\s*fe\b", "s{1} fe"),
        (r"\b(\d{1,3})\s*a\b", "a{1}"),
        (r"\bfold\b", "z fold"),
        (r"\bgrand\b", "grand"),
    ],
}


BRAND_CONFIG["xiaomi"] = {
    "letters": {
        "اكس": "x",
        "اف": "f",
        "ام": "m",
        "سي": "c",
        "كيه": "k",
        "ايه": "a",
        "تي": "t",
        "مي": "mi",
    },

    "aliases": {
        "ميكس": "mix",
        "تربو": "turbo",
        "بلاك شارك": "black shark",
    },

    "pre": [
        (r"xiaomi\s+مي\s+تن\s+تي", "xiaomi mi 10t"),
        (r"xiaomi\s+بوك\s+اكس\s+ثري\s+pro", "poco x3 pro"),
        (r"xiaomi\s+بوك\s+اكس\s+ثري", "poco x3"),
        (r"\bxiaomi\s+18\s*fold\b", "xiaomi 18 fold"),
        (r"\bxiaomi\s+fold\s+xiaomi\s+18\s*fold\b",
         "xiaomi fold xiaomi 18 fold"),
    ],

    "rules": [
        # Black Shark
        (
            r"\bblack\s*shark\s*(\d{1,2})(?:\s*(pro))?\b",
            "black shark {1} {2}"
        ),

        (
            r"\bredmi\s*note\s*(\d{1,2})"
            r"\s*(s|t|a)?"
            r"\s*(pro\s*plus|pro\s*max|pro|plus)?"
            r"\s*(5g)?\b",
            "redmi note {1}{2} {3} {4}"
        ),

        # Redmi K
        (
            r"\bredmi\s*k\s*(\d{2,3})"
            r"\s*(pro\s*max|pro|ultra|plus)?\b",
            "redmi k{1} {2}"
        ),

        # Redmi Turbo
        (
            r"\bredmi\s*turbo\s*(\d{1,2})\s*(pro|max)?\b",
            "redmi turbo {1} {2}"
        ),

        # Redmi A / C
        (
            r"\bredmi\s*([ac])\s*(\d{1,2})(y)?\b",
            "redmi {1}{2}{3}"
        ),

        # Redmi 12C / 13C / 12 5G / 13 5G وما شابه
        (
            r"\bredmi\s*(\d{1,2})\s*(c|a|t|s|x)"
            r"\s*(prime|pro|plus)?\b",
            "redmi {1}{2} {3}"
        ),

        (
            r"\bredmi\s*(\d{1,2})"
            r"\s*(prime|pro|plus)?\b",
            "redmi {1} {2}"
        ),

        # POCO X / F / M / C
        (
            r"\bpoco\s*([xfmc])\s*(\d{1,2})"
            r"\s*(pro\s*max|nfc|pro|max|gt|ultra|plus)?\b",
            "poco {1}{2} {3}"
        ),

        (
            r"\bpoco\b.*?\b([xfmc])\s*(\d{1,2})"
            r"\s*(pro\s*max|nfc|pro|max|gt|ultra|plus)?\b",
            "poco {1}{2} {3}"
        ),

        # Xiaomi Mix Fold / Flip
        (
            r"\bmix\s*(fold|flip)\s*(\d{1,2})?\b",
            "mix {1} {2}"
        ),

        # Xiaomi 18 Fold أو Xiaomi 18fold
        (
            r"\bxiaomi\s*(\d{1,2})\s*fold\b",
            "{1} fold"
        ),

        # Mi A
        (
            r"\bmi\s*a\s*(\d{1,2})\b",
            "mi a{1}"
        ),

        # Mi Note
        (
            r"\bmi\s*note\s*(\d{1,2})\s*(pro|lite)?\b",
            "mi note {1} {2}"
        ),

        # Mi / Mi T
        (
            r"\bmi\s*(\d{1,2}t?)\s*(pro|lite|ultra)?\b",
            "mi {1} {2}"
        ),

        # Xiaomi 12C -> Redmi 12C
        (
            r"\bxiaomi\s*(\d{1,2})\s*c\b",
            "redmi {1}c"
        ),

        # Xiaomi A3 -> Redmi A3
        (
            r"\bxiaomi\s*a\s*(\d{1,2})\b",
            "redmi a{1}"
        ),

        (
            r"\bxiaomi\s*(\d{1,2}t?)"
            r"\s*(pro|lite|ultra|plus)?\b",
            "{1} {2}"
        ),

        # Ultra 15 -> 15 ultra
        (
            r"\bultra\s*(\d{2})\b",
            "{1} ultra"
        ),

        (
            r"\bc\s*(\d{2})\b",
            "redmi c{1}"
        ),

        (
            r"\bnote\s*(\d{1,2})"
            r"\s*(s|t)?"
            r"\s*(pro\s*plus|pro\s*max|pro|plus)?"
            r"\s*(5g)?\b",
            "redmi note {1}{2} {3} {4}"
        ),
    ],
}


BRAND_CONFIG["oppo"] = {
    "letters": {
        "ايه": "a",
        "اي": "a",
        "اية": "a",
        "اف": "f",
        "ار": "r",
        "تي": "t",
        "اكس": "x",
    },

    "aliases": {
        "opoo": "oppo",
        "oppooo": "oppo",
        "فايف جي": "5g",
        "فايند": "find",
    },

    "pre": [
        (r"\bfind\s+ان\s*(?=\d)", "find n "),

        # Turbo: تربو -> turbo
        (
            r"(?<![\u0600-\u06FF])تربو(?![\u0600-\u06FF])",
            "turbo"
        ),

        (r"\ba\s*6\s+اي\b", "a6i"),

        # A6 Pro
        (r"\ba\s*6\s+pro\b", "a6pro"),
    ],

    "rules": [
        (r"\ba\s*6a\b", "a6i"),

        # Find N series
        (
            r"\bfind\s*n\s*(\d{1,2})\b",
            "find n{1}"
        ),

        # Find X series
        (
            r"\bfind\s*x\s*(\d{1,2})\s*(pro|plus|ultra)?\b",
            "find x{1} {2}"
        ),

        # K series: K13 Turbo Pro 5G
        (
            r"\bk\s*(\d{1,2})\s*turbo\s*(pro)?\s*(5g)?\b",
            "k{1} turbo {2} {3}"
        ),

        # Reno series: Reno 7, Reno 8T, Reno 15F 5G
        (
            r"\breno\s*(\d{1,2})\s*(t|f|z)?\s*"
            r"(pro\s*plus|pro|plus)?\s*(5g)?\b",
            "reno {1}{2} {3} {4}"
        ),

        # A series: A60, A5i, A6 Pro, A6X, A1K
        (
            r"\ba\s*(\d{1,3})\s*"
            r"(pro\s*plus|pro|plus|x|k|s|i)?\s*(5g)?\b",
            "a{1}{2} {3}"
        ),

        # F series: F5, F1s
        (
            r"\bf\s*(\d{1,2})\s*(s|x|pro)?\b",
            "f{1}{2}"
        ),

        # R series: R15 Pro
        (
            r"\br\s*(\d{1,2})\s*(pro|plus)?\b",
            "r{1} {2}"
        ),
    ]
}


BRAND_CONFIG["honor"] = {
    "letters": {
        "اكس": "x",
        "سي": "c",
        "سى": "c",
        "سيه": "c",
        "سيي": "c",
        "بي": "b",
        "بى": "b",
        "ايه": "a",
        "اي": "i",
    },

    "aliases": {
        "honour": "honor",
        "هونور": "honor",
        "اونر": "honor",
    },

    "pre": [
        # Arabic X: اكس 8 -> x 8
        (r"(?<![\u0600-\u06FF])اكس(?![\u0600-\u06FF])", "x"),

        # Arabic Magic V: ماجيك في 3 -> magic v 3
        (r"ماجيك\s+في(?=\s*\d)", "magic v"),

        # Correct likely typo only in the specific model context
        (r"\bhonor\s+wen\s+rt\b", "honor win rt"),
        (r"\bhonor\s+wen(?=\s+5g\b)", "honor win"),
    ],

    "rules": [
        # Honor X9c Smart
        (r"\bx\s*(\d{1,2})\s*c\s*smart\b", "x{1}c smart"),

        # Honor X5B PLUS
        (r"\bx\s*(\d{1,2})\s*(c|b|a|i|d)\s*(plus|pro)\b", "x{1}{2} {3}")

        # Honor X series: X6, X6b, X7a, X8c, X9c
        (r"\bx\s*(\d{1,2})\s*(c|b|a|i|d|pro|plus)?\b", "x{1}{2}"),

        # Arabic reversed format: 6 X -> X6
        (r"\b(\d{1,2})\s*x\s*(c|b|a)?\b", "x{1}{2}"),

        # Magic V series with a version number
        (r"\bmagic\s+v\s*(\d{1,2})\s*(pro|plus)?\b", "magic v{1} {2}"),

        # Magic V without a version number
        (r"\bmagic\s+v\b", "magic v"),

        # Magic numeric series: Magic 5 Pro, Magic 8 Pro
        (r"\bmagic\s*(\d{1,2})\s*(pro\s*plus|pro|plus|lite)?\b", "magic {1} {2}"),

        # Honor numeric series: Honor 200 Pro, Honor 600
        (r"\bhonor\s+(\d{2,3})\s*(pro\s*plus|pro|plus|lite)?\b", "{1} {2}"),

        # Honor Win RT / Win
        (r"\bwin\s+rt\b", "win rt"),
        (r"\bwin\b", "win"),

        # Honor Robot Phone / Robot
        (r"\brobot(?:\s+phone)?\b", "robot"),

        # Honor Play
        (r"\bplay\b", "play"),

        # Honor GT
        (r"\bgt\b", "gt"),

        # Honor 8 Pro / 8 Plus / 8 Lite
        (r"\bhonor\s+(\d{1,2})\s+(pro|plus|lite)\b", "{1} {2}"),

        # Honor 8X / 8C
        (r"\bhonor\s+(\d{1,2})\s*(x|c)\b", "{1}{2}"),
    ],
}


BRAND_CONFIG["realme"] = {
    "letters": {
        "سي": "c",
        "سى": "c",
        "بي": "p",
        "بى": "p",
        "س": "c",
    },

    "aliases": {
        "ريلمى": "realme",
        "نارزو": "narzo",
        "نوت": "note",
    },

    "pre": [
        # Arabic model names: specific phrases must come first
        (r"جي\s*تي\s*نيو", "gt neo"),
        (r"جي\s*تي", "gt"),
        (r"نوت(?=\s*\d)", "note"),
         (r"اكس(?=\s|$)", "x"),  
        (r"في(?=\s*\d)", "v"),

        # Fix common spelling variations
        (r"\bnot(?=\s*\d)", "note"),
        (r"\bgt(?=\d)", "gt "),
        (r"\bc(?=\d)", "c "),
        (r"\bp(?=\d)", "p "),
        (r"\ba(?=\d)", "a "),
        (r"\bproه\b", "pro"),
        (r"بروه\b", "pro"),
    ],

    "rules": [
        # GT Neo series — place before general GT rules
        (r"\bgt\s*neo\s*(\d{1,2})\s*(t)?\b", "gt neo {1}{2}"),

        # GT Master Edition
        (r"\bgt\s*master\s*edition\b", "gt master edition"),

        # GT Pro series
        (r"\bgt\s*(\d{1,2})\s*pro\b", "gt {1} pro"),

        # GT T series: GT 6T -> gt 6t
        (r"\bgt\s*(\d{1,2})\s*t\b", "gt {1}t"),

        # Standard GT series
        (r"\bgt\s*(\d{1,2})\b", "gt {1}"),

        # Note series
        (r"\bnote\s*(\d{2,3})\s*(x)?\b", "note {1}{2}"),

        # C series with Pro or Plus suffix, before the general C rule
        (r"\bc\s*(\d{1,3})\s*(pro|plus)\b", "c{1} {2}"),

        # C series: C21Y, C100i, C3
        (r"\bc\s*(\d{1,3})\s*([a-z])?\b", "c{1}{2}"),

        # P series
        (r"\bp\s*(\d{1,2})\s*(ultra|pro\s*plus|pro|plus)?\b", "p{1} {2}"),

        # Narzo series
        (r"\bnarzo\s*(\d{1,3})\s*(pro|plus|x)?\b", "narzo {1} {2}"),

        # V series
        (r"\bv\s*(\d{1,2})\s*(t|i)?\b", "v{1}{2}"),

        # Numbered series with suffixes: Realme 9i, 14t, etc.
        (r"\brealme\s+(\d{1,2})\s*(pro\s*plus|pro|plus)\b", "{1} {2}"),
        (r"\brealme\s+(\d{1,2})\s*(i|t|x)\b", "{1}{2}"),
        (r"\brealme\s+(\d{1,2})\b", "{1}"),

        # A series
        (r"\ba\s*(\d{1,2})\s*(pro|plus)?\b", "a{1} {2}"),
    ],
}


BRAND_CONFIG["infinix"] = {
    "letters": {},

    "aliases": {
        "انفنيكس": "infinix",
        "انفنكس": "infinix",
        "انفينكس": "infinix",
        "إنفنيكس": "infinix",
        "سمارت": "smart",
        "سمار": "smart",
        "هوت": "hot",
        "نوت": "note",
        "زيرو": "zero",
        "ايدج": "edge",
        "برو": "pro",
        "بلاي": "play",
    },

    "pre": [
        # Arabic series names
        (r"جي\s*تي", "gt"),
        (r"اس(?=\s*\d)", "s"),
        (r"سمارت\s*زيرو", "smart zero"),

        # Smart 6 اي -> Smart 6i
        (r"\bsmart\s*(\d{1,2})\s*اي\b", r"smart \1i"),

        # Join brand and model if written together
        (r"\binfinix(?=[a-z])", "infinix "),

        # Separate series from numbers
        (r"\b(gt|smart|note|hot|zero|s)\s*(?=\d)", r"\1 "),

        # Separate suffixes from numbers
        (r"(?<=\d)(pro|plus|play|ultra|lite)\b", r" \1"),
    ],

    "rules": [
        # GT series
        (r"\bgt\s*(\d{1,2})\s*pro\b", "gt {1} pro"),
        (r"\bgt\s*(\d{1,2})\s*plus\b", "gt {1} plus"),
        (r"\bgt\s*(\d{1,2})\b", "gt {1}"),

        # Smart Zero
        (r"\bsmart\s+zero\b", "smart zero"),

        # Smart series
        (r"\bsmart\s*(\d{1,2})\s*i\b", "smart {1}i"),
        (r"\bsmart\s*(\d{1,2})\b", "smart {1}"),

        # Zero series: Zero 8i, Zero 30, etc.
        (r"\bzero\s*(\d{1,2})\s*(i|x|pro)?\b", "zero {1}{2}"),

        # Note Edge
        (r"\bnote\s*edge\b", "note edge"),

        # Note series: Note 50s, Note 60
        (r"\bnote\s*(\d{1,3})\s*(s|pro|plus|x|i)?\b", "note {1}{2}"),

        # Hot series with letter suffix: Hot 60i
        (r"\bhot\s*(\d{1,3})\s*(i|s|x)\b", "hot {1}{2}"),

        # Hot series with word suffix: Hot 11 Play, Hot 60 Pro
        (
            r"\bhot\s*(\d{1,3})\s*(play|pro\s*plus|pro|plus|ultra|lite)?\b",
            "hot {1} {2}"
        ),

        # S series: S4, S5
        (r"\bs\s*(\d{1,2})\s*(pro|plus|lite)?\b", "s{1} {2}"),
    ],
}


BRAND_CONFIG["vivo"] = {
    "letters": {},

    "aliases": {
        "فيفو": "vivo",
        "اكس": "x",
        "إكس": "x",
        "فولد": "fold",
        "اف اي": "fe",
        "إف إي": "fe",
        "واي": "y",
        "واى": "y",
        "اس": "s",
        "إس": "s",
        "برو": "pro",
        "لايت": "lite",
        "الترا": "ultra",
        "نيو": "neo",
    },

    "pre": [
        # Arabic V-series notation: في 70 -> v 70
        (r"في(?=\s*\d)", "v"),

        # Arabic iQOO spelling variants
        (r"اي\s*كيو\s*او(?:و)?", "iqoo"),

        # Arabic model suffixes
        (r"اف\s*اي\b", "fe"),
        (r"اي(?=\s|$)", "e"),

        # Correct the common V40 Lite typo when it follows a model number
        (r"(?<=\d)\s*ite\b", " lite"),

        # Smart spacing for concatenated brand and model
        (r"\bvivo(?=[a-z])", "vivo "),

        # X Fold 3 Pro and similar
        (r"\bx\s*fold\s*(?=\d)", "x fold "),

        # Separate series from model number
        (r"\b(x|y|v|s)\s*(?=\d)", r"\1 "),

        # Separate suffixes when written directly after digits
        (r"(?<=\d)(pro|plus|ultra|lite|fe)\b", r" \1"),
    ],

    "rules": [
        # iQOO Neo series
        (
            r"\biqoo\s*neo\s*(\d{1,3})\s*(pro\s*plus|pro|plus|ultra)?\b",
            "iqoo neo {1} {2}"
        ),

        # X Fold series: X Fold 3 Pro
        (
            r"\bx\s*fold\s*(\d{1,2})\s*(pro|plus|ultra)?\b",
            "x fold {1} {2}"
        ),

        # X series with FE suffix: X300 FE
        (
            r"\bx\s*(\d{2,3})\s*(fe|ultra|pro|plus|lite|e)?\b",
            "x{1} {2}"
        ),

        # V series with suffix: V23e, V27e, V29e
        (
            r"\bv\s*(\d{1,3})\s*(e|s|d)\s*(pro|plus|lite|ultra)?\b",
            "v{1}{2} {3}"
        ),

        # V series with Pro / Lite / Ultra
        (
            r"\bv\s*(\d{1,3})\s*(pro|plus|lite|ultra)\s*(5g)?\b",
            "v{1} {2} {3}"
        ),

        # V series without suffix
        (
            r"\bv\s*(\d{1,3})\b",
            "v{1}"
        ),

        # Titles like "Vivo 40 Lite" or "Vivo 50 Lite"
        (
            r"\bvivo\s+(\d{1,3})\s*lite\b",
            "v{1} lite"
        ),

        # S series with suffix
        (
            r"\bs\s*(\d{1,3})\s*(pro|plus|lite|ultra)?\b",
            "s{1} {2}"
        ),

        # Y series with suffixes: Y11D, Y31D, Y20s, Y17s
        (
            r"\by\s*(\d{1,3})\s*(s|d|e)\s*(pro|plus|lite|ultra)?\b",
            "y{1}{2} {3}"
        ),

        # Y series with Pro / Lite / Plus
        (
            r"\by\s*(\d{1,3})\s*(pro|plus|lite|ultra)\b",
            "y{1} {2}"
        ),

        # Standard Y series
        (
            r"\by\s*(\d{1,3})\b",
            "y{1}"
        ),
    ],
}

BRAND_CONFIG["huawei"] = {
    "letters": {},

    "aliases": {
        "هواوي": "huawei",
        "هواوى": "huawei",
        "هواويه": "huawei",

        "ميت": "mate",
        "نوفا": "nova",
        "بورا": "pura",

        "برايم": "prime",
        "برو": "pro",
        "لايت": "lite",
        "بلس": "plus",
        "الترا": "ultra",
        "التميت": "ultimate",

        "بي": "p",
        "بى": "p",
        "واي": "y",
        "واى": "y",
        "سي": "se",
    },

    "pre": [
        (r"(?<![\u0600-\u06FF])اكس(?![\u0600-\u06FF])", "x"),
        (r"ميت\s*(?=[a-z0-9])", "mate "),
        (r"نوفا\s*(?=\d)", "nova "),
        (r"بورا\s*(?=\d)", "pura "),

        (r"\bmat(?=\s*\d)", "mate "),
        (r"\bhuawei(?=[a-z])", "huawei "),

        (r"\b(y|p|nova|mate|pura)\s*(?=\d)", r"\1 "),
        (r"\bmate\s*x\s*t\s*(?=\d)", "mate xt "),
        (r"\bmate\s*x\s*(?=\d)", "mate x "),

        (r"\by\s*(\d{1,2})([a-z])\b", r"y \1\2"),

        (r"\by\s*(9)\s*(2019)\b", r"y \1 \2"),

        (r"(?<=\d)(pro|max|plus|ultra|lite|prime|ultimate)\b", r" \1"),
    ],

    "rules": [
        # -------------------------
        # Huawei Pura series
        # -------------------------
        (r"\bpura\s*(\d{2})\s*s\s*pro\s*max\b",
         "pura {1}s pro max"),

        (r"\bpura\s*(\d{2})\s*pro\s*max\b",
         "pura {1} pro max"),

        (r"\bpura\s*(\d{2})\s*(ultra|pro|plus|lite|max)\b",
         "pura {1} {2}"),

        (r"\bpura\s*(\d{2})\b",
         "pura {1}"),

        # -------------------------
        # Huawei Mate XT series
        # -------------------------
        (r"\bmate\s*xt\s*(\d{1,2})\s*(ultimate|pro|plus)?\b",
         "mate xt{1} {2}"),

        # -------------------------
        # Huawei Mate X series
        # -------------------------
        (r"\bmate\s*x\s*(\d{1,2})\s*(ultimate|pro|plus)?\b",
         "mate x{1} {2}"),

        # -------------------------
        # Huawei Mate series
        # -------------------------
        (r"\bmate\s*(\d{1,2})\s*(pro|plus|lite|x)?\b",
         "mate {1} {2}"),

        # -------------------------
        # Huawei Nova Max without a number
        (r"\bnova\s+max\b", "nova max"),

        # Huawei Nova series
        # -------------------------
        (r"\bnova\s*(\d{1,2})\s*(se|i|pro|plus|lite|max)?\b",
         "nova {1}{2}"),

        # -------------------------
        # Huawei P series
        # -------------------------
        (r"\bp\s*(\d{1,2})\s*(pro|plus|lite|max)?\b",
         "p{1} {2}"),

        # -------------------------
        # Huawei Y series
        # -------------------------
        (r"\by\s*(7)\s*a\b",
         "y{1}a"),

        (r"\by\s*(6)\s*p\b",
         "y{1}p"),

        (r"\by\s*(\d{1,2})\s*(prime)\s*(plus)\b",
         "y{1} prime plus"),

        (r"\by\s*(\d{1,2})\s*(prime)\s*(2019)\b",
         "y{1} prime {3}"),

        (r"\by\s*(\d{1,2})\s*(2019|2020)\b",
         "y{1} {2}"),

        (r"\by\s*(\d{1,2})\s*(prime|pro|plus|lite|p|s)?\b",
         "y{1} {2}"),
    ],
}

BRAND_CONFIG["motorola"] = {
    "letters": {},

    "aliases": {
        # Brand
        "موتورولا": "motorola",
        "موتورله": "motorola",

        # Moto G
        "موتو": "moto",
        "جي": "g",
        "جى": "g",

        # Edge
        "ايدج": "edge",
        "إيدج": "edge",

        # Razr
        "رازر": "razr",
        "ريزر": "razr",

        # Stylus
        "ستايلس": "stylus",
        "ستايلوس": "stylus",

        # Other model words
        "فيوجن": "fusion",
        "الترا": "ultra",
        "زيروو": "zero",
    },

    "pre": [
        # Brand normalization
        (r"\bmotorola(?=[a-z0-9])", "motorola "),

        # Moto G series
        (r"\bmoto\s*g\s*(?=\d)", "moto g "),

        # Edge series
        (r"\bedge\s*(?=\d)", "edge "),

        # Razr series
        (r"\brazr\s*(?=\d)", "razr "),

        # Stylus series
        (r"\bstylus\s*(?=\d)", "stylus "),

        # G04, G24, etc.
        (r"\bg\s*(?=\d)", "g "),

        # Separate suffixes attached to digits
        (r"(?<=\d)(ultra|fusion|stylus)\b", r" \1"),
    ],

    "rules": [
        # -------------------------
        # Motorola Edge
        # -------------------------

        # Reversed title: 50 Edge Fusion
        (r"\b(\d{2})\s*edge\s*fusion\b",
         "edge {1} fusion"),

        # Edge 50 Fusion, Edge 60 Fusion
        (r"\bedge\s*(\d{2})\s*fusion\b",
         "edge {1} fusion"),

        # Edge models with suffix
        (r"\bedge\s*(\d{2})\s*(ultra|pro|neo|fusion|plus)\b",
         "edge {1} {2}"),

        # Edge models without suffix
        (r"\bedge\s*(\d{2})\b",
         "edge {1}"),

        # Edge 2023+
        (r"\bedge\s*(2023)\s*\+",
         "edge {1} plus"),

        (r"\bedge\s*(\d{4})\b",
         "edge {1}"),

        # -------------------------
        # Motorola Razr
        # -------------------------
        (r"\brazr\s*(\d{2})\s*(ultra|plus)?\b",
         "razr {1} {2}"),

        # -------------------------
        # Motorola Stylus
        # -------------------------
        (r"\bstylus\s*5g\b",
         "stylus 5g"),

        (r"\bstylus\s*(\d{1,2})\s*(5g)?\b",
         "stylus {1} {2}"),

        # -------------------------
        # Motorola Moto G
        # -------------------------

        # Moto G5 Plus, Moto G85, Moto G56, etc.
        (r"\bmoto\s*g\s*(\d{1,3})\s*(plus|power|play|pro)?\b",
         "moto g{1} {2}"),

        # G04, G24, G85, etc. without Moto
        (r"\bg\s*(\d{2,3})\s*(plus|power|play|pro)?\b",
         "g{1} {2}"),

        # -------------------------
        # Motorola Signature
        # -------------------------
        (r"\bsignature\b",
         "signature"),
    ],
}

BRAND_CONFIG["oneplus"] = {
    "letters": {},

    "aliases": {
        # Brand names in Arabic
        "وان بلس": "oneplus",
        "ون بلس": "oneplus",
        "وانبلس": "oneplus",
        "ونبلس": "oneplus",

        # Series names
        "ايس": "ace",
        "آيس": "ace",
        "نورد": "nord",
        "نورد سي": "nord ce",
        "ار": "r",
        "تي": "t",

        # Suffixes
        "برو": "pro",
        "بلس": "plus",
        "الترا": "ultra",
        "اوبن": "open",
        "ماكلارين": "mclaren",
    },

    "pre": [
        # Normalize brand spelling
        (r"\bone\s+plus\b", "oneplus"),
        (r"\boneplus(?=[a-z0-9])", "oneplus "),

        # Normalize series names
        (r"\bace\s*(?=\d)", "ace "),
        (r"\bnord\s+ce\s*(?=\d)", "nord ce "),
        (r"\bnord\s*(?=\d)", "nord "),

        # Separate suffixes attached to digits
        (r"(?<=\d)(pro|plus|ultra)\b", r" \1"),

        # Normalize numbered suffixes
        (r"\b(\d{1,2})\s*t\s*pro\s*mclaren\b",
         r"\1t pro mclaren"),

        (r"\b(\d{1,2})\s*t\s*pro\b",
         r"\1t pro"),

        (r"\b(\d{1,2})\s*r\b",
         r"\1r"),
    ],

    "rules": [
        # -------------------------
        # OnePlus Ace
        # -------------------------
        (r"\bace\s*(\d{1,2})\s*t\b",
         "ace {1}t"),

        (r"\bace\s*(\d{1,2})\s*(pro|plus|ultra)\b",
         "ace {1} {2}"),

        (r"\bace\s*(\d{1,2})\b",
         "ace {1}"),

        # -------------------------
        # OnePlus Nord CE
        # -------------------------
        (r"\bnord\s*ce\s*(\d{1,2})\s*(lite)?\b",
         "nord ce{1} {2}"),

        # -------------------------
        # OnePlus Nord
        # -------------------------
        (r"\bnord\s*(\d{1,2})\s*(pro|plus)?\b",
         "nord {1} {2}"),

        # -------------------------
        # OnePlus Open
        # -------------------------
        (r"\bopen(?:\s+fold)?\b",
         "open"),

        # -------------------------
        # OnePlus numbered models
        # -------------------------

        # 7T Pro McLaren Edition
        (r"\b(\d{1,2})\s*t\s*pro\s*mclaren\b",
         "{1}t pro mclaren"),

        # 13s, 13t, 12r
        (r"\b(\d{1,2})\s*(s|t|r)\b",
         "{1}{2}"),

        # Numbered Pro models
        (r"\b(\d{1,2})\s*pro\b",
         "{1} pro"),

        # Numbered Plus / Ultra models
        (r"\b(\d{1,2})\s*(plus|ultra)\b",
         "{1} {2}"),

        # Numbered models without suffix
        (r"\b(\d{1,2})\b",
         "{1}"),
    ],
}

BRAND_CONFIG["zte"] = {
    "letters": {},

    "aliases": {
        # Brand
        "زد تي اي": "zte",
        "زد تى اي": "zte",
        "زد تي إي": "zte",
        "زد تى إي": "zte",
        "زدتي اي": "zte",
        "زدتي": "zte",

        # Nubia
        "نوبيا": "nubia",
        "نوبيا زد": "nubia z",

        # RedMagic
        "ريد ماجيك": "red magic",
        "ريدماجيك": "red magic",

        # Neo
        "نيو": "neo",

        # Other
        "برو": "pro",
        "اير": "air",
        "إير": "air",
        "الترا": "ultra",
        "بلس": "plus",
    },

    "pre": [
        # Brand normalization
        (r"\bzte(?=[a-z0-9])", "zte "),

        # Normalize Nubia and RedMagic
        (r"\bred\s*magic\s*(?=\d)", "red magic "),
        (r"\bnubia\s*z\s*(?=\d)", "nubia z "),
        (r"\bnubia\s*a\s*(?=\d)", "nubia a "),
        (r"\bnubia\s*v\s*(?=\d)", "nubia v "),
        (r"\bnubia\s*neo\s*(?=\d)", "nubia neo "),

        # Blade series
        (r"\bblade\s*a\s*(?=\d)", "blade a "),

        # Normalize Neo series
        (r"\bneo\s*(?=\d)", "neo "),

        # Fix attached model names
        (r"\bnubia(?=[a-z]\d)", "nubia "),
    ],

    "rules": [
        # -------------------------
        # RedMagic
        # -------------------------
        (r"\bred\s*magic\s*(\d{1,2})\s*(pro|max|ultra|air)?\b",
         "red magic {1} {2}"),

        # -------------------------
        # Nubia Neo
        # -------------------------
        (r"\bnubia\s*neo\s*(\d{1,2})\s*(5g|pro|plus)?\b",
         "nubia neo {1} {2}"),

        # -------------------------
        # Nubia Z series
        # -------------------------
        (r"\bnubia\s*z\s*(\d{1,2})\s*(pro|ultra|plus)?\b",
         "nubia z{1} {2}"),

        # -------------------------
        # Nubia A series
        # -------------------------
        (r"\bnubia\s*a\s*(\d{1,3})\s*(5g)?\b",
         "nubia a{1} {2}"),

        # -------------------------
        # Nubia V series
        # -------------------------
        (r"\bnubia\s*v\s*(\d{1,3})\s*(5g)?\b",
         "nubia v{1} {2}"),

        # -------------------------
        # ZTE Blade
        # -------------------------
        (r"\bblade\s*a\s*(\d{1,3})\s*(5g)?\b",
         "blade a{1} {2}"),

        # -------------------------
        # ZTE Neo
        # -------------------------
        (r"\bneo\s*(\d{1,2})\b",
         "nubia neo {1}"),

        # -------------------------
        # Unknown / Other Model
        # -------------------------
        (r"\bother\s+model\b",
         "unknown"),
    ],
}

BRAND_CONFIG["tecno"] = {
    "letters": {},

    "aliases": {
        "تكنو": "tecno",

        "سبارك": "spark",
        "سبارك جو": "spark go",
        "سبارك سي ام": "spark cm",
        "سبارك سي إم": "spark cm",

        "كامون": "camon",
        "كامون سي ام": "camon cm",
        "كامون سي إم": "camon cm",

        "بوفا": "pova",
        "بوب": "pop",

        "برو": "pro",
        "بلس": "plus",
        "جو": "go",
    },

    "pre": [
        (r"\btecno(?=[a-z0-9])", "tecno "),

        (r"\bspark\s*go\s*(?=\d)", "spark go "),
        (r"\bspark\s*cm\b", "spark cm"),
        (r"\bspark\s*(?=\d)", "spark "),
        (r"\bcamon\s*cm\b", "camon cm"),
        (r"\bcamon\s*(?=\d)", "camon "),
        (r"\bpova\s*(?=\d)", "pova "),
        (r"\bpop\s*(?=\d)", "pop "),

        (r"(?<=\d)(pro|plus)\b", r" \1"),
    ],

    "rules": [
        # Tecno Spark Go 3
        (
            r"\bspark\s*go\s*(\d{1,2})\b",
            "spark go {1}"
        ),

        # Tecno Spark 20 Pro+
        (
            r"\bspark\s*(\d{1,3})\s*pro\s*plus\b",
            "spark {1} pro plus"
        ),

        # Tecno Spark 20 Pro
        (
            r"\bspark\s*(\d{1,3})\s*pro\b",
            "spark {1} pro"
        ),

        # Tecno Spark CM
        (
            r"\bspark\s*cm\b",
            "spark cm"
        ),

        # Tecno Spark 30C
        (
            r"\bspark\s*(\d{1,3})\s*c\b",
            "spark {1}c"
        ),

        # Tecno Spark 30 / Spark 40
        (
            r"\bspark\s*(\d{1,3})\b",
            "spark {1}"
        ),

        # Tecno Camon CM
        (
            r"\bcamon\s*cm\b",
            "camon cm"
        ),

        # Tecno Camon 40 Pro 5G
        (
            r"\bcamon\s*(\d{1,3})\s*pro\s*5g\b",
            "camon {1} pro 5g"
        ),

        # Tecno Camon 40 Pro
        (
            r"\bcamon\s*(\d{1,3})\s*pro\b",
            "camon {1} pro"
        ),

        # Tecno Camon 40
        (
            r"\bcamon\s*(\d{1,3})\b",
            "camon {1}"
        ),

        # Tecno Pova 6 Pro / Pova 7
        (
            r"\bpova\s*(\d{1,3})\s*(pro|plus|ultra)?\b",
            "pova {1} {2}"
        ),

        # Tecno Pop 7
        (
            r"\bpop\s*(\d{1,3})\b",
            "pop {1}"
        ),
    ],
}


BRAND_CONFIG["itel"] = {
    "letters": {},
    "aliases": {
        "ايتل": "itel",
        "ايتيل": "itel",

        "اس": "s",
        "إس": "s",

        "ايه": "a",
        "إيه": "a",

        "ار": "r",
        "آر": "r",

        "اس 4": "s4",
        "اس 24": "s24",
        "اس 25": "s25",

        "الترا": "ultra",
        "سي": "c",
        "سى": "c",
    },

    "pre": [
        (r"\bitel(?=[a-z0-9])", "itel "),
        (r"\b([as])\s*(\d{1,3})\s*c\b", r"\1 \2c"),
        (r"\ba\s*(?=\d)", "a "),
        (r"\bs\s*(?=\d)", "s "),
        (r"\brs\s*(?=\d)", "rs "),
        (r"\br\s+s\s*(?=\d)", "rs "),
        (r"\b(\d{1,3})\s*c\b", r"\1c"),
    ],

    "rules": [
        # itel S25 Ultra
        (
            r"\bs\s*(\d{1,3})\s*ultra\b",
            "s{1} ultra"
        ),

        # itel S24 / S25
        (
            r"\bs\s*(\d{1,3})\b",
            "s{1}"
        ),

        # itel A50C
        (
            r"\ba\s*(\d{1,3})\s*c\b",
            "a{1}c"
        ),

        # itel A90 / A80 / A100C
        (
            r"\ba\s*(\d{1,3})\s*c\b",
            "a{1}c"
        ),
        (
            r"\ba\s*(\d{1,3})\b",
            "a{1}"
        ),

        # itel RS4
        (
            r"\brs\s*(\d{1,3})\b",
            "rs {1}"
        ),
    ],
}


BRAND_CONFIG["google"] = {
    "letters": {},
    "aliases": {
        "جوجل": "google",
        "بكسل": "pixel",
        "برو": "pro",
        "فولد": "fold",
        "ايه": "a",
        "إيه": "a",
    },

    "pre": [
        (r"\bgoogle(?=[a-z0-9])", "google "),
        (r"\bpixel\s*(?=\d)", "pixel "),
        (r"\b(\d{1,2})\s*pro\s*fold\b", r"\1 pro fold"),
        (r"\b(\d{1,2})\s*pro\b", r"\1 pro"),
        (r"\b(\d{1,2})\s*5g\b", r"\1 5g"),
    ],

    "rules": [
        # Pixel 11 Pro Fold
        (
            r"\bpixel\s*(\d{1,2})\s*pro\s*fold\b",
            "pixel {1} pro fold"
        ),

        # Pixel 6 Pro / Pixel 9 Pro
        (
            r"\bpixel\s*(\d{1,2})\s*pro\b",
            "pixel {1} pro"
        ),

        # Pixel 8a / Pixel 9a
        (
            r"\bpixel\s*(\d{1,2})\s*a\b",
            "pixel {1}a"
        ),

        # Pixel 10 5G
        (
            r"\bpixel\s*(\d{1,2})\s*5g\b",
            "pixel {1} 5g"
        ),

        # Pixel 6 / Pixel 7 / Pixel 10 / Pixel 11
        (
            r"\bpixel\s*(\d{1,2})\b",
            "pixel {1}"
        ),
    ],
}


BRAND_CONFIG["sony"] = {
    "letters": {},
    "aliases": {
        "سوني": "sony",
        "اكسبريا": "xperia",
        "إكسبريا": "xperia",
        "اريكسون": "ericsson",
        "إريكسون": "ericsson",
        "مارك": "mark",
        "برو": "pro",
        "الترا": "ultra",
        "زد": "z",
    },

    "pre": [
        (r"\bsony(?=[a-z0-9])", "sony "),
        (r"\bxperia(?=[a-z0-9])", "xperia "),
        (r"\b(\d)\s*mark\s*(\d)\b", r"\1 mark \2"),
        (r"\b(\d{1,2})\s*(iv|v|vi|iii|ii)\b", r"\1 \2"),
        (r"\bpro\s*[- ]?\s*i\b", "pro i"),
        (r"\bz\s*ultra\b", "z ultra"),
    ],

    "rules": [
        # Sony Xperia 1 Pro-I
        (
            r"\bxperia\s+pro\s+i\b",
            "xperia pro-i"
        ),

        # Sony Xperia 1 Mark 2 / Mark 7
        (
            r"\bxperia\s+(\d)\s*mark\s*(\d)\b",
            "xperia {1} mark {2}"
        ),

        # Sony Xperia 1 V / 5 IV
        (
            r"\bxperia\s+(\d{1,2})\s*(iv|v|vi|iii|ii)\b",
            "xperia {1} {2}"
        ),

        # Sony Xperia Z Ultra
        (
            r"\bxperia\s+z\s+ultra\b",
            "xperia z ultra"
        ),

        # Sony Xperia 1 / 5
        (
            r"\bxperia\s+(\d{1,2})\b",
            "xperia {1}"
        ),

        # Sony Ericsson K610i
        (
            r"\b([a-z]{1,3}\d{2,4}i?)\b",
            "{1}"
        ),
    ],
}


BRAND_CONFIG["nokia"] = {
    "letters": {},
    "aliases": {
        "نوكيا": "nokia",
        "اكس": "x",
        "إكس": "x",
        "بلس": "plus",
        "برو": "pro",
        "الترا": "ultra",
    },

    "pre": [
        (r"\bnokia(?=[a-z0-9])", "nokia "),

        (r"\b([gc])\s*(?=\d)", r"\1 "),
        (r"\bx\s*(?=\d)", "x "),
        (r"\bn\s*(?=\d)", "n "),

        (r"\b(\d+)\s*\.\s*(\d+)\b", r"\1.\2"),

        (r"(?<=\d)(plus|pro|ultra)\b", r" \1"),
    ],

    "rules": [
        # Nokia G300 5G
        (
            r"\bg\s*(\d{1,3})\s*5g\b",
            "g{1} 5g"
        ),
        (
            r"\bg\s*(\d{1,3})\b",
            "g{1}"
        ),

        # Nokia C21 Plus / C-series
        (
            r"\bc\s*(\d{1,3})\s*plus\b",
            "c{1} plus"
        ),
        (
            r"\bc\s*(\d{1,3})\s*pro\b",
            "c{1} pro"
        ),
        (
            r"\bc\s*(\d{1,3})\b",
            "c{1}"
        ),

        # Nokia X350 / X2
        (
            r"\bx\s*(\d{1,4})\b",
            "x{1}"
        ),

        # Nokia N9
        (
            r"\bn\s*(\d{1,3})\b",
            "n{1}"
        ),

        # Nokia 7.1
        (
            r"\b(\d{1,2})\.(\d)\b",
            "{1}.{2}"
        ),
    ],
}


BRAND_CONFIG["lenovo"] = {
    "letters": {},
    "aliases": {
        "لينوفو": "lenovo",
        "كيه": "k",
        "نوت": "note",
        "نوتة": "note",
        "ليجن": "legion",
        "ليجيون": "legion",
        "بلس": "plus",
        "برو": "pro",
    },

    "pre": [
        (r"\blenovo(?=[a-z0-9])", "lenovo "),
        (r"\blegion\s*y\s*(?=\d)", "legion y "),
        (r"\bk\s*(?=\d)", "k "),
        (r"\ba\s*(?=\d)", "a "),
        (r"\b(note)\s*(?=\d)", "note "),
        (r"\b(\d{1,3})\s*note\b", r"\1 note"),
    ],

    "rules": [
        # Lenovo Legion Y70
        (
            r"\blegion\s*y\s*(\d{1,3})\b",
            "legion y{1}"
        ),

        # Lenovo K14 Plus
        (
            r"\bk\s*(\d{1,3})\s*plus\b",
            "k{1} plus"
        ),

        # Lenovo K12 Note / K8 Note
        (
            r"\bk\s*(\d{1,3})\s*note\b",
            "k{1} note"
        ),

        # Lenovo K15
        (
            r"\bk\s*(\d{1,3})\b",
            "k{1}"
        ),

        # Lenovo A8
        (
            r"\ba\s*(\d{1,3})\b",
            "a{1}"
        ),

        # Lenovo Note 6
        (
            r"\bnote\s*(\d{1,3})\b",
            "note {1}"
        ),
    ],
}


BRAND_CONFIG["lg"] = {
    "letters": {},
    "aliases": {
        "ال جي": "lg",
        "إل جي": "lg",
        "ال جى": "lg",
        "إل جى": "lg",

        "فيلفيت": "velvet",
        "وينج": "wing",
        "وينغ": "wing",
        "ستايلو": "stylo",
        "ثينك كيو": "thinq",
        "ثينكيو": "thinq",
    },

    "pre": [
        (r"\blg(?=[a-z0-9])", "lg "),

        (r"\b(g|v|k|q|w|x)\s*(?=\d)", r"\1 "),
        (r"\bstylo\s*(?=\d)", "stylo "),
        (r"\bvelvet(?=\d)", "velvet "),
        (r"\bwing(?=\d)", "wing "),

        (r"\bthin\s*q\b", "thinq"),
        (r"\bthinq\b", "thinq"),

        (r"\b(v\d{1,2})\s*thinq\b", r"\1 thinq"),
    ],

    "rules": [
        # LG Velvet
        (r"\bvelvet\s*(\d{1,2})?\b", "velvet {1}"),

        # LG Wing
        (r"\bwing\s*(\d{1,2})?\b", "wing {1}"),

        # LG Stylo 6 / Stylo 7
        (r"\bstylo\s*(\d{1,2})\b", "stylo {1}"),

        # LG V60 ThinQ / V50 ThinQ
        (r"\bv\s*(\d{1,2})\s*thinq\b", "v{1} thinq"),

        # LG G-series
        (r"\bg\s*(\d{1,2})\b", "g{1}"),

        # LG V-series
        (r"\bv\s*(\d{1,2})\b", "v{1}"),

        # LG K-series
        (r"\bk\s*(\d{1,3})\b", "k{1}"),

        # LG Q-series
        (r"\bq\s*(\d{1,3})\b", "q{1}"),

        # LG W-series
        (r"\bw\s*(\d{1,3})\b", "w{1}"),

        # LG X-series
        (r"\bx\s*(\d{1,3})\b", "x{1}"),
    ],
}



def predict_model_key(title, brand, with_rule=False):
    """Predict a canonical model key and, optionally, the rule that matched."""
    brand = str(brand).strip().lower()

    # Handle missing brand using specific title patterns
    if not brand or brand == "nan":
        title_text = str(title).lower().strip()

        # Xiaomi 17 Ultra
        if re.search(r"\bmi\s*17\s*ultra\b", title_text):
            return _prediction_result(
                "xiaomi 17 ultra",
                "xiaomi:inferred_mi_17_ultra",
                with_rule,
            )

        # Xiaomi Redmi Turbo 4 Pro
        if re.search(r"\bturbo\s*4\s*pro\b", title_text):
            return _prediction_result(
                "xiaomi redmi turbo 4 pro",
                "xiaomi:inferred_redmi_turbo_4_pro",
                with_rule,
            )

        # Huawei Mate 10 Lite written in Arabic
        if re.search(r"ميت\s*تن\s*لايت", title_text):
            return _prediction_result(
                "huawei mate 10 lite",
                "huawei:arabic_mate_10_lite",
                with_rule,
            )

        # Huawei Mate 30 Pro 5G
        if re.search(r"\bmate\s*30\s*pro\s*5g\b", title_text):
            return _prediction_result(
                "huawei mate 30 pro 5g",
                "huawei:mate_30_pro_5g",
                with_rule,
            )

        # Exact title: 17 Pro Max
        if re.fullmatch(r"17\s*pro\s*max", title_text):
            return _prediction_result(
                "apple iphone 17 pro max",
                "apple:inferred_17_pro_max",
                with_rule,
            )

        return _prediction_result("unknown", "unknown_brand", with_rule)

    if brand == "apple":
        model, match_rule = extract_iphone_model(title, with_rule=True)
        model_key = "unknown" if model == "unknown" else f"apple {model}"
        return _prediction_result(model_key, match_rule, with_rule)

    return extract_brand_model(title, brand, with_rule=with_rule)

