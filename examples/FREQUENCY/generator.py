def generate(seed: int, params: dict) -> str:
    cases=[([5],[5,4]),([2,2,2,3],[2,3,4]),([1,2,3,4],[1,5]),([7,7,8,7,9],[7,8,6])]
    a,q=cases[(seed-1)%len(cases)]
    return f"{len(a)} {len(q)}\n"+" ".join(map(str,a))+"\n"+"\n".join(map(str,q))+"\n"
