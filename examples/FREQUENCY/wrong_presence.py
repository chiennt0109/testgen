import sys
v=list(map(int,sys.stdin.read().split())); n,q=v[:2]; a=set(v[2:2+n]); print(*[int(x in a) for x in v[2+n:]],sep="\n")
