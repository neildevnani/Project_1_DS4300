# INC-02: Hash table build cost grows with n² instead of n

## Summary

Building the hash table got a lot slower as we added more keys. Every time n doubled, the number of resizes also doubled and the build time went up about 3 to 4 times instead of 2. The problem was that the table only added 1,024 buckets every time it grew instead of growing based on its size. Changing it to double the number of buckets fixed it. With all 114,000 track IDs in E1, the number of resizes dropped from 117 to 14.

## Detection

We noticed it while testing how long it takes to build the hash table with 1,000 up to 32,000 keys, and then checked it with E1 (build cost vs. n). The figure inc02_hash_table_e1.png in the analysis folder (made in analysis/hash_analysis.ipynb) shows it. On the left graph, the hash table's build time line gets steeper as n grows, and on the right graph the number of resizes goes up in a straight line with n.

What made us suspicious was the resizes counter. A hash table should only need about one more resize each time n doubles, but here the number of resizes kept doubling along with n.

## Expected vs. observed

Expected: inserting into a hash table should be O(1) on average, even with resizes, because resizes should happen less and less often as the table gets bigger. So building the whole table should be about O(n), and the number of resizes should only grow like log2(n), which would be around 8 resizes at 1,000 keys and 13 at 32,000 keys.

Observed: the number of resizes grew right along with n, and the build time grew faster than n.

n = 1,000: 2 resizes, 2,056 buckets, 0.0055 seconds
n = 2,000: 3 resizes, 3,080 buckets, 0.0031 seconds
n = 4,000: 6 resizes, 6,152 buckets, 0.0088 seconds
n = 8,000: 11 resizes, 11,272 buckets, 0.0206 seconds
n = 16,000: 21 resizes, 21,512 buckets, 0.05 seconds
n = 32,000: 42 resizes, 43,016 buckets, 0.1704 seconds

Going from 16,000 to 32,000 keys, resizes went from 21 to 42 when theory says it should only go up by about 1, and the time went up 3.4 times when it should only about double. The smaller sizes are too fast to time accurately, but the bigger ones show the time getting close to 4 times every time n doubles, which means it's acting like O(n²).

## Evidence

Figure: analysis/inc02_hash_table_e1.png, from analysis/hash_analysis.ipynb. The left graph is the median build time vs. n on log-log axes and the right graph is resizes vs. n, both for the hash table in E1.

E1 hash table results before the fix (median of 5 reps):
n = 1,000: 2 resizes, 0.59 ms
n = 2,000: 3 resizes, 1.15 ms
n = 5,000: 6 resizes, 4.46 ms
n = 10,000: 13 resizes, 16.35 ms
n = 30,000: 37 resizes, 120.73 ms
n = 60,000: 68 resizes, 503.75 ms
n = 114,000: 117 resizes, 1,629.16 ms

The fitted slope of build time vs. n on the log-log graph was 1.72 before the fix. A slope of 1 means O(n) and a slope of 2 means O(n²), so it was acting a lot closer to O(n²) than O(n). The resizes counter shows it even better, because counters are the same on every machine. It went from 2 to 117 as n went from 1,000 to 114,000, when it should only be around log2(n).

The counters show the problem even without the timings. structure_info also showed the number of buckets only ever went up by 1,024 at a time in our quick test (2,056, then 3,080, and so on up to 43,016).

The E1 "before" rows are from code_version f6f773e (run on neil-mac) and the "after" rows are from 305b687 (run on kenza-mba). Our quick test numbers are from 37403b8 (before) and 305b687 (after), both on kenza-mba.

## Root cause

The problem is in indexes/hash_table.py, in the _grow function on line 60, along with GROWTH_STEP = 1024 on line 31. Line 60 sets the new number of buckets to the current number plus GROWTH_STEP.

The table grows whenever it has more than 0.75 keys per bucket on average (line 55). Since every resize only adds the same 1,024 buckets, the table has to resize about every 768 inserts no matter how big it already is. Every resize moves every single key into the new buckets, which costs O(n). So there end up being about n / 768 resizes that each cost O(n), which adds up to O(n²) to build the table.

It should grow based on how big the table already is, like doubling it. That way the gaps between resizes keep getting bigger, there are only about log2(n) resizes, and all the moving adds up to O(n) total, so inserts are O(1) on average again.

It still gives the right answers because every key still gets moved into the correct bucket each time. The table is just getting rebuilt way more often than it needs to be.

## Fix

We changed line 60 in _grow so the table doubles its number of buckets instead of adding 1,024 every time it grows. The diff below is the output of git diff 37403b8..305b687 -- indexes/

```diff
diff --git a/indexes/hash_table.py b/indexes/hash_table.py
index d6de160..ca5e395 100644
--- a/indexes/hash_table.py
+++ b/indexes/hash_table.py
@@ -57,7 +57,7 @@ class HashTableIndex(Index):
 
     def _grow(self) -> None:
         """Move every entry into a larger list of buckets."""
-        new_capacity = len(self._buckets) + self.GROWTH_STEP
+        new_capacity = len(self._buckets) * 2
         new_buckets: list[list[tuple[Any, list[Any]]]] = [[] for _ in range(new_capacity)]
         for bucket in self._buckets:
             for entry in bucket:
```

Commit: 305b687

## Verification

We ran the exact same test again after the fix, with the same sizes, to compare.

n = 1,000: 8 resizes, 2,048 buckets, 0.005 seconds
n = 2,000: 9 resizes, 4,096 buckets, 0.0037 seconds
n = 4,000: 10 resizes, 8,192 buckets, 0.0073 seconds
n = 8,000: 11 resizes, 16,384 buckets, 0.0131 seconds
n = 16,000: 12 resizes, 32,768 buckets, 0.0229 seconds
n = 32,000: 13 resizes, 65,536 buckets, 0.0424 seconds

Now the resizes only go up by 1 every time n doubles (8 at 1,000 keys up to 13 at 32,000), which matches the log2(n) that theory predicts, and the number of buckets doubles each time. The build time also about doubles when n doubles now (0.0229 to 0.0424 seconds going from 16,000 to 32,000 keys, about 1.9 times) instead of going up 3 to 4 times like before.

Before the fix, 32,000 keys took 42 resizes and 0.1704 seconds. After the fix it took 13 resizes and 0.0424 seconds, so it's about 4 times faster at that size, and the gap would keep getting bigger as n grows.

We also reran E1 after the fix. With the full 114,000 keys, the hash table now only needs 14 resizes instead of 117, and the build took 84.54 ms instead of 1,629.16 ms. The slope of build time vs. n went from 1.72 down to 1.05, which matches O(n). The before and after E1 runs were on different laptops, so the exact times aren't a perfect comparison, but the resizes counter and the slope don't depend on the machine, and both show the fix worked.

make test still passes.

## Impact on recommendations

Yes, it could have. With the bug, building the hash table on the full Spotify data (about 114,000 keys) took 117 resizes, each one moving every key, so the hash table would have looked really bad for F4 (catalog import) and expensive to build for F1 (track page). That could have made us pick the B+ tree or sorted list instead, even though after the fix the hash table is the fastest for exact lookups like F1. It doesn't change F2 or F3 because a hash table can't do prefix or range searches well either way.

## Why the tests didn't catch it

The tests only check that the index returns the right values, and it does, it's just slow. A test that would catch this would check the counters instead of just the answers, like inserting n keys and making sure the resizes counter is only around log2(n), or checking that doubling n only doubles the work instead of quadrupling it.