"""
scripts/create_sample_data.py
Gera dados sintéticos realistas de Brasileirão e Champions League.
NÃO representam resultados reais — apenas para validação local do sistema.

Uso:
    python scripts/create_sample_data.py
"""
from __future__ import annotations
import hashlib, random, sys
from datetime import date, timedelta
from pathlib import Path
from typing import List
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import pandas as pd
from app.core.config import settings
from app.core.logger import get_logger
logger = get_logger(__name__)

BRASILEIRAO_TEAMS = [
    "Flamengo","Palmeiras","Atletico Mineiro","Corinthians","Fluminense",
    "Botafogo","Cruzeiro","Gremio","Internacional","Sao Paulo",
    "Santos","Vasco","Bahia","Fortaleza","Atletico Goianiense",
    "Bragantino","Coritiba","America Mineiro","Cuiaba","Goias",
]
UCL_TEAMS = [
    "Real Madrid","Manchester City","Bayern Munich","Psg","Liverpool","Chelsea",
    "Barcelona","Juventus","Borussia Dortmund","Inter Milan","Atletico Madrid","Ajax",
    "Porto","Benfica","Napoli","Ac Milan","Arsenal","Tottenham","Lyon","Sevilla",
    "Rb Leipzig","Shakhtar Donetsk","Sporting Cp","Villarreal","Rangers","Celtic",
    "Club Brugge","Salzburg","Marseille","Monaco","Frankfurt","Feyenoord",
]

def _mid(c,d,h,a): return hashlib.md5(f"{c}_{d}_{h}_{a}".lower().replace(" ","_").encode()).hexdigest()[:12]
def _goals(lh,la): return int(np.random.poisson(lh)), int(np.random.poisson(la))
def _stats(hg,ag):
    hs=max(1,int(np.random.normal(12,3))); as_=max(1,int(np.random.normal(10,3)))
    hp=round(random.uniform(38,62),1)
    def tg(g):
        g015=g7590=ght=0
        for _ in range(g):
            m=random.randint(1,90)
            if m<=15: g015+=1
            if m>75: g7590+=1
            if m<=45: ght+=1
        return g015,g7590,ght
    hg015,hg7590,htg=tg(hg); ag015,ag7590,atg=tg(ag)
    return {"home_shots":hs,"away_shots":as_,"home_shots_on_target":min(hs,max(0,int(hs*random.uniform(0.3,0.5)))),"away_shots_on_target":min(as_,max(0,int(as_*random.uniform(0.3,0.5)))),"home_corners":max(0,int(np.random.poisson(5.0))),"away_corners":max(0,int(np.random.poisson(4.5))),"home_yellow_cards":max(0,int(np.random.poisson(1.8))),"away_yellow_cards":max(0,int(np.random.poisson(1.8))),"home_red_cards":1 if random.random()<0.05 else 0,"away_red_cards":1 if random.random()<0.05 else 0,"home_fouls":max(5,int(np.random.normal(12,3))),"away_fouls":max(5,int(np.random.normal(12,3))),"home_possession":hp,"away_possession":round(100-hp,1),"home_xg":round(max(0.1,np.random.normal(hg*0.9+0.3,0.5)),2),"away_xg":round(max(0.1,np.random.normal(ag*0.9+0.3,0.5)),2),"first_half_home_goals":htg,"first_half_away_goals":atg,"minute_first_goal":random.randint(1,90) if (hg+ag)>0 else 0,"home_goals_0_15":hg015,"away_goals_0_15":ag015,"home_goals_75_90":hg7590,"away_goals_75_90":ag7590}

def generate_brasileirao(seasons,rounds=38):
    recs=[]; teams=BRASILEIRAO_TEAMS[:20]; strength={t:round(random.uniform(0.8,1.8),2) for t in teams}
    for s in seasons:
        bd=date(int(s),4,1)
        for rn in range(1,rounds+1):
            sh=teams.copy(); random.shuffle(sh); pairs=[(sh[i],sh[i+1]) for i in range(0,20,2)]; rd=bd+timedelta(days=(rn-1)*7+random.randint(0,2))
            for h,a in pairs:
                hg,ag=_goals(strength[h]*1.1,strength[a]); mid=_mid("brasileirao",str(rd),h,a)
                recs.append({"match_id":mid,"competition":"brasileirao","season":s,"date":rd,"home_team":h,"away_team":a,"home_goals":hg,"away_goals":ag,"matchday":rn,**_stats(hg,ag)})
    return pd.DataFrame(recs)

def generate_ucl(seasons):
    recs=[]; teams=UCL_TEAMS[:32]; strength={t:round(random.uniform(1.0,2.2),2) for t in teams}
    for s in seasons:
        by=int(s[:4]); groups=[teams[i:i+4] for i in range(0,32,4)]
        mups=[(0,1),(2,3),(0,2),(1,3),(0,3),(1,2)]
        for gi,grp in enumerate(groups):
            for rd,(ti,tj) in enumerate(mups):
                for leg,(hi,ai) in enumerate([(ti,tj),(tj,ti)]):
                    rdt=date(by,9,1)+timedelta(days=rd*21+leg*7+gi); h,a=grp[hi],grp[ai]; hg,ag=_goals(strength[h]*1.05,strength[a])
                    recs.append({"match_id":_mid("cl",str(rdt),h,a),"competition":"champions_league","season":s,"date":rdt,"home_team":h,"away_team":a,"home_goals":hg,"away_goals":ag,"stage":"group",**_stats(hg,ag)})
        kt=teams[:16].copy()
        for stg,sdt in [("round_of_16",date(by+1,2,14)),("quarter_final",date(by+1,4,9)),("semi_final",date(by+1,4,30))]:
            random.shuffle(kt); ws=[]
            for i in range(0,len(kt),2):
                if i+1>=len(kt): break
                h,a=kt[i],kt[i+1]
                for leg in range(1,3):
                    ld=sdt+timedelta(days=7*(leg-1)); hg,ag=_goals(strength[h],strength[a])
                    recs.append({"match_id":_mid("cl",str(ld)+f"l{leg}",h,a),"competition":"champions_league","season":s,"date":ld,"home_team":h,"away_team":a,"home_goals":hg,"away_goals":ag,"stage":stg,**_stats(hg,ag)})
                ws.append(h if random.random()>0.5 else a)
            kt=ws
        if len(kt)>=2:
            h,a=kt[0],kt[1]; fd=date(by+1,6,1); hg,ag=_goals(strength[h],strength[a])
            recs.append({"match_id":_mid("cl_final",str(fd),h,a),"competition":"champions_league","season":s,"date":fd,"home_team":h,"away_team":a,"home_goals":hg,"away_goals":ag,"stage":"final",**_stats(hg,ag)})
    return pd.DataFrame(recs)

if __name__=="__main__":
    np.random.seed(42); random.seed(42)
    sd=settings.SAMPLES_DATA_DIR; pd_=settings.PROCESSED_DATA_DIR
    print("Generating Brasileirao (2022-2024)...")
    bra=generate_brasileirao(["2022","2023","2024"]); bra.to_csv(sd/"brasileirao_sample.csv",index=False); bra.to_csv(pd_/"brasileirao_2022-2024.csv",index=False); print(f"  {len(bra)} matches.")
    print("Generating Champions League (2022/23-2023/24)...")
    ucl=generate_ucl(["2022/23","2023/24"]); ucl.to_csv(sd/"champions_league_sample.csv",index=False); ucl.to_csv(pd_/"champions_league_2022-2024.csv",index=False); print(f"  {len(ucl)} matches.")
    print("\nDone! Run: python scripts/train_all.py")
