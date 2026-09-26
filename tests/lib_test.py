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


class TestStrictSwitchBehavior(unittest.TestCase):
    """Pins down what strict=True/False actually change today.

    Current behavior (verified against the implementation): the `strict`
    flag only controls whether literal line terminators (\\n, \\r) may
    appear unescaped inside strings. It has no effect on unterminated
    strings, single-quoted strings, or trailing commas.
    """

    maxDiff = None

    def test_unterminated_string_fails_in_both_modes(self):
        # An unterminated string is a hard syntax error regardless of
        # strict; the message and position are identical in both modes.
        for strict in (True, False):
            with self.assertRaises(ValueError) as ctx:
                json5.loads('"abc', strict=strict)
            self.assertEqual(
                '<string>:1 Unexpected end of input at column 5',
                str(ctx.exception),
            )

        # Same for an unterminated single-quoted string.
        for strict in (True, False):
            with self.assertRaises(ValueError) as ctx:
                json5.loads("'abc", strict=strict)
            self.assertEqual(
                '<string>:1 Unexpected end of input at column 5',
                str(ctx.exception),
            )

        # strict=False does not rescue a string that runs into end of
        # input, even across a newline.
        with self.assertRaises(ValueError) as ctx:
            json5.loads('"a\nb', strict=False)
        self.assertEqual(
            '<string>:2 Unexpected end of input at column 2',
            str(ctx.exception),
        )

    def test_single_quoted_strings_allowed_in_both_modes(self):
        # Single quotes are legal JSON5 in both modes; strict does not
        # gate them.
        self.assertEqual(json5.loads("'abc'", strict=True), 'abc')
        self.assertEqual(json5.loads("'abc'", strict=False), 'abc')

    def test_trailing_commas_allowed_in_both_modes(self):
        # Trailing commas in arrays and objects are legal JSON5 in both
        # modes; strict does not gate them.
        for strict in (True, False):
            self.assertEqual(json5.loads('[1, 2,]', strict=strict), [1, 2])
            self.assertEqual(
                json5.loads('{a: 1,}', strict=strict), {'a': 1}
            )

    def test_literal_newline_in_string_is_what_strict_gates(self):
        # This is the one thing strict actually changes: a literal
        # newline inside a string is rejected with strict=True and
        # accepted with strict=False.
        s = '"a\nb"'
        with self.assertRaises(ValueError) as ctx:
            json5.loads(s, strict=True)
        self.assertEqual(
            '<string>:1 Unexpected "\n" at column 3', str(ctx.exception)
        )
        self.assertEqual(json5.loads(s, strict=False), 'a\nb')

        # Same for a carriage return.
        self.assertEqual(json5.loads('"a\rb"', strict=False), 'a\rb')

    def test_other_control_characters_ignore_strict(self):
        # DISCREPANCY (implementation looks wrong, expectation would be
        # the opposite): one would expect strict=True to reject all
        # unescaped control characters (U+0000-U+001F) in strings, per
        # the JSON5 spec. In fact raw \\t and \\x01 are accepted in BOTH
        # modes; only line terminators are gated by strict. These
        # assertions pin the current (permissive) behavior.
        self.assertEqual(json5.loads('"a\tb"', strict=True), 'a\tb')
        self.assertEqual(json5.loads('"\x01"', strict=True), '\x01')

        # Conversely, a raw U+2028 (line separator) is REJECTED in both
        # modes, even though strict=False accepts \\n and \\r. The
        # grammar's non-strict escape hatch only covers U+0000-U+001F,
        # so U+2028/U+2029 can never appear literally in a string.
        for strict in (True, False):
            with self.assertRaises(ValueError):
                json5.loads('"\u2028"', strict=strict)


