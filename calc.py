#!/usr/bin/env python3
# a monadic parser
from typing import Any, Callable, Generator
from functools import wraps, update_wrapper


class ParserError(Exception):
    pass


class Parser:
    def __init__(self, func=None):
        self.func = func
        if callable(func):
            update_wrapper(self, func)

    def parse(self, context: str) -> (Any, str):
        if self.func is None:
            return None, context
        return self.func(context)

    def __or__(self, other: "Parser") -> "Parser":
        @Parser
        def parse(context: str):
            try:
                return self.parse(context)
            except ParserError:
                return other.parse(context)
        return parse

    @classmethod
    def ret(cls, value):
        return cls(lambda c: (value, c))

    def bind(self, f: Callable[[Any], "Parser"]) -> "Parser":
        @Parser
        def bound(context):
            a, context = self.parse(context)
            return f(a).parse(context)
        return bound


def pick() -> "Parser":
    @Parser
    def parser(context):
        if len(context) == 0:
            raise ParserError("unexpected EOF")
        return context[0], context
    return parser


def pop() -> "Parser":
    @Parser
    def parser(context):
        if len(context) == 0:
            raise ParserError("unexpected EOF")
        return context[0], context[1:]
    return parser


def reduce(g) -> Parser:
    try:
        m_a = next(g)
    except StopIteration as err:
        return err.value

    return m_a.bind(lambda a: reduce(g.partial_apply(a)))


def do(f: Callable[..., Generator[Parser, Any, Parser]]) -> Parser:
    @wraps(f)
    @Parser
    def parse(context: str):
        class _Generator:
            class _Null:
                pass

            def __init__(self, generator):
                self._generator = generator
                self._x = _Generator._Null

            def __next__(self):
                if self._x is not _Generator._Null:
                    x = self._x
                    self._x = _Generator._Null
                    return self._generator.send(x)
                return next(self._generator)

            def __iter__(self):
                return self

            def send(self, x):
                return self._generator.send(x)

            def partial_apply(self, x):
                self._x = x
                return self

            def __repr__(self):
                return f"Generator {self._generator.__repr__()}"
        return reduce(_Generator(f())).parse(context)
    return parse


def sat(p: Callable[[str], bool]):
    @do
    def parser():
        ch = yield pop()
        if p(ch):
            return Parser.ret(ch)
        raise ParserError(f"unexpected {ch}")
    return parser


def char(ch):
    return sat(lambda x: x == ch)


def string(s: str):
    @do
    def parser():
        for ch in s:
            yield char(ch)
        return Parser.ret(s)
    return parser


def many(p) -> Parser:
    # if you accept recursion
    # return many1(p) | Parser.ret([])

    # or you prefer a loop version
    @do
    def parse_many():
        result = []
        while True:
            x = yield p | Parser.ret(ParserError)
            if x is ParserError:
                return Parser.ret(result)
            result.append(x)
    return parse_many


def many1(p) -> Parser:
    @do
    def m():
        x = yield p
        xs = yield many(p)
        return Parser.ret([x] + xs)
    return m


@Parser
def space(context):
    return many(sat(lambda x: x in " \t\n\r")).parse(context)


def token(p):
    @do
    def m():
        a = yield p
        yield space
        return Parser.ret(a)
    return m


def symb(s):
    return token(string(s))


def operator(p_op, p_n1, p_n2):
    @do
    def result():
        n1 = yield p_n1
        op = yield p_op
        n2 = yield p_n2
        return Parser.ret(op(n1, n2))
    return result


@Parser
def expr(context):
    return (addop(term, expr) | term).parse(context)


@Parser
def term(context):
    return (mulop(factor, term) | factor).parse(context)


@Parser
def factor(context):
    @do
    def parse_parenthesis():
        yield symb("(")
        n = yield expr
        yield symb(")")
        return Parser.ret(n)
    return (digits | parse_parenthesis).parse(context)


@Parser
def digits(context):
    one = sat(lambda z: z in "1234567890.")
    x, context = token(many1(one)).parse(context)
    return eval("".join(x)), context


def addop(pn1, pn2):
    @do
    def plus():
        yield symb("+")
        return Parser.ret(lambda a, b: a + b)

    @do
    def minus():
        yield symb("-")
        return Parser.ret(lambda a, b: a - b)
    return operator(plus | minus, pn1, pn2)


def mulop(pn1, pn2):
    @do
    def times():
        yield symb("*")
        return Parser.ret(lambda a, b: a * b)

    @do
    def divide():
        yield symb("/")
        return Parser.ret(lambda a, b: a / b)
    return operator(times | divide, pn1, pn2)


def main():
    while True:
        line = input("> ")
        if line == "":
            break
        try:
            value, ctx = expr.parse(line)
            if ctx != "":
                print("Extra input at: ", ctx)
            else:
                print(value)
        except Exception as e:
            print("exception:", e)


if __name__ == '__main__':
    main()
