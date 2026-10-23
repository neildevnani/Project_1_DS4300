"""Your experiments.  *** YOU EXTEND THIS FILE. ***

Run one experiment, or all of them:

    make experiments MEMBER=alice MACHINE=alice-mbp                 # all
    make experiments MEMBER=alice MACHINE=alice-mbp ONLY=example     # one

``example_point_lookups`` below is the summer 2024 interns' one finished experiment, and it works. Copy its
pattern for each experiment the README asks for (E1-E6), and register each
new function in ``EXPERIMENTS`` at the bottom of this file.

The pattern, for every configuration you measure:
    1. prepare keys and queries OUTSIDE the timed region,
    2. build a fresh index (time it with ``time_build`` if build cost matters),
    3. ``index.reset_stats()``, then time one batch with ``time_batch``,
    4. ``writer.record(index, ...)`` one row,
    5. repeat for ``reps`` replicates.
"""

from __future__ import annotations
import random
import time
from typing import Callable, Optional, Sequence

from bench.cli import parse, parser, writer_from_args
from bench.results import ResultsWriter
from bench.timing import build_memory_bytes, time_batch, time_build
from indexes import ALL_INDEXES, make_index
from loaders.spotify import key_value_pairs, load_tracks
from datagen.synthetic import point_queries, range_queries, prefix_queries

SEED = 4300


