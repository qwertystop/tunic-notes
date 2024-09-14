"""
For finding patterns in text from the game Tunic
"""

import glob
import itertools
from collections import defaultdict

import lark

GRAMMAR = r"""
start: section
section: "#" HEADER _NEWLINE (section+ | line+)
HEADER: LITERAL
line: (word | ("[" LITERAL "]"))+ _NEWLINE
word: glyph ("/" glyph)*
LITERAL: /[^]\n]+/
glyph: ( GLYPH_TOP "-"? GLYPH_BOT )
       | GLYPH_TOP -> top_glyph_only
       | GLYPH_BOT -> bot_glyph_only
GLYPH_TOP: /[1234QWER]+/
GLYPH_BOT: /[ASDFZXCV]+/
_NEWLINE: /\n/

%import common.WS_INLINE

%ignore WS_INLINE
%ignore /(?<!.)\n/
"""

# These map all known or suspected glyphs/words to all locations where they have been seen.
SCANNED_TREES: list[lark.Tree] = []
FOUND_WORDS: defaultdict[str, set[str]] = defaultdict(set)
FOUND_TOP_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
FOUND_BOT_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
WORD_TRANSLATIONS: dict[str, str] = {
    "134R-X/4WR-S": "<TAKE, GET>",
    "12": "<A>",
    "234R-XV/W-ASDFZV": "<ITEM>",
    "123QWR-DZX": "you",
    "4R-AFX/3-AS/WR-AS": "<FOUND>",
    "124R-SDFX/WR-AS": "guard",
    "123WR-DV": "<OF>",
    "12WR-ASX": "<THE>",
    "34Q-DFZ/WR-X": "well",
    "134QR-ASDFZX/WR-X/WR-AS": "<SHIELD/BLOCK>",
    "34-DFXV": "it",
    "123QWR-DZX/3WR-SXDF/3WR-SX": "uses",
    "124QR-SDFZX/WR-X/WR-ASDF/3AS": "golden",
}
SOUND_TRANSLATIONS: dict[str, str] = {
    "3WR-SX": "z",
    # maybe "f", blowing-sound, from library picture? but we also have it in "guardhouse"
    "WR-SFX": "how",
    # From "well well well" fox at well
    "34Q-DFZ": "weh",
    "WR-X": "ll",
    "QWR-SDFZ": "beh",
    "DFZ": "eh",
    "34-DFXV": "it",
    "DF": "ə",
    "12": "ah",
    "WR-AS": "d",
}
SUBGLYPH_SOUNDS: dict[frozenset[str], str] = {
    frozenset(g.split("")): s for g, s in SOUND_TRANSLATIONS.items()
}


def mirroring_unify():
    """
    Hypothesis under test:
    Glyph-parts above and below the separator represent the same thing transformed in some way.
    Test by:
    unifying into a single representation.
    Result:
    No single mapping seems to work;
    any one pattern unifies very few.
    """
    # none of these manual ones worked
    # so let's try all possiblities
    possible_tos = list(itertools.permutations("1234QWR"))
    # for to in
    # [
    # # simple vertical
    # # shift
    # '1234QWR',
    # # mirror on the
    # # center
    # '3412QWR',
    # # mirror diamond
    # # left-right
    # '2143QWR',
    # # double mirror
    # '4321QWR' ]
    top_glyphs = set(FOUND_TOP_GLYPHS.keys())
    bot_glyphs = set(FOUND_BOT_GLYPHS.keys())
    print(f"{len(top_glyphs)} top glyphs.")
    print(f"{len(bot_glyphs)} bot glyphs.")
    for to in possible_tos:
        table = str.maketrans("ASDFZXV", "".join(to))
        mapped = set(glyph.translate(table) for glyph in FOUND_BOT_GLYPHS)
        res = len(top_glyphs | mapped)
        if res < 100:
            print(f"{''.join(to)}: {res}.")


def glyph_ordering(char):
    """Sort the characters in a glyph in keyboard order."""
    return "1234QWERASDFZXCV".find(char)


def clean_glyph(glyph: str) -> str:
    """
    Deduplicate and sort characters in text representation of a glyph.
    Remove E and C, those are currently theorized to be actually part
    of the following glyph.
    """
    return "".join(
        sorted(set(glyph.replace("E", "").replace("C", "")), key=glyph_ordering)
    )


