"""
For finding patterns in text from the game Tunic
"""

import glob
from collections import defaultdict

import lark

GRAMMAR = r"""
start: section
section: "#" HEADER _NEWLINE (section+ | line+)
HEADER: LITERAL
line: (word | ("[" LITERAL "]"))+ _NEWLINE
word: glyph ("/" glyph)*
LITERAL: /[^]\n]+/
glyph: ( GLYPH_TOP GLYPH_BOT )
       | GLYPH_TOP -> top_glyph_only
       | GLYPH_BOT -> bot_glyph_only
GLYPH_TOP: /[1234QWER]+/
GLYPH_BOT: /[ASDFZXCV]+/
_NEWLINE: /\n/

%import common.WS_INLINE

%ignore WS_INLINE
%ignore /(?<!.)\n/
"""

# These map all detected glyphs and words to all locations where they have been seen.
SCANNED_TREES: list[lark.Tree] = []
FOUND_WORDS: defaultdict[str, list[str]] = defaultdict(list)
FOUND_TOP_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
FOUND_BOT_GLYPHS: defaultdict[str, set[str]] = defaultdict(set)
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
                FOUND_WORDS[word.this_word].append(
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
        print(tree.pretty())
    return trees


if __name__ == "__main__":
    _main()
