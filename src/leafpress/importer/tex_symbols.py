"""Text-level LaTeX conversions for the TeX importer.

Pure functions and lookup tables for things that turn LaTeX text into plain
Unicode: accent commands (``\\"o`` → ö), symbol macros (``\\ss`` → ß,
``\\&`` → &), typographic ligatures (``---`` → —), and siunitx quantities
(``\\SI{3e8}{\\metre\\per\\second}`` → 3 × 10⁸ m/s).
"""

from __future__ import annotations

import re
import unicodedata

# Accent macro -> Unicode combining character
ACCENT_MARKS: dict[str, str] = {
    "`": "\u0300",  # grave
    "'": "\u0301",  # acute
    "^": "\u0302",  # circumflex
    "~": "\u0303",  # tilde
    "=": "\u0304",  # macron
    "u": "\u0306",  # breve
    ".": "\u0307",  # dot above
    '"': "\u0308",  # diaeresis / umlaut
    "r": "\u030a",  # ring
    "H": "\u030b",  # double acute
    "v": "\u030c",  # caron
    "d": "\u0323",  # dot below
    "c": "\u0327",  # cedilla
    "k": "\u0328",  # ogonek
    "b": "\u0331",  # macron below
}

# Macros that stand for a single character or short text. Markdown-significant
# characters are returned escaped so they stay literal.
SYMBOL_MACROS: dict[str, str] = {
    "&": "&",
    "%": "%",
    "$": "\\$",
    "#": "\\#",
    "_": "\\_",
    "{": "{",
    "}": "}",
    " ": " ",
    ",": "\u2009",  # thin space
    ";": " ",
    ":": " ",
    "!": "",
    "/": "",
    "@": "",
    "-": "",  # discretionary hyphen
    "i": "ı",
    "j": "ȷ",
    "o": "ø",
    "O": "Ø",
    "ss": "ß",
    "SS": "SS",
    "ae": "æ",
    "AE": "Æ",
    "oe": "œ",
    "OE": "Œ",
    "aa": "å",
    "AA": "Å",
    "l": "ł",
    "L": "Ł",
    "dh": "ð",
    "DH": "Ð",
    "th": "þ",
    "TH": "Þ",
    "ldots": "…",
    "dots": "…",
    "textellipsis": "…",
    "LaTeX": "LaTeX",
    "LaTeXe": "LaTeX2e",
    "TeX": "TeX",
    "BibTeX": "BibTeX",
    "copyright": "©",
    "textcopyright": "©",
    "textregistered": "®",
    "texttrademark": "™",
    "textdegree": "°",
    "degree": "°",
    "S": "§",
    "P": "¶",
    "dag": "†",
    "ddag": "‡",
    "pounds": "£",
    "textsterling": "£",
    "euro": "€",
    "texteuro": "€",
    "textbackslash": "\\\\",
    "textasciitilde": "~",
    "textasciicircum": "^",
    "textbar": "|",
    "textless": "<",
    "textgreater": ">",
    "textbullet": "•",
    "textendash": "–",
    "textemdash": "—",
    "textquoteleft": "‘",
    "textquoteright": "’",
    "textquotedblleft": "“",
    "textquotedblright": "”",
    "guillemotleft": "«",
    "guillemotright": "»",
    "quad": " ",
    "qquad": "  ",
    "today": "",
}

_LIGATURES = (
    ("---", "—"),
    ("--", "–"),
    ("``", "“"),
    ("''", "”"),
    ("~", " "),  # non-breaking space; a plain space reads better in Markdown
)


def apply_ligatures(text: str) -> str:
    """Apply LaTeX's text ligatures (``---``, ``--``, quotes, ``~``)."""
    for src, dst in _LIGATURES:
        text = text.replace(src, dst)
    return text


def apply_accent(macro: str, base: str) -> str:
    """Put the accent for ``macro`` on the first character of ``base``.

    Example:
        >>> apply_accent('"', "o")
        'ö'
    """
    if not base:
        return ACCENT_MARKS.get(macro, "")
    first, rest = base[0], base[1:]
    # \"{\i} uses a dotless i so the accent replaces the dot
    first = {"ı": "i", "ȷ": "j"}.get(first, first)
    return unicodedata.normalize("NFC", first + ACCENT_MARKS[macro]) + rest


# -- siunitx --------------------------------------------------------------

_SI_PREFIXES: dict[str, str] = {
    "yocto": "y", "zepto": "z", "atto": "a", "femto": "f", "pico": "p",
    "nano": "n", "micro": "µ", "milli": "m", "centi": "c", "deci": "d",
    "deca": "da", "deka": "da", "hecto": "h", "kilo": "k", "mega": "M",
    "giga": "G", "tera": "T", "peta": "P", "exa": "E", "zetta": "Z",
    "yotta": "Y", "kibi": "Ki", "mebi": "Mi", "gibi": "Gi", "tebi": "Ti",
}  # fmt: skip

