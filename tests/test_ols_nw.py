"""report_book.ols_nw against a hand-computed example (to 1e-8).

y = [1, 2, 4, 3, 5, 6], x = [0, 1, 2, 3, 4, 5], X = [1, x], lags = 1 (Bartlett weight 1 - 1/2 = 0.5).
By hand: sum x = 15, sum x^2 = 55, sum y = 21, sum xy = 0+2+8+9+20+30 = 69, n = 6.
  slope = (6*69 - 15*21) / (6*55 - 15^2) = (414 - 315) / (330 - 225) = 99/105 = 33/35
  intercept = (21 - 15 * 33/35) / 6 = (735/35 - 495/35) / 6 = 240/210 = 8/7
  residuals u_i = y_i - 8/7 - 33/35 x_i, in 35ths: -5, -3, 34, -34, 3, 5 (sum 0)
  R^2 = 1 - SSR/SST, SSR = (25 + 9 + 1156 + 1156 + 9 + 25)/1225 = 2380/1225, SST = sum (y - 3.5)^2 = 17.5
Newey-West: S = sum_t u_t^2 x_t x_t' + 0.5 * sum_t u_t u_{t-1} (x_t x_{t-1}' + x_{t-1} x_t'),
cov = (X'X)^-1 S (X'X)^-1; the expected t-values below are computed from those exact fractions."""
from fractions import Fraction as F

import numpy as np

import report_book as R


def test_ols_nw_hand_example():
    y = np.array([1, 2, 4, 3, 5, 6], float)
    x = np.arange(6, dtype=float)
    X = np.column_stack([np.ones(6), x])
    b, t, r2 = R.ols_nw(y, X, lags=1)
    assert abs(b[0] - 8 / 7) < 1e-8 and abs(b[1] - 33 / 35) < 1e-8
    assert abs(r2 - (1 - (2380 / 1225) / 17.5)) < 1e-8
    # exact NW covariance with fractions
    u = [F(v, 35) for v in (-5, -3, 34, -34, 3, 5)]
    xs = [F(i) for i in range(6)]
    S = [[F(0), F(0)], [F(0), F(0)]]
    for i in range(6):
        v = (F(1), xs[i])
        for a in range(2):
            for c in range(2):
                S[a][c] += u[i] ** 2 * v[a] * v[c]
    for i in range(1, 6):
        v, w = (F(1), xs[i]), (F(1), xs[i - 1])
        for a in range(2):
            for c in range(2):
                S[a][c] += F(1, 2) * u[i] * u[i - 1] * (v[a] * w[c] + w[a] * v[c])
    det = F(6 * 55 - 15 * 15)
    inv = [[F(55) / det, F(-15) / det], [F(-15) / det, F(6) / det]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(2)) for j in range(2)] for i in range(2)]
    cov = mul(mul(inv, S), inv)
    t_exact = [float(F(8, 7)) / float(cov[0][0]) ** 0.5, float(F(33, 35)) / float(cov[1][1]) ** 0.5]
    assert abs(t[0] - t_exact[0]) < 1e-8 and abs(t[1] - t_exact[1]) < 1e-8
