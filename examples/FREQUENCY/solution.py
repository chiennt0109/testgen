import sys
v=list(map(int,sys.stdin.read().split())); n,q=v[:2]; a=v[2:2+n]; print(*[a.count(x) for x in v[2+n:]],sep="\n")
