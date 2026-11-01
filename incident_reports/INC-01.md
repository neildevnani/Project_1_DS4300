# INC-01: Sorted list point lookups grow with n instead of log(n)


## Summary

Two or three sentences: what was slow, how much slower, which index and operation, and what fixed it.

## Detection

E2 (`code_version f6f773e`) showed the problem: comparisons per lookup grew
linearly with n (log-log slope k = 0.96 for hits and misses) instead of
following log2(n). At n = 114,000, lookups took about 3 ms each, versus under
1 µs for `ref_bisect`, which uses the same sorted layout.

## Expected vs. observed

**Expected:** a sorted list supports binary search, so a point lookup should
cost $O(\log n)$: about $\log_2 n$ comparisons, which is ~10 at n = 1,000 and
~17 at n = 114,000. Hits and misses should cost about the same.

**Observed** (E2, `code_version f6f773e`, medians across 5 reps): comparisons
per hit grew from 510 at n = 1,000 to 46,119 at n = 114,000, about 2,700× the
theoretical ~17. Misses grew from 1,000 to 89,741. The fitted log-log slope
was k = 0.96 for both hits and misses, indicating $O(n)$ growth rather than
$O(\log n)$. Misses examined every distinct key and hits about half as many,
the pattern of a linear scan from the start of the list. At full size, a hit
took about 3,058 µs, versus 0.70 µs for `ref_bisect`.

## Evidence

## Evidence

All rows below are from E2 (`E2_point_track_id`, session `a2ac476ea8ec`,
`code_version f6f773e`).

![E2 comparisons per lookup vs n](inc01_e2_comparisons.png)

*Figure 1: comparisons per lookup for `sorted_list` hits and misses on log-log
axes, against the $\log_2 n$ theory line. Both series are parallel lines with
slope k = 0.96, far above the theory line, confirming linear growth.*

![E2 time per lookup vs n, sorted_list vs ref_bisect](inc01_e2_time_vs_bisect.png)

*Figure 2: time per point hit for `sorted_list` and `ref_bisect`. Both store keys
in sorted order, but `sorted_list` grows with n while `ref_bisect` stays nearly
flat, reaching a ~4,400× gap at n = 114,000.*

The comparison counters are deterministic, so they rule out noise or hardware as
the cause. The CORE suite showed identical `sorted_list` counts on all four team
machines (45,613,624 comparisons per 1,000 hits at n = 114,000). Other
`sorted_list` operations behaved as expected: build averaged about 15
comparisons per insert, consistent with binary search, which isolates the bug to
`search`.

## Root cause

**File:** `indexes/sorted_list.py`, **function:** `search`, **lines 57–63.**

`search` walks the key list from the start (line 57), comparing each key to the
target until it finds a match (line 59) or passes where the key would be
(line 62). That is a linear scan, costing O(n) comparisons per lookup.

The list is kept sorted precisely so lookups can use binary search, and the
class already has a binary search helper, `_bisect_left` (lines 27–42), which
`insert` and `range_search` both use. `search` should call it as well,
narrowing to the key's position in about log2(n) comparisons.

Both approaches return the same values, since each finds the same key in the
same sorted list, so every correctness test passes. The scan just examines
many more keys: about half the list on a hit, and up to all of it on a miss.
The early `break` on line 63 doesn't change the big-O. This matches the
counters: hits examined about half of the distinct keys, and misses examined
all of them.

## Fix

The change you made, as a diff (`git diff <before>..<after> -- indexes/`), and the commit hash.

## Verification

Before/after comparison on the same workload and seeds (same experiment, two `code_version`s).
Confirm `make test` still passes.

## Impact on recommendations

Would this bug have changed which index you recommend for any feature (F1–F4)? How?

## Why the tests didn't catch it

What kind of test *would* catch a bug like this?
