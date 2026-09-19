import sys
v=list(map(int,sys.stdin.read().split())); n,q=v[:2]; a=v[2:2+n]; z=v[2+n:]; print(*[sum(a[z[i]-1:z[i+1]-1]) for i in range(0,2*q,2)],sep="\n")