_SI_UNITS: dict[str, str] = {
    "metre": "m", "meter": "m", "second": "s", "gram": "g", "kilogram": "kg",
    "ampere": "A", "kelvin": "K", "mole": "mol", "candela": "cd",
    "hertz": "Hz", "newton": "N", "pascal": "Pa", "joule": "J", "watt": "W",
    "volt": "V", "ohm": "Ω", "coulomb": "C", "farad": "F", "henry": "H",
    "tesla": "T", "weber": "Wb", "siemens": "S", "celsius": "°C",
    "degreeCelsius": "°C", "degree": "°", "arcminute": "′", "arcsecond": "″",
    "percent": "%", "litre": "L", "liter": "L", "byte": "B", "bit": "bit",
    "minute": "min", "hour": "h", "day": "d", "electronvolt": "eV",
    "decibel": "dB", "neper": "Np", "bel": "B", "radian": "rad",
    "steradian": "sr", "lumen": "lm", "lux": "lx", "becquerel": "Bq",
    "gray": "Gy", "sievert": "Sv", "katal": "kat", "tonne": "t",
    "hectare": "ha", "astronomicalunit": "au", "dalton": "Da",
    "angstrom": "Å", "bar": "bar", "barn": "b", "knot": "kn",
    "mmHg": "mmHg", "atomicmassunit": "u", "clight": "c",
}  # fmt: skip

_SUPERSCRIPTS = str.maketrans("0123456789-+", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺")

# Units written without a separating space after the number
_UNSPACED_UNITS = {"°", "′", "″"}


def _superscript(text: str) -> str:
    return text.translate(_SUPERSCRIPTS) if re.fullmatch(r"[-+]?\d+", text) else f"^{text}"


def format_si_number(raw: str) -> str:
    """Format a siunitx number: ``3.0e8`` → ``3.0 × 10⁸``, ``1.5+-0.2`` → ``1.5 ± 0.2``."""
    s = raw.strip().replace(" ", "")
    s = s.replace("+-", " ± ").replace("\\pm", " ± ")
    s = re.sub(
        r"(?<=[\d.])[eEdD]([-+]?\d+)",
        lambda m: " × 10" + m.group(1).lstrip("+").translate(_SUPERSCRIPTS),
        s,
    )
    return s


def format_si_unit(raw: str) -> str:
    """Format a siunitx unit, from macros (``\\kilo\\metre\\per\\second``) or text (``m/s``).

    Example:
        >>> format_si_unit(r"\\kilo\\metre\\per\\second\\squared")
        'km/s²'
    """
    if "\\" not in raw:
        # Literal form: m.s^{-1}, kg m^2
        text = raw.strip().replace("~", " ").replace(".", "·")
        return re.sub(r"\^\{?([-+]?\w+)\}?", lambda m: _superscript(m.group(1)), text)

    # Like siunitx's default per-mode=power: \per gives a negative exponent
    units: list[list] = []  # [symbol, power]
    per_pending = False
    prefix = ""
    pre_power = 1  # from \square / \cubic before the unit
    tokens = re.findall(r"\\([A-Za-z]+)(?:\{([^}]*)\})?|([^\\\s]+)", raw)
    for macro, arg, literal in tokens:
        if literal:
            units.append([literal, -1 if per_pending else 1])
            per_pending = False
        elif macro == "per":
            per_pending = True
        elif macro in _SI_PREFIXES:
            prefix = _SI_PREFIXES[macro]
        elif macro in ("square", "cubic"):
            pre_power = 2 if macro == "square" else 3
        elif macro in ("squared", "cubed") and units:
            units[-1][1] *= 2 if macro == "squared" else 3
        elif macro in ("tothe", "raiseto") and units and re.fullmatch(r"-?\d+", arg or ""):
            units[-1][1] *= int(arg)
        elif macro in _SI_UNITS:
            power = pre_power * (-1 if per_pending else 1)
            units.append([prefix + _SI_UNITS[macro], power])
            prefix, pre_power, per_pending = "", 1, False
    return "·".join(
        sym if power == 1 else sym + str(power).translate(_SUPERSCRIPTS) for sym, power in units
    )


def format_si_quantity(number: str, unit: str) -> str:
    """Combine a formatted number and unit (``25 °C``, ``90°``, ``50 %``)."""
    num = format_si_number(number)
    u = format_si_unit(unit)
    if not u:
        return num
    return f"{num}{u}" if u in _UNSPACED_UNITS else f"{num} {u}"


def format_si_range(first: str, second: str, unit: str = "") -> str:
    """Format ``\\SIrange``/``\\numrange`` as ``10–20 m``."""
    lo, hi = format_si_number(first), format_si_number(second)
    u = format_si_unit(unit) if unit else ""
    if not u:
        return f"{lo}–{hi}"
    return f"{lo}{u}–{hi}{u}" if u in _UNSPACED_UNITS else f"{lo}–{hi} {u}"
