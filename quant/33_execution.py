"""Як реально заходити: маркет на закритті бара vs пасивна лімітка vs запізнення.
R-простір, однаковий cost-модель. Combo KC+ADX>20, BTC+ETH+SOL."""
import importlib.util, builtins
import numpy as np, pandas as pd
import engine as E
_p=builtins.print; builtins.print=lambda *a,**k:None
spec=importlib.util.spec_from_file_location("r23","quant/23_reduce_dd.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); builtins.print=_p
DATA=m.DATA
FEE=0.0005

def adx14(d):
    h,l=d["high"],d["low"];up=h.diff();dn=-l.diff()
    pdm=((up>dn)&(up>0))*up;mdm=((dn>up)&(dn>0))*dn;tr=E.true_range(d);a=tr.ewm(alpha=1/14,adjust=False).mean()
    pdi=100*pdm.ewm(alpha=1/14,adjust=False).mean()/a;mdi=100*mdm.ewm(alpha=1/14,adjust=False).mean()/a
    return (100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).ewm(alpha=1/14,adjust=False).mean()

def signals(d):
    cl=d["close"]; mid=E.ema(cl,20); band=2*E.atr(d,10)
    side=np.zeros(len(d)); side[((cl>mid+band)&(cl>E.ema(cl,200))).to_numpy()]=1
    side[((cl<mid-band)&(cl<E.ema(cl,200))).to_numpy()]=-1; side[adx14(d).to_numpy()<20]=0
    return side,(E.atr(d,14)*2.0).to_numpy()

def scan(d,side,sd,mode,slip=0.0003,rr=2.0):
    o,h,l,c=[d[x].to_numpy() for x in ["open","high","low","close"]]; n=len(d)
    R=[]; signals_seen=0; filled=0; i=0
    while i<n-2:
        s=side[i]; dist=sd[i]
        if s==0 or not np.isfinite(dist) or dist<=0: i+=1; continue
        signals_seen+=1
        # визначення входу
        eb=None; entry=None; slip_in=slip
        if mode=="market_open":      eb=i+1; entry=o[i+1]
        elif mode=="delay_1bar":     eb=i+2; entry=o[i+2]
        elif mode=="limit_close":    # лімітка на ціні закриття (= marketable, заповнюється одразу)
            lim=c[i]; slip_in=0.0
            if s>0 and l[i+1]<=lim: eb=i+1; entry=lim
            elif s<0 and h[i+1]>=lim: eb=i+1; entry=lim
            else: i+=1; continue
        elif mode=="limit_pullback": # ПАСИВНА лімітка на 0.5*ATR нижче (чекаємо відкат, 2 бари)
            atr=dist/2.0; lim=c[i]-s*0.5*atr; slip_in=0.0; got=False
            for jj in (i+1,i+2):
                if jj>=n: break
                if (s>0 and l[jj]<=lim) or (s<0 and h[jj]>=lim): eb=jj; entry=lim; got=True; break
            if not got: i+=1; continue  # відкату не було -> пропустили рух
        if entry is None: i+=1; continue
        filled+=1
        entry_f=entry*(1+slip_in) if s>0 else entry*(1-slip_in)
        stop=entry_f-s*dist; tgt=entry_f+s*rr*dist
        # форвард-скан
        ex=None; j=eb
        while j<n:
            if s>0:
                if l[j]<=stop: ex=stop*(1-slip); break
                if h[j]>=tgt: ex=tgt; break
            else:
                if h[j]>=stop: ex=stop*(1+slip); break
                if l[j]<=tgt: ex=tgt; break
            j+=1
        if ex is None: ex=c[-1]
        gross=s*(ex-entry_f)/dist
        cost=FEE*2*(entry_f/dist)  # комісія вх+вих у R
        R.append(gross-cost); i=j+1
    return np.array(R), signals_seen, filled

def evalmode(mode,slip=0.0003):
    allR=[]; sig=0; fil=0
    for c in ["BTC","ETH","SOL"]:
        d=DATA[c]; side,sd=signals(d); R,s,f=scan(d,side,sd,mode,slip); allR.append(R); sig+=s; fil+=f
    R=np.concatenate(allR)
    print(f"  {mode:16}{('slip'+str(slip)):>10} n={len(R):4d} fill={fil/sig*100:3.0f}% "
          f"sumR={R.sum():6.1f} exp={R.mean():+.3f} WR={(R>0).mean()*100:.0f}%")

print("СПОСОБИ ВХОДУ (R-простір, BTC+ETH+SOL):\n")
print("  Маркет-вхід одразу після закриття 4h-бара (як у бектесті):")
evalmode("market_open",0.0003)
evalmode("market_open",0.0010)  # гірший слипедж (швидкий ринок на закритті)
print("\n  Запізнення на 1 бар (зайшов через 4 год — проспав закриття):")
evalmode("delay_1bar",0.0003)
print("\n  Пасивна ЛІМІТКА на ціні закриття сигнального бара (чекаєш кращу ціну):")
evalmode("limit_close",0.0003)
print("\n  Висновок нижче.")
