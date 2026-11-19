import os,time,json,logging
from pathlib import Path
import redis
from sqlalchemy import select
from .db import Session
from .models import Pack,PackLine,Edition,BasketMeta
from .common import lock
from .basket_rules import recommend
from .basket_service import effective_baskets,meta
q=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
while True:
    Path('/tmp/books-heartbeat').touch()
    try:
        item=q.blpop('book-baskets',timeout=2)
        if not item:continue
        pack_id,_,run=item[1].partition(':')
        with Session()as s:
            p=lock(s,Pack,int(pack_id))
            if p.ml_state!='queued'or p.ml_run!=run:continue
            p.ml_state='running';s.commit()
            try:
                generation=s.scalar(select(BasketMeta.generation).where(BasketMeta.id==1))or 0
                entries=[{'id':b.id,'code':b.code,'source_class':b.source_class,'subjects':b.subjects}for b in effective_baskets(s)]
                subjects=list(s.scalars(select(Edition.subject).join(PackLine,PackLine.edition_id==Edition.id).where(PackLine.pack_id==p.id)))
                result=recommend(entries,subjects)
                m=meta(s);p=lock(s,Pack,p.id)
                if p.ml_state!='running'or p.ml_run!=run:continue
                if m.generation!=generation:
                    p.ml_state='failed';p.error='分析期间历史课程篮发生合并或补登记，旧成绩未发布，请重新分析';s.commit();continue
                result['basket_generation']=generation;p.recommendation=result;p.scores_valid=True;p.ml_state='ready';p.error=None
                Path(f'/artifacts/basket-{p.id}.json').write_text(json.dumps(result,ensure_ascii=False));s.commit()
            except Exception as ex:p.ml_state='failed';p.error=str(ex)[:450];s.commit();logging.exception('basket failed')
    except Exception:logging.exception('queue unavailable');time.sleep(1)
