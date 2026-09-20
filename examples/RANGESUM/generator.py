def generate(seed: int, params: dict) -> str:
    cases=[([5],[(1,1)]),([1,2,3,4],[(1,4),(2,3)]),([-5,10,-2],[(1,2),(3,3)]),([10**9,10**9],[(1,2)])]
    a,q=cases[(seed-1)%len(cases)]
    return f"{len(a)} {len(q)}\n"+" ".join(map(str,a))+"\n"+"\n".join(f"{l} {r}" for l,r in q)+"\n"
