#include <bits/stdc++.h>
using namespace std;
int main(){int n,k;cin>>n>>k;vector<long long>a(n);for(auto&x:a)cin>>x;long long ans=LLONG_MIN;for(int i=0;i+k<=n;i++){long long s=0;for(int j=i;j<i+k;j++)s+=a[j];ans=max(ans,s);}cout<<ans<<'\n';}
