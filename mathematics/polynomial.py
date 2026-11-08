"""A tiny exact polynomial type: just enough algebra for school answers, with no SymPy.

Coefficients are Fractions and terms are kept fully expanded, so two expressions are equal exactly
when their polynomials are equal ("2x+2" == "2(x+1)"). Dividing by an expression that contains a
letter is not supported (it would not be a polynomial) and raises ``ValueError``.

Pure Python on purpose: SymPy cannot be loaded by the web (WebAssembly) build of the game.
"""
from fractions import Fraction


class Polynomial:
    __slots__ = ("terms",)

    def __init__(self, terms=None):
        # {monomial: coefficient}; a monomial is a sorted tuple of (letter, power), () = constant.
        self.terms = {m: Fraction(c) for m, c in (terms or {}).items() if c != 0}

    # ------------------------------------------------------------------ construction
    @classmethod
    def constant(cls, value):
        return cls({(): Fraction(value)})

    @classmethod
    def variable(cls, name):
        return cls({((name, 1),): Fraction(1)})

    @staticmethod
    def _lift(other):
        if isinstance(other, Polynomial):
            return other
        if isinstance(other, (int, Fraction)):
            return Polynomial.constant(other)
        return NotImplemented

    # ------------------------------------------------------------------ queries
    @property
    def is_constant(self):
        return all(m == () for m in self.terms)

    @property
    def value(self):
        """The number this polynomial equals; ``ValueError`` if it still contains a letter."""
        if not self.is_constant:
            raise ValueError("expression still contains a letter")
        return self.terms.get((), Fraction(0))

    @property
    def is_Integer(self):  # noqa: N802  (same spelling as SymPy, used by the parser)
        return self.is_constant and self.value.denominator == 1

    def __int__(self):
        return int(self.value)

    def __eq__(self, other):
        other = self._lift(other)
        if other is NotImplemented:
            return NotImplemented
        return self.terms == other.terms

    def __hash__(self):
        return hash(frozenset(self.terms.items()))

    # ------------------------------------------------------------------ arithmetic
    def __neg__(self):
        return Polynomial({m: -c for m, c in self.terms.items()})

    def __add__(self, other):
        other = self._lift(other)
        if other is NotImplemented:
            return NotImplemented
        terms = dict(self.terms)
        for m, c in other.terms.items():
            terms[m] = terms.get(m, 0) + c
        return Polynomial(terms)

    __radd__ = __add__

    def __sub__(self, other):
        other = self._lift(other)
        return NotImplemented if other is NotImplemented else self + (-other)

    def __rsub__(self, other):
        other = self._lift(other)
        return NotImplemented if other is NotImplemented else other + (-self)

    def __mul__(self, other):
        other = self._lift(other)
        if other is NotImplemented:
            return NotImplemented
        terms = {}
        for m1, c1 in self.terms.items():
            for m2, c2 in other.terms.items():
                powers = dict(m1)
                for name, power in m2:
                    powers[name] = powers.get(name, 0) + power
                m = tuple(sorted(powers.items()))
                terms[m] = terms.get(m, 0) + c1 * c2
        return Polynomial(terms)

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = self._lift(other)
        if other is NotImplemented:
            return NotImplemented
        if not other.is_constant:
            raise ValueError("can only divide by a number")
        if other.value == 0:
            raise ZeroDivisionError("division by zero")
        return self * Polynomial.constant(1 / other.value)

    def __rtruediv__(self, other):
        other = self._lift(other)
        return NotImplemented if other is NotImplemented else other / self

    def __pow__(self, exponent):
        exponent = self._lift(exponent)
        if exponent is NotImplemented:
            return NotImplemented
        if not exponent.is_Integer:
            raise ValueError("only whole-number powers are supported")
        n = int(exponent)
        if n < 0:
            if not self.is_constant:
                raise ValueError("negative powers of letters are not supported")
            if self.value == 0:
                raise ZeroDivisionError("division by zero")
            return Polynomial.constant(self.value ** n)
        result = Polynomial.constant(1)
        for _ in range(n):
            result = result * self
        return result

    def subs(self, name, number):
        """Replace a letter with a number."""
        number = Fraction(number)
        result = Polynomial()
        for m, c in self.terms.items():
            coefficient, rest = c, []
            for letter, power in m:
                if letter == name:
                    coefficient *= number ** power
                else:
                    rest.append((letter, power))
            result = result + Polynomial({tuple(rest): coefficient})
        return result

    def __repr__(self):
        if not self.terms:
            return "0"
        parts = []
        for m, c in sorted(self.terms.items()):
            letters = "*".join(name if p == 1 else f"{name}^{p}" for name, p in m)
            parts.append(f"{c}*{letters}" if letters and c != 1 else letters or str(c))
        return " + ".join(parts)
