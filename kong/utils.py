import fnmatch
import re

from six import text_type


class PatternList(object):

    def __init__(self, *elements):
        self.elements = list(elements)
        self.patterns = self.to_patterns(elements)
        self.match_cache = set()
        self.miss_cache = set()

    def matches(self, *strings):
        matchset = set()
        matches = []
        for string in strings:
            if string in self.match_cache:
                if string not in matchset:
                    matches.append(string)
                    matchset.add(string)
                continue
            if string in self.miss_cache:
                continue
            for pattern in self.patterns:
                if string not in matchset and pattern.match(string):
                    matches.append(string)
                    matchset.add(string)
        return matches

    def to_patterns(self, elements):
        patternized = []
        for element in elements:
            patternized.append(self.to_pattern(element))
        return patternized

    def to_pattern(self, item):
        item = text_type(item)
        updated = fnmatch.translate(item)
        return re.compile(updated)

    def update(self, *elements):
        self.elements.extend(elements)
        self.patterns.extend(self.to_patterns(elements))

    def __str__(self):
        return str(self.elements)

    __repr__ = __str__


def filter_by_pattern_lists(attributes, whitelist, blacklist):
    white_matches = set(whitelist.matches(*attributes))
    black_matches = set(blacklist.matches(*attributes))
    hits = []
    misses = []
    for attr in attributes:
        if attr in white_matches and attr not in black_matches:
            hits.append(attr)
        else:
            misses.append(attr)
    return hits, misses
