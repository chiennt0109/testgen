"""Deterministic MAXSEQ demo with ten size/data profiles."""
import random

def generate(seed:int,params:dict)->str:
    rng=random.Random(seed);profile=(params.get("test_index",1)-1)%10
    sizes=[1,2,5,10,20,40,80,150,300,500];n=sizes[profile];k=rng.randint(1,n)
    if profile==0:a=[0]
    elif profile==1:a=[-10,10]
    elif profile==2:a=list(range(n))
    elif profile==3:a=list(range(n,0,-1))
    elif profile==4:a=[7]*n
    elif profile==5:a=[-1 if i%2 else 1 for i in range(n)]
    elif profile==6:a=[rng.choice([-10**9,10**9]) for _ in range(n)]
    else:a=[rng.randint(-10**9,10**9) for _ in range(n)]
    return f"{n} {k}\n"+" ".join(map(str,a))+"\n"
