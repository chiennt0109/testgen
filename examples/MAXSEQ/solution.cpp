#include <bits/stdc++.h>
using namespace std;
int main(){ios::sync_with_stdio(false);cin.tie(nullptr);int n,k;if(!(cin>>n>>k))return 0;vector<long long>a(n);for(auto&x:a)cin>>x;long long s=0;for(int i=0;i<k;i++)s+=a[i];long long ans=s;for(int i=k;i<n;i++){s+=a[i]-a[i-k];ans=max(ans,s);}cout<<ans<<'\n';}
