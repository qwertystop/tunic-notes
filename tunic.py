"""
For finding patterns in text from the game Tunic
"""

import glob
from collections import defaultdict
from pprint import pprint

import lark

GRAMMAR = r"""
start: section
section: "#" HEADER _NEWLINE (section+ | line+)
HEADER: LITERAL
line: (word | ("[" LITERAL "]"))+ _NEWLINE
word: GLYPH ("/" GLYPH)*
LITERAL: /[^]\n]+/
GLYPH: /[1234QWERASDFZXCV]+/
_NEWLINE: /\n/

%import common.WS_INLINE

%ignore WS_INLINE
%ignore /(?<!.)\n/
"""

# These map all detected glyphs and words to all locations where they have been seen.
SCANNED_TREES: list[lark.Tree] = []
FOUND_WORDS: defaultdict[str, set[str]] = defaultdict(set)
FOUND_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
GLYPH_TRANSLATIONS: dict[str, str] = {}


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

    def GLYPH(self, token):  # pylint:disable=invalid-name
        """Standardize glyphs by deduplicating and sorting them."""
        resolved = clean_glyph(token.value)
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


def _main():
    lrk = init_lark()
    visitor = TunicNotes()
    trees = {}
    for fname in glob.iglob("./notes/*.txt"):
        print(fname)
        tree = load_file(fname, lrk)
        visitor.visit(tree)
        trees[fname] = tree
    pprint(points_of_interest(FOUND_WORDS, 2))
    pprint(points_of_interest(FOUND_GLYPHS, 2))
    return trees


if __name__ == "__main__":
    _main()
