# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import math
import os
import unittest
from collections import OrderedDict

import json5


class TestLoads(unittest.TestCase):
    maxDiff = None

    def check(self, s, obj, strict=True):
        self.assertEqual(obj, json5.loads(s, strict=strict))

    def check_fail(self, s, err=None):
        try:
            json5.loads(s)
            self.fail()  # pragma: no cover
        except ValueError as e:
            if err is not None:
                self.assertEqual(err, str(e))

    def test_arrays(self):
        self.check('[]', [])
        self.check('[0]', [0])
        self.check('[0,1]', [0, 1])
        self.check('[ 0 , 1 ]', [0, 1])

        try:
            json5.loads('[ ,]')
            self.fail()  # pragma: no cover
        except ValueError as e:
            self.assertIn('Unexpected "," at column 3', str(e))

    def test_bools(self):
        self.check('true', True)
        self.check('false', False)

    def test_duplicate_keys_should_be_allowed(self):
        self.assertEqual(
            json5.loads('{foo: 1, foo: 2}', allow_duplicate_keys=True),
            {'foo': 2},
        )

    def test_duplicate_keys_should_be_allowed_by_default(self):
        self.check('{foo: 1, foo: 2}', {'foo': 2})

    def test_duplicate_keys_should_not_be_allowed(self):
        self.assertRaises(
            ValueError,
            json5.loads,
            '{foo: 1, foo: 2}',
            allow_duplicate_keys=False,
        )

        # Also check to make sure we don't reject things incorrectly.
        self.assertEqual(
            json5.loads('{foo: 1, bar: 2}', allow_duplicate_keys=False),
            {'foo': 1, 'bar': 2},
        )

    def test_empty_strings_are_errors(self):
        self.check_fail('', 'Empty strings are not legal JSON5')

    def test_partial_strings_are_errors(self):
        self.check_fail("'", '<string>:1 Unexpected end of input at column 2')

    def test_encoding(self):
        self.assertEqual(json5.loads(b'"\xf6"', encoding='iso-8859-1'), '\xf6')
        with self.assertRaises(UnicodeDecodeError):
            json5.load(io.BytesIO(b'\xff'))

    def test_numbers(self):
        # decimal literals
        self.check('1', 1)
        self.check('-1', -1)
        self.check('+1', 1)
        self.check_fail('--6', '<string>:1 Unexpected "-" at column 2')
        self.check_fail('++6', '<string>:1 Unexpected "+" at column 2')
        self.check_fail('+-6', '<string>:1 Unexpected "-" at column 2')

        # hex literals
        self.check('0xf', 15)
        self.check('0xfe', 254)
        self.check('0xfff', 4095)
        self.check('0XABCD', 43981)
        self.check('0x123456', 1193046)
        self.check_fail('0x+', '<string>:1 Unexpected "+" at column 3')

        # signed hex literals
        self.check('+0xf', 15)
        self.check('-0xf', -15)
        self.check('-0XABCD', -43981)
        self.check('-0x0', 0)

        # floats
        self.check('1.5', 1.5)
        self.check('1.5e3', 1500.0)
        self.check('-0.5e-2', -0.005)
        self.check_fail('--6.0', '<string>:1 Unexpected "-" at column 2')
        self.check_fail('++6.0', '<string>:1 Unexpected "+" at column 2')
        self.check_fail('+-6.0', '<string>:1 Unexpected "-" at column 2')

        # names
        self.check('Infinity', float('inf'))
        self.check('+Infinity', float('inf'))
        self.check('-Infinity', float('-inf'))
        self.assertTrue(math.isnan(json5.loads('NaN')))
        self.assertTrue(math.isnan(json5.loads('-NaN')))

        # syntax errors
        self.check_fail('14d', '<string>:1 Unexpected "d" at column 3')

    def test_identifiers(self):
        self.check('{a: 1}', {'a': 1})
        self.check('{$: 1}', {'$': 1})
        self.check('{_: 1}', {'_': 1})
        self.check('{a_b: 1}', {'a_b': 1})
        self.check('{a$: 1}', {'a$': 1})

        # This valid JavaScript but not valid JSON5; keys must be identifiers
        # or strings.
        self.check_fail('{1: 1}')

    def test_identifiers_unicode(self):
        # It would be silly to try and test all of the possible unicode
        # characters for correctness, but we can at least check each
        # legal Unicode category.

        # Latin Capital letter A with Tilde, category Lu (uppercase letter)
        self.check('{\xc3: 1}', {'\xc3': 1})

        # Latin small A with Ring above, category Ll (lowercase letter)
        self.check('{\u00e5: 1}', {'\u00e5': 1})

        # Modifier Letter small H, category Lm (modifier letter)
        self.check('{\u02b0: 1}', {'\u02b0': 1})

        # Latin Letter Two with Stroke, category Lo (other letter)
        self.check('{\u01bb: 1}', {'\u01bb': 1})

        # Latin Capital Letter L with Small Letter J
        # (category Lt, titlecase letter)
        self.check('{\u01c8: 1}', {'\u01c8': 1})

        # Roman Numeral One (category Nl, letter number)
        self.check('{\u2160: 1}', {'\u2160': 1})

        # Combining Diaresis (category Mn, non-spacing mark)
        self.check('{a\u0308o: 1}', {'a\u0308o': 1})

        # Rejang Virama (category Mc, spacing mark)
        self.check('{a\ua953o: 1}', {'a\ua953o': 1})

        # Arabic-Indic Digit Zero (category Nd, decimal number)
        self.check('{a\u0660: 1}', {'a\u0660': 1})

        # Undertie (category Pc, connector punctuation)
        self.check('{a\u203fb: 1}', {'a\u203fb': 1})

    def test_null(self):
        self.check('null', None)

    def test_object_hook(self):
        def hook(d):
            return [d]

        self.assertEqual(
            json5.loads('{foo: 1}', object_hook=hook), [{'foo': 1}]
        )

    def test_object_pairs_hook(self):
        def hook(pairs):
            return pairs

        self.assertEqual(
            json5.loads('{foo: 1, bar: 2}', object_pairs_hook=hook),
            [('foo', 1), ('bar', 2)],
        )

    def test_objects(self):
        self.check('{}', {})
        self.check('{"foo": 0}', {'foo': 0})
        self.check('{"foo":0,"bar":1}', {'foo': 0, 'bar': 1})
        self.check('{ "foo" : 0 , "bar" : 1 }', {'foo': 0, 'bar': 1})

    def test_parse_constant(self):
        def hook(x):
            return x

        self.assertEqual(
            json5.loads('-Infinity', parse_constant=hook), '-Infinity'
        )
        self.assertEqual(json5.loads('NaN', parse_constant=hook), 'NaN')

    def test_parse_float(self):
        def hook(x):
            return x

        self.assertEqual(json5.loads('1.0', parse_float=hook), '1.0')

    def test_parse_int(self):
        def hook(x, base=10):
            del base
            return x

        self.assertEqual(json5.loads('1', parse_int=hook), '1')

    def test_sample_file(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'sample.json5')
        with open(path, encoding='utf-8') as fp:
            obj = json5.load(fp)
        self.assertEqual(
            {
                'oh': [
                    "we shouldn't forget",
                    'arrays can have',
                    'trailing commas too',
                ],
                'this': 'is a multi-line string',
                'delta': 10,
                'hex': 3735928559,
                'finally': 'a trailing comma',
                'here': 'is another',
                'to': float('inf'),
                'while': True,
                'half': 0.5,
                'foo': 'bar',
            },
            obj,
        )

    def test_load_fails(self):
        s = io.StringIO('x')
        with self.assertRaises(ValueError):
            json5.load(s)

    def test_strict(self):
        # From [GitHub issue #82](https://github.com/dpranke/pyjson5/issues/82)
        d = '{\n"key": "value\nover two lines",\n}'
        self.check_fail(d, '<string>:2 Unexpected "\n" at column 14')
        self.check(d, {'key': 'value\nover two lines'}, strict=False)

        # Test w/ single quotes to get coverage.
        d = "{\n'key': 'value\nover two lines',\n}"
        self.check_fail(d, '<string>:2 Unexpected "\n" at column 14')
        self.check(d, {'key': 'value\nover two lines'}, strict=False)

    def test_strings(self):
        self.check('"foo"', 'foo')
        self.check("'foo'", 'foo')

        # escape chars
        self.check("'\\b\\t\\f\\n\\r\\v\\\\'", '\b\t\f\n\r\v\\')
        self.check("'\\''", "'")
        self.check('"\\""', '"')

        # hex literals
        self.check('"\\x66oo"', 'foo')

        # unicode literals
        self.check('"\\u0066oo"', 'foo')

        # string literals w/ continuation markers at the end of the line.
        # These should not have spaces is the result.
        self.check('"foo\\\nbar"', 'foobar')
        self.check("'foo\\\nbar'", 'foobar')

        # unterminated string literals.
        self.check_fail('"\n')
        self.check_fail("'\n")

        # bad hex literals
        self.check_fail("'\\x0'")
        self.check_fail("'\\xj'")
        self.check_fail("'\\x0j'")

        # bad unicode literals
        self.check_fail("'\\u0'")
        self.check_fail("'\\u00'")
        self.check_fail("'\\u000'")
        self.check_fail("'\\u000j'")
        self.check_fail("'\\u00j0'")
        self.check_fail("'\\u0j00'")
        self.check_fail("'\\uj000'")

    def test_unrecognized_escape_char(self):
        self.check(r'"\/"', '/')

    def test_nul(self):
        self.check(r'"\0"', '\x00')

    def test_whitespace(self):
        # Whitespace should be allowed before and after a value.
        self.check('\n1', 1)
        self.check('\r1', 1)
        self.check('\r\n1', 1)
        self.check('\t1', 1)
        self.check('\v1', 1)
        self.check('\ufeff 1', 1)
        self.check('\u00a0 1', 1)
        self.check('\u2028 1', 1)  # line separator
        self.check('\u2029 1', 1)  # paragraph separator
        self.check('\u2000 1', 1)  # En quad, unicode category Zs

        self.check('1\n', 1)

    def test_error_reporting(self):
        self.check_fail('[ ,]', err='<string>:1 Unexpected "," at column 3')

        self.check_fail(
            '{\n'
            '    version: "1.0",\n'
            '    author: "John Smith",\n'
            '    people : [\n'
            '        "Monty",\n'
            '        "Python"foo\n'
            '    ]\n'
            '}\n',
            err='<string>:6 Unexpected "f" at column 17',
        )

    def test_no_extra_characters_in_value(self):
        self.check_fail('0 1', '<string>:1 Unexpected "1" at column 3')
        self.check_fail('0 a', '<string>:1 Unexpected "a" at column 3')

    # ----------------------------------------------------------------
    # The tests below pin down the *current* behavior for the three
    # areas that were unclear when using json5 on user-uploaded config
    # files. They are written as characterization tests: where the
    # actual behavior differs from what a caller would reasonably
    # expect, the assertion records the actual behavior and a comment
    # says which side we believe is wrong. The implementation was not
    # changed to make these pass.
    # ----------------------------------------------------------------

    def test_syntax_error_message_has_line_and_column(self):
        # Syntax errors do at least say which line/column (both 1-based)
        # the parser got to, and give the offending character.
        self.check_fail(
            '{\n    bad: ,\n}',
            err='<string>:2 Unexpected "," at column 10',
        )
        self.check_fail(
            '{a: 1, a: 2',
            err='<string>:1 Unexpected end of input at column 12',
        )
        # load() reads from a file but still reports "<string>";
        # it has no way to report the real file name (impl side).
        with self.assertRaises(ValueError) as cm:
            json5.load(io.StringIO('{\n    bad: ,\n}'))
        self.assertEqual(
            str(cm.exception),
            '<string>:2 Unexpected "," at column 10',
        )

    def test_duplicate_key_error_has_no_position(self):
        # EXPECTATION GAP (impl side): a duplicate key is a semantic
        # error found after parsing, and the message is a bare
        # 'Duplicate key "x" found in object' with no file name, line,
        # column, or the offending object's path. A user with a
        # hundreds-of-lines config file cannot tell where to look.
        with self.assertRaises(ValueError) as cm:
            json5.loads('{a: 1, a: 2}', allow_duplicate_keys=False)
        self.assertEqual(
            str(cm.exception),
            'Duplicate key "a" found in object',
        )
        self.assertNotIn('column', str(cm.exception))
        # Unlike json.JSONDecodeError, the exception carries no
        # structured location attributes, so callers can't recover the
        # position programmatically either.
        self.assertFalse(hasattr(cm.exception, 'pos'))
        self.assertFalse(hasattr(cm.exception, 'lineno'))
        self.assertFalse(hasattr(cm.exception, 'colno'))
        self.assertIs(type(cm.exception), ValueError)

    def test_duplicate_keys_in_nested_objects_report_first_only(self):
        # Detection happens per-object during a single depth-first
        # conversion walk, so exactly one error is raised -- the first
        # duplicate encountered -- rather than an aggregated list.
        # Inner objects are checked before the outer object's pairs are
        # finished, so an inner duplicate is reported even when the
        # outer object also has a (different) duplicate key.
        with self.assertRaisesRegex(
            ValueError, r'^Duplicate key "innerkey" found in object$'
        ):
            json5.loads(
                '{'
                '"outerkey": 0, '
                '"o": {"innerkey": 1, "innerkey": 2}, '
                '"outerkey": 3'
                '}',
                allow_duplicate_keys=False,
            )

        # A duplicate nested inside an array element is still caught.
        with self.assertRaisesRegex(
            ValueError, r'^Duplicate key "a" found in object$'
        ):
            json5.loads(
                '[{"a": 1, "a": 2}]', allow_duplicate_keys=False
            )

        # Three copies of a key in one object still produce only the
        # one first-duplicate error; the second repeated occurrence is
        # never reached.
        with self.assertRaisesRegex(
            ValueError, r'^Duplicate key "a" found in object$'
        ):
            json5.loads(
                '{"a": 1, "a": 2, "a": 3}',
                allow_duplicate_keys=False,
            )

        # The same key used in two *sibling* objects is not a
        # duplicate; the key set is local to each object.
        self.assertEqual(
            json5.loads(
                '{"x": {"k": 1}, "y": {"k": 2}}',
                allow_duplicate_keys=False,
            ),
            {'x': {'k': 1}, 'y': {'k': 2}},
        )

    def test_strict_unterminated_strings(self):
        # strict=True (the default): a bare CR or LF inside a quoted
        # string terminates the token, so the string looks
        # unterminated and parsing fails, for both quote styles.
        for q in ('"', "'"):
            with self.subTest(quote=q, newline='\\n'):
                with self.assertRaises(ValueError) as cm:
                    json5.loads(q + 'abc\n' + q, strict=True)
                self.assertIn('Unexpected "\n" at column 5', str(cm.exception))
            with self.subTest(quote=q, newline='\\r'):
                with self.assertRaises(ValueError) as cm:
                    json5.loads(q + 'abc\r' + q, strict=True)
                self.assertIn('Unexpected "\r" at column 5', str(cm.exception))

        # strict=False: bare CR/LF (and CRLF) inside strings are
        # accepted and become literal characters in the value.
        for q in ('"', "'"):
            self.assertEqual(
                json5.loads(q + 'abc\n' + q, strict=False),
                'abc\n',
            )
            self.assertEqual(
                json5.loads(q + 'abc\r\n' + q, strict=False),
                'abc\r\n',
            )

        # A string actually unterminated at end of input is an error in
        # both modes; strict only relaxes CR/LF. The reported position is
        # end of input (0-based), i.e. column == len(s) + 1.
        for q in ('"', "'"):
            for strict in (True, False):
                with self.subTest(quote=q, strict=strict):
                    with self.assertRaises(ValueError) as cm:
                        json5.loads(q + 'abc', strict=strict)
                    self.assertEqual(
                        str(cm.exception),
                        '<string>:1 Unexpected end of input at column 5',
                    )

        # EXPECTATION GAP (impl side): strict=False relaxes only ASCII
        # CR/LF. U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR
        # are JSON5 line terminators too, but they are errors even with
        # strict=False.
        for ch in ('\u2028', '\u2029'):
            with self.subTest(ch=ch):
                with self.assertRaises(ValueError) as cm:
                    json5.loads('"a' + ch + 'b"', strict=False)
                self.assertIn('Unexpected', str(cm.exception))

        # EXPECTATION GAP / naming note: strict in json5 does NOT mean
        # what strict means in the stdlib json module. Other raw control
        # characters (TAB, NUL) are legal inside strings in *both*
        # modes; only CR/LF are gated.
        for ch in ('\t', '\x00', '\x01'):
            self.assertEqual(
                json5.loads('"a' + ch + 'b"', strict=True),
                'a' + ch + 'b',
            )

        # A backslash-escaped line continuation is accepted in both
        # modes and is removed entirely from the value.
        self.assertEqual(json5.loads('"a\\\nb"', strict=True), 'ab')
        self.assertEqual(json5.loads('"a\\\nb"', strict=False), 'ab')

    def test_single_quotes_and_trailing_commas_ignore_strict(self):
        # Single-quoted strings and trailing commas are core JSON5
        # features: both are legal regardless of strict, and strict
        # only affects CR/LF inside strings.
        for strict in (True, False):
            self.assertEqual(
                json5.loads("'abc'", strict=strict), 'abc'
            )
            self.assertEqual(
                json5.loads('{a: 1,}', strict=strict), {'a': 1}
            )
            self.assertEqual(
                json5.loads('[1,]', strict=strict), [1]
            )

        # But two commas / a comma where a member must be are still
        # syntax errors in both modes.
        for strict in (True, False):
            with self.subTest(strict=strict):
                with self.assertRaises(ValueError):
                    json5.loads('{,}', strict=strict)
                with self.assertRaises(ValueError):
                    json5.loads('{a: 1,,}', strict=strict)


