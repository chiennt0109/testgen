def generate(seed: int, params: dict) -> str:
    cases=[(1,[]),(4,[(1,2),(2,3),(3,1)]),(5,[(1,2),(1,3)]),(6,[(1,2),(3,4),(5,6)])]
    n,e=cases[(seed-1)%len(cases)]
    return f"{n} {len(e)}\n"+"\n".join(f"{u} {v}" for u,v in e)+("\n" if e else "")
