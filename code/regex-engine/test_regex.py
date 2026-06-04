"""正则表达式引擎测试"""
import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from matcher import Regex, match, search
from nfa import State, NFA, literal_nfa, epsilon_nfa, concat_nfa, union_nfa, star_nfa
from compiler import compile_regex, insert_explicit_concat, to_postfix


class TestCompilation(unittest.TestCase):
    CON = '\x00'

    def test_insert_concat(self):
        self.assertEqual(insert_explicit_concat("ab"), "a\x00b")
        self.assertEqual(insert_explicit_concat("abc"), "a\x00b\x00c")
        self.assertEqual(insert_explicit_concat("a|b"), "a|b")
        self.assertEqual(insert_explicit_concat("ab|c"), "a\x00b|c")
        self.assertEqual(insert_explicit_concat("(ab)"), "(a\x00b)")

    def test_compile_literal(self):
        nfa = compile_regex("a")
        self.assertIsNotNone(nfa)

    def test_compile_union(self):
        nfa = compile_regex("a|b")
        self.assertIsNotNone(nfa)

    def test_compile_concat(self):
        nfa = compile_regex("ab")
        self.assertIsNotNone(nfa)

    def test_compile_star(self):
        nfa = compile_regex("a*")
        self.assertIsNotNone(nfa)

    def test_compile_plus(self):
        nfa = compile_regex("a+")
        self.assertIsNotNone(nfa)


class TestMatch(unittest.TestCase):
    def test_literal_match(self):
        regex = Regex("hello")
        self.assertTrue(regex.match("hello"))
        self.assertFalse(regex.match("world"))

    def test_union(self):
        regex = Regex("cat|dog")
        self.assertTrue(regex.match("cat"))
        self.assertTrue(regex.match("dog"))
        self.assertFalse(regex.match("bird"))

    def test_concat(self):
        regex = Regex("ab")
        self.assertTrue(regex.match("ab"))
        self.assertFalse(regex.match("a"))

    def test_star(self):
        regex = Regex("a*")
        self.assertTrue(regex.match(""))
        self.assertTrue(regex.match("a"))
        self.assertTrue(regex.match("aaaa"))

    def test_plus(self):
        regex = Regex("a+")
        self.assertFalse(regex.match(""))
        self.assertTrue(regex.match("a"))
        self.assertTrue(regex.match("aaa"))

    def test_optional(self):
        regex = Regex("colou?r")
        self.assertTrue(regex.match("color"))
        self.assertTrue(regex.match("colour"))

    def test_group(self):
        regex = Regex("(ab)+")
        self.assertTrue(regex.match("ab"))
        self.assertTrue(regex.match("abab"))
        self.assertFalse(regex.match("aba"))

    def test_dot(self):
        regex = Regex("h.t")
        self.assertTrue(regex.match("hot"))
        self.assertTrue(regex.match("hat"))
        self.assertTrue(regex.match("hzt"))
        self.assertFalse(regex.match("ht"))

    def test_complex(self):
        regex = Regex("a(b|c)*d")
        self.assertTrue(regex.match("ad"))
        self.assertTrue(regex.match("abcd"))
        self.assertTrue(regex.match("abbccd"))
        self.assertFalse(regex.match("abdabc"))

    def test_empty_string(self):
        regex = Regex("")
        self.assertTrue(regex.match(""))
        self.assertFalse(regex.match("a"))


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.regex = Regex("\\d+")

    def test_search_simple(self):
        result = self.regex.search("abc123def")
        self.assertEqual(result, "123")

    def test_search_no_match(self):
        result = self.regex.search("abcdef")
        self.assertIsNone(result)

    def test_findall(self):
        result = self.regex.findall("abc123def456")
        self.assertEqual(result, ["123", "456"])


class TestNFABasics(unittest.TestCase):
    def test_literal_nfa(self):
        nfa = literal_nfa('a')
        self.assertTrue(match(nfa, "a"))
        self.assertFalse(match(nfa, "b"))

    def test_concat_nfa(self):
        nfa = concat_nfa(literal_nfa('a'), literal_nfa('b'))
        self.assertTrue(match(nfa, "ab"))
        self.assertFalse(match(nfa, "a"))

    def test_union_nfa(self):
        nfa = union_nfa(literal_nfa('a'), literal_nfa('b'))
        self.assertTrue(match(nfa, "a"))
        self.assertTrue(match(nfa, "b"))
        self.assertFalse(match(nfa, "c"))

    def test_star_nfa(self):
        nfa = star_nfa(literal_nfa('a'))
        self.assertTrue(match(nfa, ""))
        self.assertTrue(match(nfa, "a"))
        self.assertTrue(match(nfa, "aaa"))
        self.assertFalse(match(nfa, "b"))


if __name__ == '__main__':
    unittest.main()
