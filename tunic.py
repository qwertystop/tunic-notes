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
section: "#" HEADER _NEWLINE (section+ | _line+)
HEADER: LITERAL
_line: (word | ("[" LITERAL "]"))+ _NEWLINE
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
SOURCE_TEXTS: list[tuple[str, str]] = []
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
# Prior understanding overhauled by discovery of page 54,
# which has what appears to be a syllabary?
# Further, its structure implies that some of what we have been distinguishing
# are not in fact significant (lengths of verticals are not noted there).
# New glyph structure:
# Length of vertical may not matter? Or it matters but page 54 doesn't show
# that aspect very well, because why would any of this be easy.
# Page 54 shows 18 different glyphs made exclusively of the outer hexagon,
# and 24 glyphs made entirely of the inner lines.
# None of these distinguish upper and lower parts of the left edge of the hex.
# The length of the inner vertical varies (may or may not extend past upper or
# lower branch points), but where there is no branch, length is unclear.
# Further notes show glyphs made by compositing two of these (outer + inner).
# None of them have the dot on the bottom that we've seen before. So that's
# even more baffling.

# Based on the above, glyph components are:
# five segments of outer line (two points plus left edge)
# four confidently-known segments of interior (branches)
# possibly-ambiguous stem

# new rep:
# Outer part unchanged, except Q and Z are now the same.
# Inner part, four branches plus stem. If any branches are present on either the
# upward or downward side, the stem may either extend past the branch point to
# the tip of the hex in that direction, or it may not. If there are no branches,
# the chart present on page 54 does not provide clarity for whether the stem
# stops at the branch-point or extends to the tip.
# Old notation had:
# Q: branch-to-tip, upward
# R: center-to-branch, upward
# X: Branch-to-tip, downward.
# Center-to-branch downward does not appear in any strict (centerline-drawn)
# glyphs.

# At this point I am baffled, frustrated, and fed up. Since Zodi has finished
# the game, it is unlikely I will return to this in the near future.


def render_text(text: str):
    """Convert dense representation to printable text"""
    spacing = 3
    max_length = 80
    text_rep = [""] * 12

    def _flush():
        nonlocal text_rep
        for line in text_rep:
            print(line)
        text_rep = [""] * 12

    for word in text.split(" "):
        if word[0] == "[":
            # literal
            word_rep = [" " * len(word)] * 12
            word_rep[5] = word
        else:
            word_rep = [""] * 12
            for glyph in word.split("/"):
                for i, new in enumerate(_render_glyph(glyph)):
                    word_rep[i] = word_rep[i] + new
        if (len(text_rep[0]) + len(word_rep[0]) + spacing) > max_length:
            _flush()
        for i, new in enumerate(word_rep):
            text_rep[i] = text_rep[i] + (" " * spacing) + new
    _flush()


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

    Original transcription method:
    Upper diamond is 1234 (clockwise from top left)
    Upper left vertical: Q
    Upper inside vertical: W
    Upper descender vertical: R
    Lower diamond: ASDF (clockwise from top left)
    Lower left vertical: Z
    Lower inside vertical: X
    Lower dot: V
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
        this_word = "/".join(tree.children)
        for glyph in tree.children:
            FOUND_GLYPHS[glyph].add(this_word)
        return this_word

    def section(self, tree):
        """A block of text, possibly across multiple text boxes"""
        assert tree.children[0].type == "HEADER"
        section_name = tree.children[0].value
        subsections: list[dict] = []
        text: list[str] = []
        words: list[str] = []
        for word in tree.children[1:]:
            if isinstance(word, lark.Token) and word.type == "LITERAL":
                # literals
                text.append("[" + word.value + "]")
            elif isinstance(word, dict):
                # subsection
                subsections.append(word)
            else:
                words.append(word)
                text.append(word)
        whole_line = " ".join(text)
        for word in words:
            FOUND_WORDS[word].add(whole_line)
        SOURCE_TEXTS.append((section_name, whole_line))
        return {"header": section_name, "subsections": subsections, "text": text}

    def start(self, tree):
        return tree.children


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


def process_text(text: str):
    output_a = []
    output_b = []
    for word in text.split(" "):
        if word[0] == "[":
            # this is a literal, skip it
            output_a.append(word)
            output_b.append(word)
            continue
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
    for fname in glob.iglob("./notes/*.txt"):
        print(fname)
        _tree = load_file(fname, lrk)
        # print(tree.pretty())


def interactive():
    def known_texts():
        for header, text in SOURCE_TEXTS:
            if text:
                yield (header, text)

    ts = itertools.cycle(known_texts())
    while True:
        i = input("Input text, or leave blank for next known line: ")
        if i:
            process_text(i)
        else:
            header, text = next(ts)
            print(header)
            process_text(text)


if __name__ == "__main__":
    _main()
    interactive()