class CleanAndAnnotate(lark.visitors.Transformer_InPlace):
    """Clean glyphs"""

    def glyph(self, tree):  # pylint:disable=invalid-name
        """Standardize glyphs by deduplicating and sorting them."""
        resolved = [clean_glyph(token.value) for token in tree.children]
        return resolved

    def top_glyph_only(self, tree):
        return [clean_glyph(tree.children[0]), ""]

    def bot_glyph_only(self, tree):
        return ["", clean_glyph(tree.children[0])]

    def word(self, tree):
        """Print representation of whole word"""
        tree.this_word = "/".join(["-".join(glyph) for glyph in tree.children])
        return tree

    def section(self, tree):
        """Forward section name down to children"""
        assert tree.children[0].type == "HEADER"
        section_name = tree.children[0].value
        for i, child in enumerate(tree.children):
            if isinstance(child, lark.Tree):
                assert not hasattr(child, "in_section")
                child.in_section = section_name
                if child.data == "line":
                    assert not hasattr(child, "line_number")
                    child.line_number = i
        return tree


class TunicNotes(lark.Visitor):
    """Logs Tunic observations"""

    def word(self, tree):
        """Log all glyphs from this word in FOUND_GLYPHS"""
        for glyph in tree.children:
            FOUND_TOP_GLYPHS[glyph[0]].add(tree.this_word)
            FOUND_BOT_GLYPHS[glyph[1]].add(tree.this_word)

    def line(self, tree):
        """Log all words from this line in FOUND_WORDS"""
        for word in tree.children:
            # skip literals
            if isinstance(word, lark.Tree):
                FOUND_WORDS[word.this_word].add(
                    f"{tree.in_section}, line {tree.line_number}"
                )


def init_lark():
    """Set up the Lark parser"""
    lrk = lark.Lark(GRAMMAR, parser="lalr", transformer=CleanAndAnnotate())
    return lrk


def load_file(fname: str, lrk: lark.Lark) -> lark.Tree:
    """Open and parse a file"""
    with open(fname, "r", encoding="utf8") as file:
        content = file.read()
    tree = lrk.parse(content)

    SCANNED_TREES.append(tree)
    return tree


def points_of_interest(search_space: dict[str, set], n: int):
    """Find the entries that appear more than n times"""
    return {k: v for (k, v) in search_space.items() if len(v) >= n}


def render_text(word: str):
    """Convert dense representation to text art"""
    representation = [""] * 12
    for glyph in word.split("/"):
        for i, new in enumerate(_render_glyph(glyph)):
            representation[i] = representation[i] + new
    for line in representation:
        print(line)


def _render_glyph(glyph: str) -> list[str]:
    r"""
    Each glyph can be drawn as a 12x5 text cell:
    [ /|\ ]
    [/ | \]
    [\ | /]
    [|\|/ ]
    [| |  ]
    [-----]
    [|    ]
    [|/|\ ]
    [/ | \]
    [\ | /]
    [ \|/ ]
    [  °  ]
    """

    def _f(x: str, out: str) -> str:  # pylint:disable=invalid-name
        return out if x in glyph else " "

    representation = [
        "".join([" ", _f("1", "/"), _f("W", "|"), _f("2", "\\"), " "]),
        "".join([_f("1", "/"), " ", _f("W", "|"), " ", _f("2", "\\")]),
        "".join([_f("3", "\\"), " ", _f("W", "|"), " ", _f("4", "/")]),
        "".join([_f("Q", "|"), _f("3", "\\"), _f("W", "|"), _f("4", "/"), " "]),
        "".join([_f("Q", "|"), " ", _f("R", "|"), " ", " "]),
        "-----",
        "".join([_f("Z", "|"), " ", " ", " ", " "]),
        "".join([_f("Z", "|"), _f("A", "/"), _f("X", "|"), _f("S", "\\"), " "]),
        "".join([_f("A", "/"), " ", _f("X", "|"), " ", _f("S", "\\")]),
        "".join([_f("D", "\\"), " ", _f("X", "|"), " ", _f("F", "/")]),
        "".join([" ", _f("D", "\\"), _f("X", "|"), _f("F", "/"), " "]),
        "".join([" ", " ", _f("V", "°"), " ", " "]),
    ]
    return representation


def _main():
    lrk = init_lark()
    visitor = TunicNotes()
    for fname in glob.iglob("./notes/*.txt"):
        print(fname)
        tree = load_file(fname, lrk)
        visitor.visit(tree)
        # print(tree.pretty())


if __name__ == "__main__":
    _main()