def example_point_lookups(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """Build cost and point-lookup (hit) cost on track_id as the index grows."""
    pairs = key_value_pairs(tracks, "track_id")  # file order
    rng = random.Random(SEED)

    for n in (1_000, 10_000, len(pairs)):
        subset = pairs[:n]
        queries = [key for key, _ in rng.sample(subset, 500)]  # every query is a hit

        for name in ALL_INDEXES:
            # Memory once per configuration (tracing is slow; never time it).
            memory = build_memory_bytes(lambda: make_index(name), subset)

            for rep in range(reps):
                common = dict(
                    experiment="example", dataset="spotify", key_column="track_id",
                    insert_order="file", n_keys=n, rep=rep,
                )

                index = make_index(name)
                ns = time_build(index, subset)
                writer.record(
                    index, **common, operation="build", operation_param="",
                    n_ops=n, total_ns=ns, memory_bytes=memory,
                )

                index.reset_stats()
                ns = time_batch(index.search, queries)
                writer.record(
                    index, **common, operation="point_hit", operation_param=1.0,
                    n_ops=len(queries), total_ns=ns,
                    height=index.structure_info().get("height", ""),
                )
            print(f"  n={n:>7,}  {name:<14} done", flush=True)


def e1(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E1: track_id in file order; at least 6 sizes from 1,000 to 114,000; record memory_bytes."""
    pairs = key_value_pairs(tracks, "track_id")  # file order

    for n in (1_000, 2_000, 5_000, 10_000, 30_000, 60_000, len(pairs)):
        subset = pairs[:n]

        for name in ALL_INDEXES:
            # Memory once per configuration (tracing is slow; never time it).
            memory = build_memory_bytes(lambda: make_index(name), subset)

            for rep in range(reps):
                index = make_index(name)
                ns = time_build(index, subset)
                writer.record(
                    index, experiment="e1", dataset="spotify", key_column="track_id",
                    insert_order="file", n_keys=n, operation="build", operation_param="",
                    n_ops=n, rep=rep, total_ns=ns, memory_bytes=memory,
                )
            print(f"  n={n:>7,}  {name:<14} done", flush=True)

def e2(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E2: track_id; the same sizes as E1; point_queries with hit rates 1.0 and 0.0"""
    pairs = key_value_pairs(tracks, "track_id")

    for n in (1_000, 2_000, 5_000, 10_000, 30_000, 60_000, len(pairs)):
        subset = pairs[:n]
        keys = [key for key, _ in subset] #pulls out keys in subset
        hit = point_queries(keys, 500, 1.0, seed=SEED)
        miss = point_queries(keys, 500, 0.0, seed=SEED)

        for name in ALL_INDEXES:
            index = make_index(name)  #make empty index
            for key, value in subset:  #put n keys into index
                index.insert(key, value)

            for rep in range(reps):
                common = dict(
                    experiment="e2", dataset="spotify", key_column="track_id",
                    insert_order="file", n_keys=n, rep=rep,
                )
                index.reset_stats() #start fresh
                ns = time_batch(index.search, hit)
                writer.record(
                    index, **common, operation="point_hit", operation_param=1.0, #operation hit
                    n_ops=len(hit), total_ns=ns, #how many, how long
                    height=index.structure_info().get("height", ""),
                )
                index.reset_stats()
                ns = time_batch(index.search, miss)
                writer.record(
                    index, **common, operation="point_miss", operation_param=0.0, #operation miss
                    n_ops=len(miss), total_ns=ns,
                    height=index.structure_info().get("height", ""),
                )
            print(f"  n={n:>7,}  {name:<14} done", flush=True)

def e3(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    pairs = key_value_pairs(tracks, "tempo") # turn inro (tempo,row_id)
    keys = [k for k, _ in pairs] #keep key (tempo)
    selectivities = (0.0001, 0.001, 0.01, 0.05, 0.1, 0.25) #what fraction of all the keys one range query should match
    queries = {} #make empty dic
    for s in selectivities: # for each selectivity -> run query
        queries[s] = range_queries(keys, 200, s, seed=SEED)  #makes 200 ranges of that selectivity and stores it

    for name in ALL_INDEXES:
        index = make_index(name)  #make empty index
        for key, value in pairs:  #put n keys into index
            index.insert(key, value)

        for s in selectivities: #goes through every selectivity
            for rep in range(reps): #measurement reps times for that selectivity
                common = dict(
                    experiment="e3", dataset="spotify", key_column="tempo",
                    insert_order="file", n_keys=len(pairs), rep=rep
                )
                index.reset_stats()
                ns = time_batch(lambda q: index.range_search(*q), queries[s]) #each 200 (lo, hi) pairs open up hi=_ lo=_ and call range
                writer.record(
                    index, **common, operation="range", operation_param=s,
                    n_ops=len(queries[s]), total_ns=ns,
                )
            print(f"  s={s:<7}  {name:<14} done", flush=True)

def e4(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    pairs = key_value_pairs(tracks, "track_name") # turn into (track_name,row_id)
    keys = [k for k, _ in pairs]  # keep key (track_name)
    length = (1, 2, 3, 4 ,5)
    queries = {}
    for l in length:
        queries[l] = prefix_queries(keys, 200, l, seed=SEED)

    for name in ALL_INDEXES:
        index = make_index(name)  # make empty index
        for key, value in pairs:  # put n keys into index
            index.insert(key, value)

        for l in length:
            for rep in range(reps):
                common = dict(
                    experiment="e4", dataset="spotify", key_column="track_name",
                    insert_order="file", n_keys=len(pairs), rep=rep
                )
                index.reset_stats()
                ns = time_batch(index.prefix_search, queries[l])
                writer.record(
                    index, **common, operation="prefix", operation_param=l,
                    n_ops=len(queries[l]), total_ns=ns,
                )
            print(f"  len={l}  {name:<14} done", flush=True)

# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    "E1": e1,
    "E2": e2,
    "E3": e3,
    "E4": e4,
}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = parser("Run your experiments.")
    p.add_argument("--only", choices=sorted(EXPERIMENTS), help="run just this experiment")
    args = parse(p, argv)
    writer = writer_from_args(args)
    tracks = load_tracks()
    names = [args.only] if args.only else list(EXPERIMENTS)
    for name in names:
        print(f"{name}: {args.reps} reps, session {writer.session_id}", flush=True)
        started = time.perf_counter()
        EXPERIMENTS[name](writer, tracks, args.reps)
        print(f"{name}: finished in {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