class TestParse(unittest.TestCase):
    maxDiff = None

    def check(self, s, obj, err, pos, consume_trailing=True, start=0):
        actual_obj, actual_err, actual_pos = json5.parse(
            s, consume_trailing=consume_trailing, start=start
        )
        self.assertEqual(obj, actual_obj)
        self.assertEqual(err, actual_err)
        self.assertEqual(pos, actual_pos)

    def test_parse(self):
        self.check('4', 4, err=None, pos=1)
        self.check('4 ', 4, err=None, pos=2)
        self.check('4 ', 4, err=None, pos=1, consume_trailing=False)
        self.check(
            'x', None, err='<string>:1 Unexpected "x" at column 1', pos=0
        )
        self.check(
            '4 x', None, err='<string>:1 Unexpected "x" at column 3', pos=2
        )
        self.check('4 x', 4, err=None, pos=1, consume_trailing=False)
        self.check('x 4', 4, err=None, pos=3, start=1)
        self.check(
            'x y',
            None,
            err='<string>:1 Unexpected "y" at column 3',
            pos=2,
            start=1,
        )

        val, err, pos = json5.parse('[][]', consume_trailing=False)
        self.assertEqual(val, [])
        self.assertEqual(err, None)
        self.assertEqual(pos, 2)
        val, err, pos = json5.parse('[][]', consume_trailing=False, start=pos)
        self.assertEqual(val, [])
        self.assertEqual(err, None)
        self.assertEqual(pos, 4)

    def test_position_on_success(self):
        # On success position is the absolute (0-based) index one past
        # the last character consumed. Leading whitespace is always
        # consumed; with consume_trailing=True trailing whitespace is
        # consumed too (so position == len(s)), with False it is not.
        val, err, pos = json5.parse('12 34', consume_trailing=False)
        self.assertEqual(val, 12)
        self.assertEqual(err, None)
        self.assertEqual(pos, 2)

        # Default (consume_trailing=True): trailing whitespace consumed.
        val, err, pos = json5.parse('1  ')
        self.assertEqual((val, err, pos), (1, None, 3))
        val, err, pos = json5.parse('1  ', consume_trailing=False)
        self.assertEqual((val, err, pos), (1, None, 1))

        # Position is relative to the start of the string even when
        # parsing started at an offset (leading whitespace is skipped).
        val, err, pos = json5.parse('x  42', start=1, consume_trailing=False)
        self.assertEqual((val, err, pos), (42, None, 5))

        # Objects/arrays: position lands right after the closing
        # bracket with consume_trailing=False.
        val, err, pos = json5.parse(
            '{"a": 1}, "b"', consume_trailing=False
        )
        self.assertEqual((val, err, pos), ({'a': 1}, None, 8))
        val, err, pos = json5.parse('[1,2] 3', consume_trailing=False)
        self.assertEqual((val, err, pos), ([1, 2], None, 5))
        val, err, pos = json5.parse('{}{}', consume_trailing=False)
        self.assertEqual((val, err, pos), ({}, None, 2))

    def test_resume_from_position_with_consume_trailing_false(self):
        # The intended streaming use: feed position back in via start=
        # to read the next value. Whitespace gaps are skipped
        # automatically; the caller must skip other separators (e.g. a
        # comma) itself -- resuming directly on a comma fails.
        s = '{}  {}'
        val, err, pos = json5.parse(s, consume_trailing=False)
        self.assertEqual((val, err, pos), ({}, None, 2))
        val, err, pos = json5.parse(
            s, consume_trailing=False, start=pos
        )
        self.assertEqual((val, err, pos), ({}, None, 6))

        # The documented loop pattern (skip whitespace before resuming).
        s = '1 2 3 4'
        values = []
        start = 0
        while True:
            v, err, pos = json5.parse(
                s, start=start, consume_trailing=False
            )
            if err:
                self.fail(err)  # pragma: no cover
            values.append(v)
            start = pos
            if start == len(s) or s[start:].isspace():
                break
        self.assertEqual(values, [1, 2, 3, 4])

        # A comma is not whitespace: restarting at it is an error, and
        # the reported position is the comma itself (0-based).
        val, err, pos = json5.parse('1, 2', consume_trailing=False)
        self.assertEqual((val, err, pos), (1, None, 1))
        val, err, pos = json5.parse(
            '1, 2', consume_trailing=False, start=pos
        )
        self.assertEqual(
            (val, err, pos),
            (
                None,
                '<string>:1 Unexpected "," at column 2',
                1,
            ),
        )

    def test_position_on_syntax_error_is_farthest_failure(self):
        # position is NOT always "where it went wrong"; it is the
        # farthest offset the parser reached while trying alternatives.
        # For an unclosed container or string every alternative runs to
        # end of input, so position is len(s) (== last column).
        self.check(
            '{a: 1, a: 2',
            None,
            err='<string>:1 Unexpected end of input at column 12',
            pos=11,
            consume_trailing=False,
        )
        self.check(
            '[1, 2,',
            None,
            err='<string>:1 Unexpected end of input at column 7',
            pos=6,
        )
        self.check(
            '"abc',
            None,
            err='<string>:1 Unexpected end of input at column 5',
            pos=4,
        )

        # When the parser is stopped by an unexpected token, position
        # is the index of that token (0-based; the message column is
        # 1-based).
        self.check(
            '4 x',
            None,
            err='<string>:1 Unexpected "x" at column 3',
            pos=2,
        )
        self.check(
            '{a: 1, b: x}',
            None,
            err='<string>:1 Unexpected "x" at column 11',
            pos=10,
        )
        # After a successful value, trailing junk is reported at the
        # junk character, including across multiple-line documents.
        self.check(
            '{\n    bad: ,\n}',
            None,
            err='<string>:2 Unexpected "," at column 10',
            pos=11,
        )

        # A newline inside an otherwise-closed string reports the
        # newline itself (index 2 == column 3).
        self.check(
            '"a\nb"',
            None,
            err='<string>:1 Unexpected "\n" at column 3',
            pos=2,
        )
        # For an unterminated string after a newline: strict=True
        # stops at the newline (pos 2); strict=False accepts the
        # newline and runs to end of input (pos 4).
        self.check(
            '"a\nb',
            None,
            err='<string>:1 Unexpected "\n" at column 3',
            pos=2,
        )
        val, err, pos = json5.parse('"a\nb', strict=False)
        self.assertIsNone(val)
        self.assertEqual(
            err, '<string>:2 Unexpected end of input at column 2'
        )
        self.assertEqual(pos, 4)

    def test_position_on_duplicate_key_error(self):
        # EXPECTATION GAP (impl side): a duplicate key is found after
        # the whole document has syntactically parsed, so the returned
        # position is where syntax parsing ended (== len(s) here), not
        # the location of the second key. There is no way to point the
        # user at the offending line.
        s = '{"a": 1, "a": 2}'
        val, err, pos = json5.parse(s, allow_duplicate_keys=False)
        self.assertIsNone(val)
        self.assertEqual(err, 'Duplicate key "a" found in object')
        self.assertEqual(pos, len(s))

        # With consume_trailing=True, trailing whitespace has been
        # consumed, so position is end of string as well.
        val, err, pos = json5.parse(
            '{"a": 1, "a": 2}   ', allow_duplicate_keys=False
        )
        self.assertEqual((err, pos), ('Duplicate key "a" found in object', 19))

        # With consume_trailing=False, conversion still runs on the
        # whole parsed value, so the duplicate is caught and position is
        # right after the object (the trailing junk is not examined).
        val, err, pos = json5.parse(
            '{"a": 1, "a": 2} xyz',
            allow_duplicate_keys=False,
            consume_trailing=False,
        )
        self.assertIsNone(val)
        self.assertEqual(err, 'Duplicate key "a" found in object')
        self.assertEqual(pos, 16)

        # Nested duplicates surface with position at the end of the
        # outer document, again with no hint where the duplicate was.
        s = '{"o": {"a": 1, "a": 2}}'
        val, err, pos = json5.parse(s, allow_duplicate_keys=False)
        self.assertEqual(
            (err, pos), ('Duplicate key "a" found in object', len(s))
        )

    def test_unclosed_object_syntax_error_precedes_duplicate_check(self):
        # The reported user example: json5.parse("{a: 1, a: 2",
        # consume_trailing=False). Because the object never closes, the
        # syntax fails at end of input and the allow_duplicate_keys
        # check (which runs only after successful syntax parsing) is
        # never reached -- so this cannot be used to detect the
        # duplicate. EXPECTATION GAP (caller expectation vs impl).
        val, err, pos = json5.parse(
            '{a: 1, a: 2', consume_trailing=False
        )
        self.assertIsNone(val)
        self.assertEqual(
            err, '<string>:1 Unexpected end of input at column 12'
        )
        self.assertEqual(pos, 11)

        # Same input with the brace closes parses fine with the default
        # duplicate policy, and reports the duplicate only when
        # allow_duplicate_keys=False.
        val, err, pos = json5.parse(
            '{a: 1, a: 2}', consume_trailing=False
        )
        self.assertEqual((val, err, pos), ({'a': 2}, None, 12))
        val, err, pos = json5.parse(
            '{a: 1, a: 2}',
            allow_duplicate_keys=False,
            consume_trailing=False,
        )
        self.assertIsNone(val)
        self.assertEqual(err, 'Duplicate key "a" found in object')
        self.assertEqual(pos, 12)