class TestAllowDuplicateKeysBehavior(unittest.TestCase):
    """Pins down allow_duplicate_keys=False on nested objects.

    Current behavior: nested duplicates ARE caught, but only the first
    duplicate encountered (depth-first) is reported, and the error
    carries no position information at all.
    """

    maxDiff = None

    def test_error_message_has_no_position(self):
        # DISCREPANCY (implementation is at fault): every other parse
        # error includes '<string>:LINE ... at column COL', but the
        # duplicate-key error is raised after parsing, during AST
        # conversion, so all location information is lost. For a
        # hundreds-of-lines config file the user gets no hint where the
        # duplicate is. Assertion pins the current bare message.
        with self.assertRaises(ValueError) as ctx:
            json5.loads('{a: 1, a: 2}', allow_duplicate_keys=False)
        self.assertEqual(
            'Duplicate key "a" found in object', str(ctx.exception)
        )

    def test_nested_duplicates_are_caught(self):
        # Duplicates inside nested objects are rejected, not just
        # top-level ones.
        with self.assertRaises(ValueError) as ctx:
            json5.loads(
                '{x: {b: 1, b: 2}, y: 3}', allow_duplicate_keys=False
            )
        self.assertEqual(
            'Duplicate key "b" found in object', str(ctx.exception)
        )

        # Duplicates inside objects nested in arrays are caught, too.
        with self.assertRaises(ValueError):
            json5.loads(
                '[{k: 1, k: 2}, {k: 3, k: 4}]', allow_duplicate_keys=False
            )

    def test_only_the_first_duplicate_is_reported(self):
        # The check raises on the first duplicate it walks into and
        # aborts; it does not collect or report the remaining ones.
        # Two duplicates in the same object: only "a" is reported.
        with self.assertRaises(ValueError) as ctx:
            json5.loads(
                '{a: 1, a: 2, b: 3, b: 4}', allow_duplicate_keys=False
            )
        self.assertEqual(
            'Duplicate key "a" found in object', str(ctx.exception)
        )

        # Duplicates in two sibling nested objects: a single error for
        # the first object walked, the second object's duplicate is
        # never reported.
        with self.assertRaises(ValueError) as ctx:
            json5.loads(
                '{p: {k: 1, k: 2}, q: {k: 3, k: 4}}',
                allow_duplicate_keys=False,
            )
        self.assertEqual(
            'Duplicate key "k" found in object', str(ctx.exception)
        )

    def test_parse_position_on_duplicate_key_error(self):
        # DISCREPANCY (implementation is at fault): parse()'s docstring
        # says that on error, position is "the zero-based farthest
        # offset into the string where the parser hit an error". For a
        # duplicate-key failure there is no parse error, so position is
        # instead one past the end of the successfully parsed value
        # (12 == len('{a: 1, a: 2}')), exactly as if the parse had
        # succeeded. It does NOT point at the duplicate key (the second
        # "a" is at offset 7), so callers cannot use it to locate the
        # problem.
        val, err, pos = json5.parse(
            '{a: 1, a: 2}', allow_duplicate_keys=False
        )
        self.assertIsNone(val)
        self.assertEqual('Duplicate key "a" found in object', err)
        self.assertEqual(12, pos)

        # Same story for a nested duplicate: pos is one past the '}',
        # not near the inner duplicate at all.
        val, err, pos = json5.parse(
            '{x: {b: 1, b: 2}}', allow_duplicate_keys=False
        )
        self.assertIsNone(val)
        self.assertEqual('Duplicate key "b" found in object', err)
        self.assertEqual(17, pos)

        # consume_trailing=False does not change this: pos is still one
        # past the value, and trailing junk is never even looked at.
        val, err, pos = json5.parse(
            '{a: 1, a: 2} junk',
            allow_duplicate_keys=False,
            consume_trailing=False,
        )
        self.assertIsNone(val)
        self.assertEqual('Duplicate key "a" found in object', err)
        self.assertEqual(12, pos)


