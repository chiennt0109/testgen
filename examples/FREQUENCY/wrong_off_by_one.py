import sys
v=list(map(int,sys.stdin.read().split())); n,q=v[:2]; a=v[2:2+n]; print(*[max(0,a.count(x)-1) for x in v[2+n:]],sep="\n")
