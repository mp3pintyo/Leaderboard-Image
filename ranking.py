"""Bradley-Terry rangsor bootstrap konfidenciaintervallummal.

Az online ELO a szavazatok sorrendjétől és a K-faktortól függ. A Bradley-Terry modell
(az LMArena / FastChat, Artificial Analysis és GenAI-Arena módszere) az összes szavazatra
egyszerre illeszt maximum likelihood becslést, így a sorrend nem számít.

- A döntetlen (és a "mindkettő rossz") fél győzelemnek számít mindkét félnek.
- Minden modell kap BT_PRIOR_GAMES virtuális döntetlent egy 1500-as "átlagos" ellenféllel szemben:
  ez a kevés adatú modelleket az átlag felé húzza, és garantálja, hogy a becslés mindig létezik.
- A pontszám ELO-skálán van: 1500 + 400 * log10(erősség).
- A 95%-os konfidenciaintervallum a szavazatok bootstrap újramintavételezéséből jön.
"""
import math

import numpy as np

ELO_SCALE = 400 / math.log(10)
BASE_RATING = 1500.0


def fit_bradley_terry(wins, prior_games=1.0, max_iter=100, tol=1e-10):
    """Newton-módszerrel illesztett Bradley-Terry modell.

    :param wins: n×n mátrix, wins[i, j] = i pontjai j ellen (győzelem 1, döntetlen 0.5)
    :return: log-erősségek (theta) numpy tömbként; a 0 az 1500-as horgonynak felel meg
    """
    n = wins.shape[0]
    games = wins + wins.T
    theta = np.zeros(n)
    for _ in range(max_iter):
        prob = 1.0 / (1.0 + np.exp(theta[None, :] - theta[:, None]))  # prob[i, j] = P(i legyőzi j-t)
        anchor = 1.0 / (1.0 + np.exp(-theta))                          # P(i legyőzi a horgonyt)
        grad = (wins - games * prob).sum(axis=1) + prior_games * (0.5 - anchor)
        weight = games * prob * (1.0 - prob)
        hessian = weight.copy()
        np.fill_diagonal(hessian, -(weight.sum(axis=1) + prior_games * anchor * (1.0 - anchor)))
        try:
            step = np.linalg.solve(hessian, -grad)
        except np.linalg.LinAlgError:
            # Prior nélkül a skála eltolásra invariáns (szinguláris Hesse-mátrix)
            step = np.linalg.lstsq(hessian, -grad, rcond=None)[0]
        # Csillapítás: szélsőséges adatoknál se lőjön túl az első lépések valamelyike
        largest = np.abs(step).max(initial=0.0)
        if largest > 2.0:
            step *= 2.0 / largest
        theta += step
        if largest < tol:
            break
    return theta


def to_rating(theta):
    return BASE_RATING + ELO_SCALE * np.asarray(theta)


def build_win_matrix(pairs, n):
    """pairs: (i, j, score_i) hármasok – score_i: 1 ha i nyert, 0.5 döntetlennél."""
    wins = np.zeros((n, n))
    if len(pairs):
        arr = np.asarray(pairs, dtype=float)
        i, j, s = arr[:, 0].astype(int), arr[:, 1].astype(int), arr[:, 2]
        np.add.at(wins, (i, j), s)
        np.add.at(wins, (j, i), 1.0 - s)
    return wins


def compute_ratings(pairs, n, prior_games=1.0, bootstrap_rounds=100, seed=42):
    """Pontszám, 95%-os CI és bootstrap eloszlás.

    :param pairs: (i, j, score_i) hármasok listája
    :return: dict: rating (n), ci_lower (n), ci_upper (n)
    """
    wins = build_win_matrix(pairs, n)
    rating = to_rating(fit_bradley_terry(wins, prior_games))
    ci_lower = rating.copy()
    ci_upper = rating.copy()

    if bootstrap_rounds and len(pairs):
        arr = np.asarray(pairs, dtype=float)
        rng = np.random.default_rng(seed)
        samples = np.empty((bootstrap_rounds, n))
        for round_index in range(bootstrap_rounds):
            resampled = arr[rng.integers(0, len(arr), len(arr))]
            samples[round_index] = to_rating(fit_bradley_terry(build_win_matrix(resampled, n), prior_games))
        ci_lower, ci_upper = np.percentile(samples, [2.5, 97.5], axis=0)

    return {'rating': rating, 'ci_lower': ci_lower, 'ci_upper': ci_upper, 'wins': wins}


def rank_spread(ci_lower, ci_upper):
    """LMArena-szerű helyezés: legjobb = 1 + azok száma, akik statisztikailag biztosan jobbak;
    legrosszabb = azok száma, akiknek a CI-je átfed vagy jobb (önmagát is beleértve)."""
    lower = np.asarray(ci_lower)
    upper = np.asarray(ci_upper)
    best = 1 + (lower[None, :] > upper[:, None]).sum(axis=1)
    worst = (upper[None, :] >= lower[:, None]).sum(axis=1)
    return best.astype(int), np.maximum(worst, best).astype(int)


def wilson_interval(successes, total, z=1.96):
    """95%-os Wilson-intervallum egy arányra (pl. bal oldali győzelmi arány)."""
    if total <= 0:
        return None, None
    phat = successes / total
    denom = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denom
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denom
    return centre - margin, centre + margin
