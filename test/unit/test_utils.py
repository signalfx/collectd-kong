# -*- coding: utf-8 -*-
from fnmatch import translate

import pytest

from kong.utils import filter_by_pattern_lists, PatternList


def test_single_pattern():
    pl = PatternList('one')
    assert pl.matches('one') == ['one']
    assert pl.matches('one', 'two') == ['one']
    assert pl.matches('two', 'one') == ['one']
    assert pl.matches('__one__') == []
    assert pl.matches('__one__', '__two__') == []
    assert pl.matches('one', 'one', 'two', 'one') == ['one']


def test_unicode_pattern():
    pl = PatternList(u'ßƒß')
    assert pl.matches(u'ßƒß') == [u'ßƒß']


def test_multiple_patterns():
    pl = PatternList('one', 'two')
    assert pl.matches('one') == ['one']
    assert pl.matches('__one__') == []
    assert pl.matches('two') == ['two']
    assert pl.matches('__two__') == []
    assert pl.matches('one', 'two') == ['one', 'two']
    assert pl.matches('one', 'one', 'two', 'two', 'one', 'two') == ['one', 'two']
    assert pl.matches('two', 'two', 'one', 'two') == ['two', 'one']


def test_multiple_patterns_multiple_wildcards():
    pl = PatternList('*one*', '*two*')
    assert pl.matches('__one') == ['__one']
    assert pl.matches('one__') == ['one__']
    assert pl.matches('__one__') == ['__one__']
    assert pl.matches('__two') == ['__two']
    assert pl.matches('two__') == ['two__']
    assert pl.matches('__two__') == ['__two__']
    assert pl.matches('__three__') == []
    assert pl.matches('two', 'one', '__two__', '__one__', 'three') == ['two', 'one', '__two__', '__one__']


def test_multiple_patterns_multiple_camel_wildcards():
    pl = PatternList('*one*two', '*two*three*four')
    assert pl.matches('__one____two') == ['__one____two']
    assert pl.matches('one____two') == ['one____two']
    assert pl.matches('onetwo') == ['onetwo']
    assert pl.matches('onetwo__') == []
    assert pl.matches('onewo__') == []
    assert pl.matches('_two_three_four') == ['_two_three_four']
    assert pl.matches('two_threefour') == ['two_threefour']
    assert pl.matches('_twothree_four') == ['_twothree_four']
    assert pl.matches('_twothree_four_') == []
    assert pl.matches('_twohree_four_') == []
    assert pl.matches('onetwo', 'onetwo', 'twothreefour', 'twothreefour') == ['onetwo', 'twothreefour']


def test_update():
    pl = PatternList('1')
    assert pl.elements == ['1']
    assert len(pl.patterns) == 1
    assert [pat.pattern for pat in pl.patterns] == [translate('1')]
    pl.update('2', '3')
    assert pl.elements == ['1', '2', '3']
    assert len(pl.patterns) == 3
    assert [pat.pattern for pat in pl.patterns] == [translate(str(i)) for i in range(1, 4)]


one, two, three, four = ['__One__', '__Two__', '__Three__', '__Four__']


@pytest.mark.parametrize('white, black, expected_hits, expected_misses',
                         ((['One', 'Two'], [], [], [one, two, three, four]),
                          ([one], [], [one], [two, three, four]),
                          (['*O*', '*T*'], ['*Th*'], [one, two], [three, four]),
                          (['*'], ['Three', 'Four'], [one, two, three, four], []),
                          (['*'], [three, four], [one, two], [three, four]),
                          (['*'], ['*'], [], [one, two, three, four])))
def test_filter_by_pattern_lists(white, black, expected_hits, expected_misses):
    whitelist, blacklist = [PatternList(*ls) for ls in (white, black)]
    hits, misses = filter_by_pattern_lists([one, two, three, four], whitelist, blacklist)
    assert hits == expected_hits
    assert misses == expected_misses
