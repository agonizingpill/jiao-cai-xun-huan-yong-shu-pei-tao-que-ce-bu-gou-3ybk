from sqlalchemy import select
from fastapi import HTTPException
from .models import HistoricalBasket,Pack,BasketMeta
from .common import audit,pack

def meta(s):
    m=s.scalar(select(BasketMeta).where(BasketMeta.id==1).with_for_update())
    if not m:m=BasketMeta(id=1,generation=0);s.add(m);s.flush()
    return m
def effective_baskets(s):
    best={}
    for b in s.scalars(select(HistoricalBasket).where(HistoricalBasket.source_class.isnot(None))):
        key=(b.claimed_seq or 0,b.id)
        if b.source_class not in best or key>best[b.source_class][0]:best[b.source_class]=(key,b)
    return sorted((b for _,b in best.values()),key=lambda b:(b.source_class,b.id))
def void_scores(s,basket_ids):
    voided=0
    for p in s.scalars(select(Pack).where(Pack.recommendation.isnot(None),Pack.scores_valid.is_(True))):
        if set((p.recommendation or {}).get('used_basket_ids')or[])&set(basket_ids):p.scores_valid=False;voided+=1
    return voided
def by_code(s,code):
    b=s.scalar(select(HistoricalBasket).where(HistoricalBasket.code==code))
    if not b:raise HTTPException(404,'课程篮编号不存在 '+code)
    return b
def claim(s,d,u):
    m=meta(s);b=by_code(s,d.code)
    if b.source_class==d.source_class:return pack(b)|{'generation':m.generation,'voided':0}
    m.generation+=1;b.source_class=d.source_class;b.claimed_seq=m.generation
    voided=void_scores(s,{b.id});audit(s,u,'补登记课程篮来源班 '+b.code+' → '+d.source_class)
    return pack(b)|{'generation':m.generation,'voided':voided}
def merge(s,d,u):
    m=meta(s);a=by_code(s,d.code_a);b=by_code(s,d.code_b)
    if a.id==b.id:raise HTTPException(409,'两个编号是同一条课程篮')
    target=d.source_class or a.source_class or b.source_class
    if not target:raise HTTPException(422,'两个旧篮都未登记来源班，请指定来源班')
    if a.source_class and b.source_class and a.source_class!=b.source_class and not d.source_class:raise HTTPException(409,'两号已登记不同来源班，请显式指定来源班再确认')
    if a.source_class==target and b.source_class==target:
        kept=max((a,b),key=lambda x:x.id)
        return{'merged':False,'source_class':target,'kept_code':kept.code,'voided':0,'generation':m.generation}
    m.generation+=1
    for x in (a,b):x.source_class=target;x.claimed_seq=m.generation
    voided=void_scores(s,{a.id,b.id});kept=max((a,b),key=lambda x:x.id)
    audit(s,u,'确认课程篮同班 '+a.code+' = '+b.code+'（'+target+'），作废成绩 '+str(voided)+' 份')
    return{'merged':True,'source_class':target,'kept_code':kept.code,'voided':voided,'generation':m.generation}
