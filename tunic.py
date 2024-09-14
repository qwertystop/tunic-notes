"""
For finding patterns in text from the game Tunic
"""

import glob
import itertools
from collections import defaultdict
from pprint import pprint

import lark

GRAMMAR = r"""
start: section
section: "#" HEADER _NEWLINE (section+ | line+)
HEADER: LITERAL
line: (word | ("[" LITERAL "]"))+ _NEWLINE
word: glyph ("/" glyph)*
LITERAL: /[^]\n]+/
glyph: /[1234QWERASDFZXCV-]+/
_NEWLINE: /\n/

%import common.WS_INLINE

%ignore WS_INLINE
%ignore /(?<!.)\n/
"""

# These map all known or suspected glyphs/words to all locations where they have been seen.
SCANNED_TREES: list[lark.Tree] = []
FOUND_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
FOUND_WORDS: defaultdict[str, set[str]] = defaultdict(set)
WORD_TRANSLATIONS: dict[str, str] = {
    "134RX/4WRS": "<TAKE, GET>",
    "12": "<A>",
    "234RXV/WASDFZV": "<ITEM>",
    "123QWRDZX": "you",
    "4RAFX/3AS/WRAS": "<FOUND>",
    "124RSDFX/WRAS": "guard",
    "123WRDV": "<OF>",
    "12WRASX": "<THE>",
    "34QDFZ/WRX": "well",
    "134QRASDFZX/WRX/WRAS": "<SHIELD/BLOCK>",
    "34DFXV": "it",
    "123QWRDZX/3WRSXDF/3WRSX": "uses",
    "124QRSDFZX/WRX/WRASDF/3AS": "golden",
    "124RSX/3AS": "gun",
    "QWRSDFZ/WRX": "bell",
}
SOUND_TRANSLATIONS: dict[str, str] = {
    "3WRSX": "z",
    # maybe "f", blowing-sound, from library picture? but we also have it in "guardhouse"
    "WRSFX": "how",
    # From "well well well" fox at well
    # also from "bell"
    # "34QDFZ": "weh",
    "34Q": "w",
    "DFZ": "eh",
    "WRX": "ll",
    "QWRS": "b",
    # "34DFXV": "it",
    "DF": "ə",
    "12": "ay",
    "WRAS": "d",
    "123QWRDZX": "you",
    # suspected from "guard" and "gun"
    "124RSX": "g",
    "3AS": "n",  # reinforced from <FOUND>
    # speculation from "shield"
    "134QRASDFZX": "she",
    # speculation from "golden"
    "QDFZ": "oh",
}
SUBGLYPH_SOUNDS: dict[frozenset[str], str] = {
    frozenset(g): s for g, s in SOUND_TRANSLATIONS.items()
}


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
        sorted(
            set(glyph.replace("E", "").replace("C", "").replace("-", "")),
            key=glyph_ordering,
        )
    )


class CleanAndAnnotate(lark.visitors.Transformer_InPlace):
    """Clean glyphs"""

    def glyph(self, tree):  # pylint:disable=invalid-name
        """Standardize glyphs by deduplicating and sorting them."""
        assert len(tree.children) == 1
        resolved = clean_glyph(tree.children[0].value)
        return resolved

    def word(self, tree):
        """Print representation of whole word"""
        tree.this_word = "/".join(tree.children)
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
            FOUND_GLYPHS[glyph].add(tree.this_word)

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


def process_text(text: str):
    output_a = []
    output_b = []
    for word in text.split(" "):
        output_a.append(WORD_TRANSLATIONS.get(word, word))
        for glyph in word.split("/"):
            by_sound: list = []
            if glyph in SOUND_TRANSLATIONS:
                by_sound.append(SOUND_TRANSLATIONS[glyph])
            else:
                # let's try subglyph representations
                glyph_parts = frozenset(glyph)
                # what identified subglyphs fit here?
                possible_components = [
                    rep for rep in SUBGLYPH_SOUNDS if rep < glyph_parts
                ]
                if possible_components:
                    # try a low-effort solution first: permutations
                    options: set[str] = set()
                    for sequence in itertools.permutations(possible_components):
                        # remove subglyphs until nothing remaining fits
                        sounds = []
                        _g = glyph_parts.copy()
                        for subglyph in sequence:
                            if subglyph <= _g:
                                _g = _g - subglyph
                                sounds.append(SUBGLYPH_SOUNDS[subglyph])
                                if not _g:
                                    # nothing left to extract
                                    break
                        else:  # no break
                            # we ran out of things to try with some glyph remaining
                            # include what's left in the return
                            sounds.append(clean_glyph("".join(_g)))
                        # string the sounds together
                        options.add("_".join(sounds))
                    by_sound.append(options)
                else:
                    # found nothing, just leave an unidentified glyph
                    by_sound.append(glyph)
            output_b.append(by_sound)

    print(text)
    render_text(text)
    print(output_a)
    pprint(output_b)


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
    for WORD in FOUND_WORDS:
        process_text(WORD)
        input("press enter to continue")
