from fractions import Fraction

import sympy as s


x, y, z = s.symbols("x y z")
a = (1 + x * y) ** 3 * z + y**2 * (1 + x * y) * (4 + 3 * x * y)
b = y + 3 * x * (1 + x * y) ** 2 * z + 3 * x * y**2 * (4 + 3 * x * y)
c = 2 * x - 3 * x**2 * y - x**3 * z
mapping = s.Matrix([a, b, c])

determinant = s.factor(mapping.jacobian([x, y, z]).det())
assert determinant == -2, determinant

points = [
    (0, 0, -s.Rational(1, 4)),
    (1, -s.Rational(3, 2), s.Rational(13, 2)),
    (-1, s.Rational(3, 2), s.Rational(13, 2)),
]
images = []
for point in points:
    values = tuple(s.simplify(value.subs(dict(zip((x, y, z), point)))) for value in mapping)
    images.append(values)

assert len(set(points)) == 3
assert images == [(-s.Rational(1, 4), 0, 0)] * 3, images
print("PASS determinant=-2; three distinct rational points map to (-1/4, 0, 0)")
