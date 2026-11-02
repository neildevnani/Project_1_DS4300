# INC-03: B+ tree range and prefix queries scan the whole tree

## Summary
The B+ tree's `range_search`, and `prefix_search`, twhich base.py builds on top of, visited every node and examined all keys in the tree on every single query, no matter the size of the range. On the CORE suite on `vicente-mba`, a 1% tempo range query examined 45,653 keys instead of about 474, and ran about 26× slower than after the fix; a 3-letter prefix query ran 157 times slower. The fix replaced this recursive walk bnack over the whole tree with a singular descent to the starting leaf, then followed with a walk along the leaves next pointers that stops at the first key past hi.


## Detection


The CORE suite (Neil's run, `e9c1863`) first showed it: B+ tree range queries examined 45,653 keys per query, roughly 100× more than theory predicts for a 1% range. The E3 experiment (`f6f773e`) confirmed it: B+ tree comparisons were exactly 9,130,600 per 200 queries at every selectivity from 0.0001 to 0.25, while the sorted list's cost grew with the size of the range. A range-query cost that doesn't depend on the range size means the query is reading everything. E6 showed the same 9,130,600 at every B+ tree order from 3 to 512. Before the fix, the B+ tree did exactly as many comparisons on range queries as the hash table, which has no key order at all.

## Expected vs. observed

**Expected:** a B+ tree answers a range query in O(log n + k). It goes down the tree once (height 4, so 4 nodes and about 17 comparisons), then walks right along the leaves through only the k keys in the range. The tempo column has 45,653 distinct keys, so a 1% range covers about 456 keys: about 474 comparisons and about 25 nodes per query.

**Observed (before fix):** 45,653 comparisons and 2,197 nodes visited per query, which is every distinct key and every node in the tree. The cost was the same at every selectivity, so range search was O(n).

## Evidence

![E3 range cost before and after](INC-03_e3.png)

*E3, comparisons per range query against selectivity (log-log). Before the fix (`f6f773e`), the B+ tree line is flat. After the fix (`c8ec36c`), the B+ tree and the sorted list do almost exactly the same number of comparisons, so their lines overlap.*

CORE suite on `vicente-mba`, per query (counters ÷ 200, time = median of 5 reps):

| | Before (`e9db2d1`) | After (`c8ec36c`) |
|---|---|---|
| Range: comparisons | 45,653 | 474 |
| Range: nodes visited | 2,197 | 25 |
| Range: time | 4.90 ms | 0.19 ms |
| Prefix: comparisons | 72,396 | 168 |
| Prefix: nodes visited | 3,497 | 11 |
| Prefix: time | 10.4 ms | 0.07 ms |

Counters were identical across all 5 repetitions, and identical between Neil's machine and mine for the same code, so they reflect the code rather than the hardware.

## Root cause

File `indexes/bplus_tree.py`, function `_collect_range`, lines 179–189 in the original code, called from `range_search` (lines 173–177). The problem is lines 188–189:

```python
for child in node.children:
    self._collect_range(child, lo, hi, out)
```

For every internal node, the code recursed into **every** child without checking whether that child's keys could overlap `[lo, hi]`. So every range query went down every branch to every leaf and examined every key in the tree. It never used the leaves' `next` pointers, which exist so that a range query can go down once and then read the leaves left to right.

The answers were still correct for two reasons. In each leaf, line 184 (`if lo <= key <= hi`) only kept keys inside the range, so the extra keys were examined and then thrown away. And the loop visited children from left to right, so the results still came out in key order. The bug cost time, not correctness.

## Fix

Commit `c8ec36c`. `range_search` now:

1. returns `[]` if `lo > hi`;
2. calls `_find_leaf(lo)` to go down one path from the root to the leaf where `lo` belongs;
3. uses `_bisect_left` to find the first key `>= lo` in that leaf;
4. walks right through the keys, following `leaf.next` at the end of each leaf, adding each key's values to the result and stopping at the first key greater than `hi`.

`_collect_range` was removed, since nothing else used it.

```diff
<paste the output of: git diff c8ec36c~1 c8ec36c -- indexes/>
```

## Verification

`make test` passes after the fix: 168 passed, 3 skipped, the same as before.

E3 on the same workload (`c8ec36c`), comparisons per range query, B+ tree vs. sorted list:

| Selectivity | B+ tree | Sorted list |
|---|---|---|
| 0.0001 | 21.9 | 21.5 |
| 0.001 | 62.9 | 62.5 |
| 0.01 | 473.9 | 473.5 |
| 0.05 | 2,299.9 | 2,299.5 |
| 0.1 | 4,581.8 | 4,581.6 |
| 0.25 | 11,429.8 | 11,429.6 |

The fixed B+ tree now matches the sorted list, another O(log n + k) structure, to within less than one comparison per query. The small extra cost comes from doing one short binary search per tree level instead of one long one.

The build, point-hit and point-miss counters in the CORE suite are identical before and after the fix (for example, 16,754 comparisons and 4,000 nodes per 1,000 point hits, and 4,330 splits per build), which confirms that only range and prefix queries changed.

## Impact on recommendations

Yes, for F2 (search-as-you-type, prefix) and F3 (workout mode, tempo range). Before the fix, the B+ tree did range queries as badly as the hash table (9,130,600 comparisons per 200 queries for both), so we would have ruled it out for both features and recommended the sorted list. After the fix, it matches the sorted list's comparison counts exactly, so it is a real candidate for F2 and F3, and the choice between the two has to be made on timings and on insert cost (F4). The bug also distorted any test of the interns' claim that the B+ tree is "the answer for everything": before the fix, it was one of the worst choices for exactly the queries a B+ tree is designed for.

## Why the tests didn't catch it

The tests only check that each query returns the right values in the right order, and the buggy code did. A test that checks the amount of work would have caught it. For example: build a tree, run a range query that covers only a few keys, and assert that `nodes_visited` is at most the tree's height plus the number of leaves the range spans. Or run range queries of different sizes and assert that comparisons grow with the size of the range rather than staying constant.