"""Synthetic keys and query workloads.  *** YOU IMPLEMENT THIS FILE. ***

Real data (Spotify) shows how the indexes behave on realistic keys.
Synthetic data lets you control one variable at a time: how many keys, what
order they arrive in, how many lookups hit vs miss, how wide a range is.

Rules for every function:

* Use ``rng = random.Random(seed)`` and draw all randomness from ``rng``, so
  the same seed always produces the same output (on any machine).
* Never modify the list you are given; return a new one.

``tests/test_synthetic.py`` checks each function against this spec. Run it
with ``make test``.
"""

from __future__ import annotations

import random
import string
from typing import Any, Optional, Sequence


def random_keys(n, length=8, alphabet=string.ascii_lowercase, seed=None):
    if n > len(alphabet) ** length:
        raise ValueError(f"cannot make {n} distinct keys of length {length}")
    rng = random.Random(seed)
    seen = set()
    keys = []
    while len(keys) < n:
        key = "".join(rng.choice(alphabet) for _ in range(length))
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def arrange(
    keys: Sequence[Any],
    order: str,
    seed: Optional[int] = None,
    swap_fraction: float = 0.05,
) -> list[Any]:
    """Return a new list holding the same keys in the requested order.

    order:
        "random"        shuffled
        "sorted"        ascending
        "reversed"      descending
        "nearly_sorted" ascending, then ``round(swap_fraction * len(keys))``
                        swaps of two randomly chosen positions

    Raise ``ValueError`` for any other ``order``.
    """
    rng = random.Random(seed)
    if order == "random":
        result = list(keys)
        rng.shuffle(result)
        return result
    if order == "sorted":
        return sorted(keys)
    if order == "reversed":
        return sorted(keys, reverse=True)
    if order == "nearly_sorted":
        result = sorted(keys)
        n_swaps = round(swap_fraction * len(keys))
        for _ in range(n_swaps):
            i = rng.randrange(len(result))
            j = rng.randrange(len(result))
            result[i], result[j] = result[j], result[i]
        return result
    raise ValueError(f"unknown order: {order!r}")


def point_queries(
    keys: Sequence[str],
    n_queries: int,
    hit_rate: float,
    seed: Optional[int] = None,
) -> list[str]:
    """Return ``n_queries`` lookup keys in random order.

    Exactly ``round(n_queries * hit_rate)`` of them are *hits*: chosen at
    random (repeats allowed) from ``keys``. The rest are *misses*: random
    strings that are guaranteed NOT to be in ``keys``, each the same length as
    a randomly chosen key from ``keys``.
    """
    rng = random.Random(seed)
    key_set = set(keys)
    n_hits = round(n_queries * hit_rate)

    queries = [rng.choice(keys) for _ in range(n_hits)]

    while len(queries) < n_queries:
        length = len(rng.choice(keys))
        candidate = "".join(rng.choice(string.ascii_letters) for _ in range(length))
        if candidate not in key_set:
            queries.append(candidate)

    rng.shuffle(queries)

    return queries


def range_queries(
    keys: Sequence[Any],
    n_queries: int,
    selectivity: float,
    seed: Optional[int] = None,
) -> list[tuple[Any, Any]]:
    """Return ``n_queries`` ranges ``(lo, hi)`` for ``index.range_search(lo, hi)``.

    Let ``d`` be the number of *distinct* keys and ``w = max(1, round(selectivity * d))``.
    Sort the distinct keys, pick a random starting position that leaves room
    for ``w`` keys, and use the key there as ``lo`` and the key ``w - 1``
    positions later as ``hi``. So exactly ``w`` distinct keys satisfy
    ``lo <= key <= hi``. Works for any comparable keys (strings or numbers).
    """
    rng = random.Random(seed)

    unique_sorted_keys = list(dict.fromkeys(sorted(keys))) # orders and removes duplicate keys

    d = len(unique_sorted_keys)
    w = max(1,round(selectivity * d))

    ranges = []

    for _ in range(n_queries):
            initial_index = rng.randint(0,d - w) # initial index initialzied randomly 
            lo = unique_sorted_keys[initial_index]  # low is key is initial index
            hi = unique_sorted_keys[initial_index + w - 1] # high is key of low key + (w - 1) indices
            ranges.append((lo,hi))

    return ranges



def prefix_queries(
    keys: Sequence[str],
    n_queries: int,
    prefix_length: int,
    seed: Optional[int] = None,
) -> list[str]:
    """Return ``n_queries`` prefixes for ``index.prefix_search(prefix)``.

    Each prefix is the first ``prefix_length`` characters of a randomly chosen
    key that is at least ``prefix_length`` characters long, so every prefix
    matches at least one key.
    """
    rng = random.Random(seed)
    new_keys = []   # keys that are longer than prefix length
    prefixes = []   # prefixes

    for key in keys:    # loop through keys to find keys long enough
        if len(key) >= prefix_length:
            new_keys.append(key)

    if not new_keys:
        raise ValueError("Prefix length is longer than all keys")

    for _ in range(n_queries):   # appends a random key that is at least prefix length
        prefixes.append(rng.choice(new_keys)[:prefix_length])

    return prefixes