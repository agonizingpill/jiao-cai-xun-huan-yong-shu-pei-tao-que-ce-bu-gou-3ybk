from sqlalchemy import select,func,text
import numpy as np
from .db import Base,engine,Session
from .models import *
from .auth import hashed

def _migrate():
    with engine.begin()as c:
        if 'source_class'not in {r[0]for r in c.execute(text('SHOW COLUMNS FROM historical_baskets'))}:
            c.execute(text('ALTER TABLE historical_baskets ADD COLUMN source_class VARCHAR(60) NULL, ADD COLUMN claimed_seq INT NULL'))
        packs={r[0]for r in c.execute(text('SHOW COLUMNS FROM packs'))}
        if 'ml_run'not in packs:c.execute(text('ALTER TABLE packs ADD COLUMN ml_run VARCHAR(40) NULL'))
        if 'scores_valid'not in packs:c.execute(text('ALTER TABLE packs ADD COLUMN scores_valid TINYINT(1) NOT NULL DEFAULT 1'))

def seed():
    Base.metadata.create_all(engine)
    _migrate()
    with Session()as s:
        for role in ('operator','supervisor','viewer'):
            if not s.scalar(select(User.id).where(User.email==role+'@xunshu.demo')):s.add(User(email=role+'@xunshu.demo',password_hash=hashed('Books2026!'),role=role))
        editions={}
        for code,title,subject,version in [('PHY-V2','高中物理·必修一','physics','V2-2026'),('PHY-V1','高中物理·必修一','physics','V1-2024'),('LAB-V2','物理实验册','lab','V2-2026'),('LAB-V1','物理实验册','lab','V1-2022'),('MATH-V2','数学·必修一','math','V2-2026')]:
            e=s.scalar(select(Edition).where(Edition.code==code))
            if not e:e=Edition(code=code,title=title,subject=subject,version=version,deposit_cents=2000);s.add(e);s.flush()
            editions[code]=e
        for target,allowed,state,reason in [('PHY-V2','PHY-V1','approved','教师逐页核验，章节页码与练习相同'),('LAB-V2','LAB-V1','pending','旧版缺少传感器实验，须教师复核')]:
            if not s.scalar(select(Compatibility.id).where(Compatibility.target_id==editions[target].id,Compatibility.allowed_id==editions[allowed].id)):s.add(Compatibility(target_id=editions[target].id,allowed_id=editions[allowed].id,state=state,reason=reason))
        rooms={}
        for i in range(1,13):
            code='G1-'+str(i);room=s.scalar(select(Classroom).where(Classroom.code==code))
            if not room:room=Classroom(code=code,name='高一'+str(i)+'班',size=12);s.add(room);s.flush()
            rooms[code]=room
        for i in range(1,7):
            code='S'+str(30+i);student=s.scalar(select(Student).where(Student.code==code))
            if not student:student=Student(code=code,name='同学'+str(i),classroom_id=rooms['G1-3'].id);s.add(student);s.flush()
            if not s.scalar(select(Account.id).where(Account.student_id==student.id,Account.term=='2026秋')):s.add(Account(student_id=student.id,term='2026秋',balance_cents=0))
        for code,num in [('PHY-V2',8),('PHY-V1',10),('LAB-V2',6),('LAB-V1',4)]:
            for i in range(1,num+1):
                barcode=code+'-'+str(i).zfill(3)
                if not s.scalar(select(Copy.id).where(Copy.barcode==barcode)):s.add(Copy(barcode=barcode,edition_id=editions[code].id,condition='usable',state='available',source='2026秋回收验收'))
        for i in range(1,5):
            barcode='PHY-REPAIR-'+str(i)
            if not s.scalar(select(Copy.id).where(Copy.barcode==barcode)):s.add(Copy(barcode=barcode,edition_id=editions['PHY-V1'].id,condition='repair',state='repair',source='封面破损待修复'))
        rng=np.random.default_rng(38);patterns=[['math','physics','lab'],['language','history'],['math','computing'],['art','music']]
        class_subjects={i:patterns[int(rng.choice(4,p=[.4,.3,.2,.1]))]for i in range(1,85)}
        plan=[('HIST-'+str(i).zfill(3),'SC-2024-'+str(i).zfill(2),class_subjects[i])for i in range(1,85)]
        plan+=[('HIST-'+str(84+r).zfill(3),'SC-2024-'+str(r).zfill(2),class_subjects[r])for r in range(1,9)]
        plan+=[('HIST-'+str(93+u).zfill(3),None,patterns[int(rng.choice(4,p=[.4,.3,.2,.1]))])for u in range(4)]
        if not s.get(BasketMeta,1):s.add(BasketMeta(id=1,generation=1))
        for code,source_class,subjects in plan:
            b=s.scalar(select(HistoricalBasket).where(HistoricalBasket.code==code))
            if not b:b=HistoricalBasket(code=code,subjects=subjects);s.add(b);s.flush()
            if source_class and b.claimed_seq is None:b.source_class=source_class;b.claimed_seq=1
        s.commit();return {m.__tablename__:s.scalar(select(func.count()).select_from(m))for m in (User,Edition,Compatibility,Classroom,Student,Copy,Inspection,Pack,PackLine,Assignment,Purchase,Account,DepositEntry,HistoricalBasket)}