class TestDump(unittest.TestCase):
    def test_basic(self):
        sio = io.StringIO()
        json5.dump(True, sio)
        self.assertEqual('true', sio.getvalue())


class TestDumps(unittest.TestCase):
    maxDiff = None

    def check(self, obj, s, **kwargs):
        self.assertEqual(s, json5.dumps(obj, **kwargs))

    def test_allow_duplicate_keys(self):
        self.assertIn(
            json5.dumps({1: 'foo', '1': 'bar'}),
            {'{"1": "foo", "1": "bar"}', '{"1": "bar", "1": "foo"}'},
        )

        self.assertRaises(
            ValueError,
            json5.dumps,
            {1: 'foo', '1': 'bar'},
            allow_duplicate_keys=False,
        )

    def test_arrays(self):
        self.check([], '[]')
        self.check([1, 2, 3], '[1, 2, 3]')
        self.check(
            [{'foo': 'bar'}, {'baz': 'quux'}], '[{foo: "bar"}, {baz: "quux"}]'
        )

    def test_bools(self):
        self.check(True, 'true')
        self.check(False, 'false')

    def test_check_circular(self):
        # This tests that a non-cyclic object works w/ either flag value.
        obj = [1, 2, 3]
        self.check(obj, '[1, 2, 3]')  # testing the default
        self.check(obj, '[1, 2, 3]', check_circular=True)
        self.check(obj, '[1, 2, 3]', check_circular=False)

        # This tests a trivial cycle.
        obj = [1, 2, 3]
        obj[2] = obj
        self.assertRaises(ValueError, json5.dumps, obj)

        # This checks that json5 doesn't raise an error with
        # check_circular=false and a cycle. However,
        # the underlying Python implementation likely will.
        try:
            json5.dumps(obj, check_circular=False)
            self.fail()  # pragma: no cover
        except RecursionError:
            pass

        # This checks that repeated but non-circular references
        # are okay.
        x = [1, 2]
        y = {'foo': x, 'bar': x}
        self.check(y, '{foo: [1, 2], bar: [1, 2]}')

        # This tests a more complicated cycle.
        x = {}
        y = {}
        z = {}
        z['x'] = x
        z['y'] = y
        z['x']['y'] = y
        z['y']['x'] = x
        self.assertRaises(ValueError, json5.dumps, z)

    def test_custom_arrays(self):
        # A sequence-like object could be dumped by either
        # iterating over it using __iter__, or manually iterating
        # over it using __len__ and __getitem__. As long as one or
        # the other is implemented, this test will pass. The implementation
        # is perhaps more lenient than it should be, as we don't ensure
        # that all three methods are implemented correctly.
        class MyArray:
            def __iter__(self):
                yield 0
                yield 1
                yield 1

            def __getitem__(self, i):
                return 0 if i == 0 else 1  # pragma: no cover

            def __len__(self):
                return 3  # pragma: no cover

        self.assertEqual(json5.dumps(MyArray()), '[0, 1, 1]')

    def test_invalid_collection(self):
        # Check that something that isn't actually an array or a dict doesn't
        # work.
        self.assertRaises(TypeError, json5.dumps, {1, 2, 3})

    def test_custom_numbers(self):
        # See https://github.com/dpranke/pyjson5/issues/57: we
        # need to ensure that we use the bare int.__repr__ and
        # float.__repr__ in order to get legal JSON values when
        # people have custom subclasses with customer __repr__ methods.
        # (This is what JSON does and we want to match it).
        # pylint: disable=no-self-argument, invalid-repr-returned
        class MyInt(int):
            def __repr__(other):  # pragma: no cover
                del other
                self.fail()

        self.assertEqual(json5.dumps(MyInt(5)), '5')

        class MyFloat(float):
            def __repr__(other):  # pragma: no cover
                del other
                self.fail()

        self.assertEqual(json5.dumps(MyFloat(0.5)), '0.5')

    def test_custom_objects(self):
        class MyDict:
            def __iter__(self):  # pragma: no cover
                yield ('a', 1)
                yield ('b', 2)

            def keys(self):
                return ['a', 'b']

            def __getitem__(self, k):
                return {'a': 1, 'b': 2}[k]

            def __len__(self):
                return 2

        self.assertEqual(json5.dumps(MyDict()), '{a: 1, b: 2}')

    def test_custom_encoder(self):
        class Test:
            pass

        class Encoder(json5.JSON5Encoder):
            def default(self, obj):
                assert isinstance(obj, Test)
                return {'foo': 'bar'}

        # This tests that the custom value is indented at the same level
        # that a regular object would be. This is also testing that
        # Encoder.default is only being called when we don't otherwise know
        # how to encode something.
        self.assertEqual(
            '{\n    baz: {\n        foo: "bar",\n    },\n    quux: 4,\n}',
            json5.dumps({'baz': Test(), 'quux': 4}, indent=4, cls=Encoder),
        )

    def test_custom_strings(self):
        class MyStr(str):
            pass

        self.assertEqual(json5.dumps({'foo': MyStr('bar')}), '{foo: "bar"}')

    def test_default(self):
        def _custom_serializer(obj):
            del obj
            return 'something'

        self.assertRaises(TypeError, json5.dumps, set())
        self.assertEqual(
            json5.dumps(set(), default=_custom_serializer), '"something"'
        )

    def test_ensure_ascii(self):
        self.check('\u00fc', '"\\u00fc"')
        self.assertEqual(json5.dumps('\u00fc', ensure_ascii=False), '"\u00fc"')

    def test_indent(self):
        self.assertEqual(json5.dumps([1, 2, 3], indent=None), '[1, 2, 3]')
        self.assertEqual(json5.dumps([1, 2, 3], indent=-1), '[\n1,\n2,\n3,\n]')
        self.assertEqual(json5.dumps([1, 2, 3], indent=0), '[\n1,\n2,\n3,\n]')
        self.assertEqual(json5.dumps([], indent=2), '[]')
        self.assertEqual(
            json5.dumps([1, 2, 3], indent=2), '[\n  1,\n  2,\n  3,\n]'
        )
        self.assertEqual(
            json5.dumps([1, 2, 3], indent=' '), '[\n 1,\n 2,\n 3,\n]'
        )
        self.assertEqual(
            json5.dumps([1, 2, 3], indent='++'), '[\n++1,\n++2,\n++3,\n]'
        )
        self.assertEqual(
            json5.dumps([[1, 2, 3]], indent=2),
            '[\n  [\n    1,\n    2,\n    3,\n  ],\n]',
        )

        self.assertEqual(json5.dumps({}, indent=2), '{}')
        self.assertEqual(
            json5.dumps({'foo': 'bar', 'baz': 'quux'}, indent=2),
            '{\n  foo: "bar",\n  baz: "quux",\n}',
        )

    def test_numbers(self):
        self.check(15, '15')
        self.check(1.0, '1.0')
        self.check(float('inf'), 'Infinity')
        self.check(float('-inf'), '-Infinity')
        self.check(float('nan'), 'NaN')

        for v in (float('inf'), float('-inf'), float('nan')):
            with self.assertRaises(ValueError) as ctx:
                json5.dumps(v, allow_nan=False)
            self.assertIn(str(v), str(ctx.exception))

    def test_null(self):
        self.check(None, 'null')

    def test_separators(self):
        # Check that custom separators work; these separators add an
        # extra space.
        self.check(
            [{'foo': 1}, 2], '[{foo:  1},  2]', separators=(',  ', ':  ')
        )

    def test_objects(self):
        self.check({'foo': 1}, '{foo: 1}')
        self.check({'foo bar': 1}, '{"foo bar": 1}')
        self.check({'1': 1}, '{"1": 1}')

    def test_reserved_words_in_object_keys_are_quoted(self):
        self.check({'new': 1}, '{"new": 1}')

    def test_identifiers_starting_with_reserved_words(self):
        # `newbie` should not be quoted.
        self.check({'newbie': 1}, '{newbie: 1}')

    def test_non_string_keys(self):
        self.assertEqual(
            json5.dumps({False: 'a', 1: 'b', 2.0: 'c', None: 'd'}),
            '{"false": "a", "1": "b", "2.0": "c", "null": "d"}',
        )

    def test_quote_keys(self):
        self.assertEqual(
            json5.dumps({'foo': 1}, quote_keys=True), '{"foo": 1}'
        )

    def test_strings_containing_backslashes_and_quotes(self):
        # Understanding how things are escaped in test of JSON5 strings
        # can be tricky.

        # Normal Python escaping means that the following asserts are true:
        self.assertEqual('\\z', '\\z')
        self.assertEqual('\\z', r'\z')
        self.assertEqual('\\z', r'\z')

        # But, in Python, escaping quotes in a raw string is tricky, because
        # the escape is left in the output. The results of this are:

        # (1) You cannot use a raw string to match a value ending in a
        # an odd number of backslashes: the first N-1 backslashes would
        # be matched by the same number of backslashes in the raw string,
        # leaving a single backslash followed by a quote. The quote
        # would then be considered escaped, leaving the string unterminated.
        # Ending in an even number of backslashes is fine:
        self.assertEqual(len(r'\\'), 2)
        self.assertEqual(r'\\', '\\\\')

        # (2) You cannot use a raw string to represent a value that contains
        # the same kind of quote you're using to enclose the string, unless the
        # value actually contains an odd number of backslashes immediately
        # preceding the quote:
        self.assertEqual(len(r'\''), 2)
        self.assertEqual(r'\'', "\\'")
        self.assertEqual(r'\'', "\\'")
        self.assertEqual(r'\'', r'\'')

        # Now, in JSON5, if the value doesn't contain backslashes, you can
        # use normal quoting as you would in Python, but you can't use
        # raw strings, since the raw strings would require the values to
        # have backslashes in them:
        self.check("'single'", '"\'single\'"')
        self.check("'single'", '"\'single\'"')

        # In order to represent a backslash in the value you also need to
        # escape it in the JSON string: a string containing a single backslash
        # is represented by "\\". So, in order to match that single backslash
        # via non-raw strings in Python source code, you need to (3) double the
        # backslashes (for JSON5) and then double them again, for python source
        # code. I.e., you need *4* backslashes in the source code. In many
        # cases you can also use single-quoted raw strings (where you have
        # to (4) double the number of quotes in the output), but in this
        # particular example, you cannot use single-quoted raw strings,
        # due to (1).
        self.check('\\', '"\\\\"')
        self.check('\\', '"\\\\"')

        # You cannot use a double-quoted raw string to represent
        # double-quoted JSON5 strings, since the output needs to start with a
        # double quote, and you can't represent that in a raw double-quoted
        # string due to (2).

        # Here you see the doubling of backslashes in single-quoted
        # raw output strings, and the quadrupling in a non-raw string.
        self.check(r'\z', r'"\\z"')
        self.check(r'\\z', r'"\\\\z"')
        self.check(r'\\\z', r'"\\\\\\z"')
        self.check(r'\z', '"\\\\z"')

        self.check('"', '"\\""')
        self.check('"', '"\\""')

        # Here it's okay to use a raw string for output since the output
        # needs to have a single backslash and doesn't end in a single quote.
        self.check('"', r'"\""')

        # Here you cannot use raw strings for the output as the output
        # would need to have only two backslashes in it.
        self.check(r'\'', '"\\\\\'"')
        self.check(r'\'', '"\\\\\'"')

    def test_string_escape_sequences(self):
        # self.check(r'\'', '"\\\\\'"')
        self.check("'\\'", '"\'\\\\\'"')
        self.check(
            '\u2028\u2029\b\t\f\n\r\v\\\0',
            r'"\u2028\u2029\b\t\f\n\r\v\\\0"',
        )

    def test_string_quote_styles(self):
        def checkp(**kwargs):
            return lambda obj, s: self.assertEqual(
                s, json5.dumps(obj, **kwargs)
            )

        sq = "'"
        dq = '"'

        neither = 'a b c'
        single_neither = sq + neither + sq
        double_neither = dq + neither + dq

        single = "a 'b' c"
        single_single = sq + r'a \'b\' c' + sq
        double_single = dq + single + dq

        double = 'a "b" c'
        single_double = sq + double + sq
        double_double = dq + r'a \"b\" c' + dq

        both = 'a \'b\' "c" d'
        single_both = sq + r'a \'b\' "c" d' + sq
        double_both = dq + r"a 'b' \"c\" d" + dq

        reverse = 'a "b" \'c\' d'
        single_reverse = sq + r'a "b" \'c\' d' + sq
        double_reverse = dq + r"a \"b\" 'c' d" + dq

        more_single = "a 'b' 'c' \"d\" e"
        single_more_single = sq + r'a \'b\' \'c\' "d" e' + sq
        double_more_single = dq + r"a 'b' 'c' \"d\" e" + dq

        more_double = 'a "b" "c" \'d\' e'
        single_more_double = sq + r'a "b" "c" \'d\' e' + sq
        double_more_double = dq + r"a \"b\" \"c\" 'd' e" + dq

        more_single_double_first = "a \"b\" 'c' 'd' e"
        single_more_single_double_first = sq + r'a "b" \'c\' \'d\' e' + sq
        double_more_single_double_first = dq + r"a \"b\" 'c' 'd' e" + dq

        more_double_single_first = 'a \'b\' "c" "d" e'
        single_more_double_single_first = sq + r'a \'b\' "c" "d" e' + sq
        double_more_double_single_first = dq + r"a 'b' \"c\" \"d\" e" + dq

        # Default settings (should be ALWAYS_DOUBLE)
        c = checkp()
        c(neither, double_neither)
        c(single, double_single)
        c(double, double_double)
        c(both, double_both)
        c(reverse, double_reverse)
        c(more_single, double_more_single)
        c(more_double, double_more_double)
        c(more_single_double_first, double_more_single_double_first)
        c(more_double_single_first, double_more_double_single_first)

        c = checkp(quote_style=json5.QuoteStyle.ALWAYS_DOUBLE)
        c(neither, double_neither)
        c(single, double_single)
        c(double, double_double)
        c(both, double_both)
        c(reverse, double_reverse)
        c(more_single, double_more_single)
        c(more_double, double_more_double)
        c(more_single_double_first, double_more_single_double_first)
        c(more_double_single_first, double_more_double_single_first)

        c = checkp(quote_style=json5.QuoteStyle.ALWAYS_SINGLE)
        c(neither, single_neither)
        c(single, single_single)
        c(double, single_double)
        c(both, single_both)
        c(reverse, single_reverse)
        c(more_single, single_more_single)
        c(more_double, single_more_double)
        c(more_single_double_first, single_more_single_double_first)
        c(more_double_single_first, single_more_double_single_first)

        c = checkp(quote_style=json5.QuoteStyle.PREFER_DOUBLE)
        c(neither, double_neither)
        c(single, double_single)
        c(double, single_double)
        c(both, double_both)
        c(reverse, double_reverse)
        c(more_single, double_more_single)
        c(more_double, single_more_double)
        c(more_single_double_first, double_more_single_double_first)
        c(more_double_single_first, single_more_double_single_first)

        c = checkp(quote_style=json5.QuoteStyle.PREFER_SINGLE)
        c(neither, single_neither)
        c(single, double_single)
        c(double, single_double)
        c(both, single_both)
        c(reverse, single_reverse)
        c(more_single, double_more_single)
        c(more_double, single_more_double)
        c(more_single_double_first, double_more_single_double_first)
        c(more_double_single_first, single_more_double_single_first)

    def test_skip_keys(self):
        od = OrderedDict()
        od[(1, 2)] = 2
        self.assertRaises(TypeError, json5.dumps, od)
        self.assertEqual(json5.dumps(od, skipkeys=True), '{}')

        od['foo'] = 1
        self.assertEqual(json5.dumps(od, skipkeys=True), '{foo: 1}')

        # Also test that having an invalid key as the last element
        # doesn't incorrectly add a trailing comma (see
        # https://github.com/dpranke/pyjson5/issues/33).
        od = OrderedDict()
        od['foo'] = 1
        od[(1, 2)] = 2
        self.assertEqual(json5.dumps(od, skipkeys=True), '{foo: 1}')

    def test_sort_keys(self):
        od = OrderedDict()
        od['foo'] = 1
        od['bar'] = 2
        self.assertEqual(json5.dumps(od, sort_keys=True), '{bar: 2, foo: 1}')

    def test_trailing_commas(self):
        # By default, multi-line dicts and lists should have trailing
        # commas after their last items.
        self.assertEqual(json5.dumps({'foo': 1}, indent=2), '{\n  foo: 1,\n}')
        self.assertEqual(json5.dumps([1], indent=2), '[\n  1,\n]')

        self.assertEqual(
            json5.dumps({'foo': 1}, indent=2, trailing_commas=False),
            '{\n  foo: 1\n}',
        )
        self.assertEqual(
            json5.dumps([1], indent=2, trailing_commas=False), '[\n  1\n]'
        )

    def test_supplemental_unicode(self):
        self.check(chr(0x10000), '"\\ud800\\udc00"')

    def test_empty_key(self):
        self.assertEqual(json5.dumps({'': 'value'}), '{"": "value"}')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