class TestConsumeTrailingBehavior(unittest.TestCase):
    """Pins down where parsing resumes with consume_trailing=False.

    Current behavior: on success, position is the zero-based index one
    past the last character of the value, i.e. the index at which the
    next parse() call should start. Whitespace and comments between
    values are skipped by the *next* call, not the current one.
    """

    maxDiff = None

    def test_position_is_the_resume_index(self):
        s = '[1, 2] [3]'
        val, err, pos = json5.parse(s, consume_trailing=False)
        self.assertEqual([1, 2], val)
        self.assertIsNone(err)
        # pos points at the space right after ']'; the remainder of the
        # string is readable from there.
        self.assertEqual(6, pos)
        self.assertEqual(' [3]', s[pos:])

        # Resuming with start=pos parses the next value; leading
        # whitespace is skipped by the next call itself.
        val, err, pos = json5.parse(s, consume_trailing=False, start=pos)
        self.assertEqual([3], val)
        self.assertIsNone(err)
        self.assertEqual(10, pos)
        self.assertEqual('', s[pos:])

    def test_comments_between_values_are_skipped_by_next_call(self):
        s = '[1,2]// c\n[3]'
        val, err, pos = json5.parse(s, consume_trailing=False)
        self.assertEqual([1, 2], val)
        self.assertIsNone(err)
        # pos is right after ']', before the comment.
        self.assertEqual(5, pos)
        self.assertEqual('// c\n[3]', s[pos:])

        # The comment is treated as whitespace by the next call.
        val, err, pos = json5.parse(s, consume_trailing=False, start=pos)
        self.assertEqual([3], val)
        self.assertIsNone(err)
        self.assertEqual(13, pos)

    def test_trailing_whitespace_is_not_consumed(self):
        # With consume_trailing=False, pos stops right after the value
        # even if only whitespace follows.
        val, err, pos = json5.parse('{a:1}   ', consume_trailing=False)
        self.assertEqual({'a': 1}, val)
        self.assertIsNone(err)
        self.assertEqual(5, pos)

    def test_incomplete_value_still_fails(self):
        # consume_trailing=False does not rescue an unterminated value:
        # '{a: 1, a: 2' has no valid prefix, so this is an error and
        # pos is the error offset (end of input), not a resume point.
        val, err, pos = json5.parse('{a: 1, a: 2', consume_trailing=False)
        self.assertIsNone(val)
        self.assertEqual(
            '<string>:1 Unexpected end of input at column 12', err
        )
        self.assertEqual(11, pos)

    def test_error_position_vs_success_position(self):
        # Pins down the two different meanings position has, which is
        # the source of the "sometimes at the value end, sometimes at
        # the error" confusion:
        #   - success: pos is one past the value (a resume index);
        #   - syntax error: pos is the zero-based offset of the
        #     offending character (errpos);
        #   - duplicate-key error: pos is one past the value, as if the
        #     parse had succeeded (see TestAllowDuplicateKeysBehavior).
        val, err, pos = json5.parse('4 x')
        self.assertIsNone(val)
        self.assertEqual('<string>:1 Unexpected "x" at column 3', err)
        self.assertEqual(2, pos)  # offset of the 'x' itself

        val, err, pos = json5.parse('4 x', consume_trailing=False)
        self.assertEqual(4, val)
        self.assertIsNone(err)
        self.assertEqual(1, pos)  # one past the '4'

    def test_null_parses_to_none_with_no_error(self):
        # GOTCHA (documentation is at fault): with consume_trailing=False
        # a keyword only needs to match a prefix of the remaining text,
        # so 'nullx' parses as `null` leaving 'x' unread. The returned
        # value is None with err=None, so callers must check `err`, not
        # the value, to detect failure -- the `if v:` loop in parse()'s
        # own docstring would silently drop null/false/0 values.
        val, err, pos = json5.parse('nullx', consume_trailing=False)
        self.assertIsNone(val)
        self.assertIsNone(err)
        self.assertEqual(4, pos)

        val, err, pos = json5.parse('truely', consume_trailing=False)
        self.assertEqual(True, val)
        self.assertIsNone(err)
        self.assertEqual(4, pos)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
