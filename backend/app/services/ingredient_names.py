"""Conservative shared normalization for content validation and exact matching."""

import re
import unicodedata

IDENTIFIER = re.compile(r"(e|ins)\s*-?\s*([0-9]{3,4}[a-z]?(?:\([ivx]+\))?)\Z")


def normalize_name(text: str) -> str:
    text = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    # Strip paired label emphasis and surrounding punctuation, not chemical
    # punctuation or the final ')' of an identifier such as E150(i).
    text = text.strip()
    while text and (unicodedata.category(text[0]).startswith("P") or text[0].isspace()):
        text = text[1:]
    while text and (
        text[-1].isspace()
        or (
            unicodedata.category(text[-1]).startswith("P")
            and not (text[-1] == ")" and text.count("(") >= text.count(")"))
        )
    ):
        text = text[:-1]
    match = IDENTIFIER.fullmatch(text)
    return "".join(match.groups()) if match else text
