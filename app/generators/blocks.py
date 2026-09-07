"""Reusable deterministic generators for schema blocks."""
from __future__ import annotations
import math
import random
import string
from typing import Any
from app.core.constraints import ConstraintError, bounds, evaluate


def scalar(spec: dict[str, Any], ctx: dict[str, Any], rng: random.Random) -> int | float:
    lo, hi = bounds(spec, ctx, (-100, 100)); mode = spec.get("mode", "random").lower().replace(" ", "_")
    fixed = {"minimum": lo, "maximum": hi, "zero": 0, "one": 1,
             "near_minimum": min(hi, lo + 1), "near_maximum": max(lo, hi - 1)}
    if mode in fixed:
        value = fixed[mode]
        if not lo <= value <= hi: raise ConstraintError(f"Mode {mode} unavailable in [{lo}, {hi}]")
        return value
    candidates: list[int] = []
    if mode == "negative": candidates = list(range(lo, min(hi, -1) + 1))
    elif mode == "positive": candidates = list(range(max(lo, 1), hi + 1))
    elif mode == "power_of_two": candidates = [1 << i for i in range(63) if lo <= 1 << i <= hi]
    elif mode == "perfect_square": candidates = [i*i for i in range(math.isqrt(max(0, lo)), math.isqrt(max(0, hi))+1) if lo <= i*i]
    elif mode == "multiple_of_k":
        k = int(evaluate(spec.get("k", 1), ctx)); candidates = list(range(((lo+k-1)//k)*k, hi+1, k)) if k else []
    elif mode == "custom_values": candidates = [int(x) for x in spec.get("values", []) if lo <= int(x) <= hi]
    elif mode in {"prime", "composite"}:
        def prime(n: int) -> bool: return n >= 2 and all(n % d for d in range(2, math.isqrt(n)+1))
        candidates = [x for x in range(max(lo, 2), hi+1) if prime(x) == (mode == "prime")]
    elif mode == "random": return rng.randint(lo, hi)
    else: raise ConstraintError(f"Unknown scalar mode: {mode}")
    if not candidates: raise ConstraintError(f"Mode {mode} has no valid value in [{lo}, {hi}]")
    return rng.choice(candidates)


def array(spec: dict[str, Any], ctx: dict[str, Any], rng: random.Random) -> list[int]:
    n = int(evaluate(spec.get("length", 10), ctx)); lo, hi = bounds(spec, ctx, (-100, 100))
    if n < 0: raise ConstraintError("Array length cannot be negative")
    pattern = spec.get("pattern", "random").lower().replace(" ", "_")
    if spec.get("distinct") and hi-lo+1 < n: raise ConstraintError("Not enough distinct values")
    if pattern in {"permutation"}: result = list(range(lo, lo+n));
    elif pattern == "all_equal": result = [rng.randint(lo, hi)]*n
    elif pattern in {"binary", "mostly_zero", "mostly_one"}:
        if lo > 0 or hi < 1: raise ConstraintError("Binary pattern requires range containing 0 and 1")
        p = .5 if pattern == "binary" else (.1 if pattern == "mostly_zero" else .9); result = [int(rng.random() < p) for _ in range(n)]
    elif pattern in {"increasing", "strict_increasing", "decreasing", "strict_decreasing", "nondecreasing", "nonincreasing"}:
        strict = "strict" in pattern
        if strict and hi-lo+1 < n: raise ConstraintError("Range too small for strict sequence")
        result = rng.sample(range(lo, hi+1), n) if strict else [rng.randint(lo, hi) for _ in range(n)]
        result.sort(reverse="decreasing" in pattern or "nonincreasing" in pattern)
    elif pattern in {"many_duplicates", "few_distinct"}:
        pool = [rng.randint(lo, hi) for _ in range(min(max(1, int(spec.get("distinct_count", 3))), hi-lo+1))]; result = [rng.choice(pool) for _ in range(n)]
    elif pattern in {"alternating", "zigzag"}: result = [lo if i%2 == 0 else hi for i in range(n)]
    elif pattern == "arithmetic_progression":
        step = int(spec.get("step", 1)); start = int(spec.get("start", lo)); result = [start+i*step for i in range(n)]
    elif pattern == "periodic":
        period = spec.get("values", [lo, hi]); result = [int(period[i%len(period)]) for i in range(n)]
    elif pattern in {"mountain", "valley"}:
        vals = [lo + (hi-lo)*min(i, n-1-i)//max(1, (n-1)//2) for i in range(n)]; result = vals if pattern == "mountain" else [lo+hi-x for x in vals]
    elif pattern == "extreme_values": result = [rng.choice([lo, hi]) for _ in range(n)]
    elif pattern == "custom_pattern": result = [int(x) for x in spec.get("values", [])]
    else: result = [rng.randint(lo, hi) for _ in range(n)]
    if len(result) != n or any(x < lo or x > hi for x in result): raise ConstraintError("Array pattern violates length or bounds")
    if spec.get("distinct") and len(set(result)) != n: result = rng.sample(range(lo, hi+1), n)
    if spec.get("shuffle"): rng.shuffle(result)
    return result


def graph(spec: dict[str, Any], ctx: dict[str, Any], rng: random.Random) -> list[tuple[int, ...]]:
    n, m = int(evaluate(spec.get("n", "n"), ctx)), int(evaluate(spec.get("m", "m"), ctx)); directed = bool(spec.get("directed")); simple = spec.get("simple", True)
    weighted = bool(spec.get("weighted")); self_loop = bool(spec.get("allow_self_loop")); connected = bool(spec.get("connected")); pattern = spec.get("pattern", "random_sparse").lower().replace(" ", "_")
    maximum = n*n if directed and self_loop else n*(n-1) if directed else n*(n-1)//2
    if not simple: maximum = max(maximum, m)
    if n < 0 or m < 0 or m > maximum or connected and n and m < n-1: raise ConstraintError("Invalid graph n/m constraints")
    edges: list[tuple[int,int]]=[]; seen:set[tuple[int,int]]=set()
    def add(u:int,v:int)->None:
        key=(u,v) if directed else tuple(sorted((u,v)))
        if (self_loop or u!=v) and (not simple or key not in seen): seen.add(key); edges.append((u,v))
    if connected and n: 
        order=list(range(1,n+1)); rng.shuffle(order)
        for i in range(1,n): add(order[i], order[rng.randrange(i)])
    if pattern in {"path", "cycle", "star"}:
        edges=[]; seen=set()
        for i in range(1,n): add(i,i+1)
        if pattern=="star": edges=[]; seen=set(); [add(1,i) for i in range(2,n+1)]
        if pattern=="cycle" and n>2: add(n,1)
    attempts=0
    while len(edges)<m and attempts < max(100, m*20): add(rng.randint(1,n),rng.randint(1,n)); attempts+=1
    if len(edges)!=m: raise ConstraintError("Could not construct requested graph")
    if weighted:
        lo,hi=bounds({"min":spec.get("weight_min",1),"max":spec.get("weight_max",100)},ctx); return [(u,v,rng.randint(lo,hi)) for u,v in edges]
    return edges


def tree(spec: dict[str, Any], ctx: dict[str, Any], rng: random.Random) -> list[tuple[int, ...]]:
    n=int(evaluate(spec.get("n","n"),ctx)); pattern=spec.get("pattern","random_tree").lower().replace(" ","_"); edges=[]
    for v in range(2,n+1):
        if pattern=="path": p=v-1
        elif pattern=="star": p=1
        elif pattern=="balanced_binary_tree": p=v//2
        elif pattern=="broom": p=v-1 if v <= max(2,n//2) else max(1,n//2)
        elif pattern=="caterpillar": p=max(1,min(v-1,n//2))
        else: p=rng.randint(1,v-1)
        edges.append((p,v))
    if spec.get("weighted"):
        lo,hi=bounds({"min":spec.get("weight_min",1),"max":spec.get("weight_max",100)},ctx); return [(u,v,rng.randint(lo,hi)) for u,v in edges]
    return edges


def query_list(spec:dict[str,Any],ctx:dict[str,Any],rng:random.Random)->list[tuple[int,...]]:
    count=int(evaluate(spec.get("count", "q"),ctx)); n=int(evaluate(spec.get("n","n"),ctx)); mode=spec.get("pattern","random_range").lower().replace(" ","_"); rows=[]
    for i in range(count):
        if mode=="single_point": l=r=rng.randint(1,n)
        elif mode=="whole_range": l,r=1,n
        elif mode=="prefix": l,r=1,rng.randint(1,n)
        elif mode=="suffix": l,r=rng.randint(1,n),n
        elif mode=="nested": l,r=1+i%n,n-i%n; l,r=(l,r) if l<=r else (r,l)
        else: l=rng.randint(1,n); r=rng.randint(l,n)
        row=[l,r]
        if spec.get("format") == "l r x": row.append(rng.randint(*bounds(spec,ctx)))
        rows.append(tuple(row))
    return rows


def generate_block(spec:dict[str,Any],ctx:dict[str,Any],rng:random.Random)->Any:
    kind=spec.get("type","integer").lower().replace(" ","_")
    if kind in {"integer","long_long"}: return scalar(spec,ctx,rng)
    if kind in {"array","permutation"}: return array({**spec, **({"pattern":"permutation"} if kind=="permutation" else {})},ctx,rng)
    if kind in {"graph","weighted_graph"}: return graph({**spec,"weighted":kind=="weighted_graph" or spec.get("weighted",False)},ctx,rng)
    if kind in {"tree","weighted_tree"}: return tree({**spec,"weighted":kind=="weighted_tree" or spec.get("weighted",False)},ctx,rng)
    if kind in {"query_list","interval_list"}: return query_list(spec,ctx,rng)
    if kind=="real": lo,hi=bounds(spec,ctx); return rng.uniform(lo,hi)
    if kind=="string":
        n=int(evaluate(spec.get("length",10),ctx)); alphabet={"lowercase":string.ascii_lowercase,"uppercase":string.ascii_uppercase,"digits":string.digits,"binary":"01","letters":string.ascii_letters,"alphanumeric":string.ascii_letters+string.digits}.get(spec.get("alphabet","lowercase"),spec.get("custom_alphabet","abc")); p=spec.get("pattern","random").lower().replace(" ","_"); s="".join(rng.choice(alphabet) for _ in range(n)); return s if p=="random" else (alphabet[0]*n if p=="all_same" else (s[:(n+1)//2]+s[:n//2][::-1]))
    if kind=="raw_custom_block": return str(spec.get("text",""))
    raise ConstraintError(f"Unsupported block type: {kind}")
