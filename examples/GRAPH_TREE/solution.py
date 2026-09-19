import sys
v=list(map(int,sys.stdin.read().split())); n,m=v[:2]; p=list(range(n))
def f(x):
 while p[x]!=x:p[x]=p[p[x]];x=p[x]
 return x
for i in range(m):
 a,b=v[2+2*i]-1,v[3+2*i]-1;a,b=f(a),f(b);p[a]=b
print(len({f(i) for i in range(n)}))
