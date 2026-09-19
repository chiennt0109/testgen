def validate(input_text:str,params:dict):
    try:
        lines=input_text.splitlines();n,k=map(int,lines[0].split());a=list(map(int,lines[1].split()))
        return (len(a)==n and 1<=k<=n,"" if len(a)==n and 1<=k<=n else "Invalid n, k, or array length")
    except (ValueError,IndexError) as exc:return False,str(exc)
