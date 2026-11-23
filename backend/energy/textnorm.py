import re
import unicodedata


def normalize_name(s: str) -> str:
    """Lowercase, fold umlauts/ß so 'Tübingen', 'Tubingen' and 'Tuebingen' all match.

    Applied identically to stored names and to user queries, so the folding only has
    to be *consistent*, not linguistically perfect.
    """
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"(ae|oe|ue)", lambda m: m.group(1)[0], s)
    return re.sub(r"\s+", " ", s).strip()
