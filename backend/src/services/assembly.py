"""分表样本行录入、更正日志与拼回委托的批次刷新管线。

写入路径（API）：样本行立即落库，同时追加一条有序更正日志并通知后台；
刷新路径（worker，单线程串行）：
- 建批：把未入批的更正冻结为一个批次，基线为当前已发布版本；
- 计算：从基线版本的样本快照与拼接计数出发，只增量应用本批更正；
- 发布：整批拼好后一次性切换版本，此前页面继续显示旧版；
- 守卫：发布以版本号CAS，迟到的批次作废（superseded），其更正释放回待办，
  在新基线上重新入批，绝不盖掉已显示的新版本；
- 恢复：中断的批次保持 processing，重启或周期扫描时按原范围重算，
  已应用的更正自动跳过，重试不重复应用。
"""
from sqlalchemy import select,update,func
from datetime import datetime,timezone
from fastapi import HTTPException
from src.config.database import Session
from src.models.entities import Report,SampleRow,Correction,Assembly,AssemblyBatch,AssemblyState,Audit
from .joining import apply_corrections
from .reports import queue

MAX_ROWS_PER_SUB=50
MAX_ROWS_PER_REPORT=200

# ---------- 查询 ----------

def _report(db,ident):
    obj=db.get(Report,ident)
    if not obj:raise HTTPException(404,'报告不存在')
    return obj

def _decomposition(report):
    if report.status!='completed' or not report.result:raise HTTPException(409,'报告尚未完成分解，暂无分表可录入样本')
    return report.result['decomposition']

def _pending_count(db,report_id):
    return db.scalar(select(func.count()).select_from(Correction).where(Correction.report_id==report_id,Correction.status=='pending'))

def samples_listing(db,ident):
    report=_report(db,ident)
    rows=[]
    pending=set(db.scalars(select(Correction.row_id).where(Correction.report_id==ident,Correction.status=='pending')))
    for x in db.scalars(select(SampleRow).where(SampleRow.report_id==ident).order_by(SampleRow.id)):
        rows.append({'id':x.id,'report_id':x.report_id,'subrelation':x.subrelation,'values':x.values,'sync':'pending' if x.id in pending else 'synced'})
    return {'status':report.status,'subrelations':report.result['decomposition'] if report.result else None,'rows':rows,'pending':_pending_count(db,ident)}

def _iso(value):
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return value.isoformat()

def assembly_detail(db,ident):
    report=_report(db,ident)
    state=db.get(AssemblyState,ident)
    version=state.version if state else 0
    asm=db.scalar(select(Assembly).where(Assembly.report_id==ident,Assembly.version==version)) if version else None
    refreshing=db.scalar(select(func.count()).select_from(AssemblyBatch).where(AssemblyBatch.report_id==ident,AssemblyBatch.status=='processing'))>0
    return {'status':report.status,'version':version,'rows':asm.rows if asm else [],'published_at':_iso(asm.created_at) if asm else None,
            'refreshing':refreshing,'pending':_pending_count(db,ident),'attributes':report.result['attributes'] if report.result else None}

# ---------- 写入（API侧） ----------

def _validate_values(decomposition,sub,values):
    if sub<0 or sub>=len(decomposition):raise HTTPException(422,'分表序号超出范围')
    expected=set(decomposition[sub])
    if set(values)!=expected:raise HTTPException(422,'样本行属性必须与分表一致：'+'、'.join(sorted(expected)))
    clean={}
    for k,v in values.items():
        s=str(v).strip()
        if not s or len(s)>120:raise HTTPException(422,'样本取值不能为空，且不超过120字')
        clean[k]=s
    return clean

def _signal(report_id):
    try:queue.rpush('schemaworkbook:assembly',str(report_id))
    except Exception:pass  # 队列暂时不可用时由周期扫描兜底

def _commit_with_audit(db,user,action,report_id):
    db.add(Audit(actor=user.email,action=action));db.commit();_signal(report_id)

def create_sample(db,ident,data,user):
    report=_report(db,ident)
    decomposition=_decomposition(report)
    values=_validate_values(decomposition,data.subrelation,data.values)
    total=db.scalar(select(func.count()).select_from(SampleRow).where(SampleRow.report_id==ident))
    if total>=MAX_ROWS_PER_REPORT:raise HTTPException(422,f'每份报告最多{MAX_ROWS_PER_REPORT}条样本行')
    per=db.scalar(select(func.count()).select_from(SampleRow).where(SampleRow.report_id==ident,SampleRow.subrelation==data.subrelation))
    if per>=MAX_ROWS_PER_SUB:raise HTTPException(422,f'每个分表最多{MAX_ROWS_PER_SUB}条样本行')
    row=SampleRow(report_id=ident,subrelation=data.subrelation,values=values)
    db.add(row);db.flush()
    db.add(Correction(report_id=ident,row_id=row.id,subrelation=data.subrelation,old_values=None,new_values=values))
    _commit_with_audit(db,user,f'录入分表样本行 报告#{ident} R{data.subrelation+1}',ident)
    return {'id':row.id,'report_id':ident,'subrelation':row.subrelation,'values':row.values}

def update_sample(db,sid,data,user):
    row=db.get(SampleRow,sid)
    if not row:raise HTTPException(404,'样本行不存在')
    report=_report(db,row.report_id)
    values=_validate_values(_decomposition(report),row.subrelation,data.values)
    if values==row.values:return {'id':row.id,'report_id':row.report_id,'subrelation':row.subrelation,'values':row.values}  # 无变化不落更正，重试安全
    old=dict(row.values)
    row.values=values
    db.add(Correction(report_id=row.report_id,row_id=row.id,subrelation=row.subrelation,old_values=old,new_values=values))
    _commit_with_audit(db,user,f'更正分表样本行 #{row.id}',row.report_id)
    return {'id':row.id,'report_id':row.report_id,'subrelation':row.subrelation,'values':row.values}

def delete_sample(db,sid,user):
    row=db.get(SampleRow,sid)
    if not row:raise HTTPException(404,'样本行不存在')
    report_id=row.report_id
    db.add(Correction(report_id=report_id,row_id=row.id,subrelation=row.subrelation,old_values=dict(row.values),new_values=None))
    db.delete(row)
    _commit_with_audit(db,user,f'撤掉分表样本行 #{sid}',report_id)
    return {'deleted':sid}

def request_refresh(db,ident,user):
    _report(db,ident)
    _signal(ident)
    return {'queued':ident}

# ---------- 刷新批次（worker侧，串行执行） ----------

def _state_for_update(db,report_id):
    state=db.scalar(select(AssemblyState).where(AssemblyState.report_id==report_id).with_for_update())
    if not state:
        state=AssemblyState(report_id=report_id,version=0)
        db.add(state);db.flush()
    return state

def _create_batch(db,report_id):
    """把未入批的待办更正冻结为一个批次；返回批次id，无待办或已有在途批次则None。

    同一报告同一时刻至多一个 processing 批次（建批时持状态行锁检查），
    保证更正严格按日志顺序落版，不会出现乱序重基。
    """
    state=_state_for_update(db,report_id)
    busy=db.scalar(select(func.count()).select_from(AssemblyBatch).where(AssemblyBatch.report_id==report_id,AssemblyBatch.status=='processing'))
    if busy:return None
    corrections=db.scalars(select(Correction).where(Correction.report_id==report_id,Correction.status=='pending',Correction.batch_id.is_(None)).order_by(Correction.id)).all()
    if not corrections:return None
    batch=AssemblyBatch(report_id=report_id,base_version=state.version,correction_ids=[c.id for c in corrections],status='processing')
    db.add(batch);db.flush()
    for c in corrections:c.batch_id=batch.id
    db.commit()
    return batch.id

def _compute_and_publish(batch_id):
    with Session() as db:
        batch=db.get(AssemblyBatch,batch_id)
        if not batch or batch.status!='processing':return
        report=db.get(Report,batch.report_id)
        decomposition=report.result['decomposition']
        base_rows,base_snapshot=[],{}
        if batch.base_version:
            base=db.scalar(select(Assembly).where(Assembly.report_id==batch.report_id,Assembly.version==batch.base_version))
            if base:base_rows,base_snapshot=base.rows,base.sample_snapshot
        corrections=[]
        for cid in batch.correction_ids:
            c=db.get(Correction,cid)
            if c and c.status!='applied':  # 已应用的是重试残留，跳过
                corrections.append({'row_id':c.row_id,'subrelation':c.subrelation,'old_values':c.old_values,'new_values':c.new_values,'status':c.status})
        rows,snapshot=apply_corrections(decomposition,base_rows,base_snapshot,corrections)
        published=db.execute(update(AssemblyState).where(AssemblyState.report_id==batch.report_id,AssemblyState.version==batch.base_version).values(version=batch.base_version+1)).rowcount
        if published!=1:
            db.rollback()  # 迟到的批次：已有更新版本发布，结果作废，更正释放回待办重新入批
            with Session() as again:
                again.execute(update(AssemblyBatch).where(AssemblyBatch.id==batch_id,AssemblyBatch.status=='processing').values(status='superseded'))
                again.execute(update(Correction).where(Correction.id.in_(batch.correction_ids),Correction.status=='pending').values(batch_id=None))
                again.commit()
            return
        db.add(Assembly(report_id=batch.report_id,version=batch.base_version+1,rows=rows,sample_snapshot=snapshot,batch_id=batch.id))
        db.execute(update(Correction).where(Correction.id.in_(batch.correction_ids),Correction.status!='applied').values(status='applied'))
        batch.status='published'
        db.commit()

def process_report(report_id):
    """先恢复中断的批次，再循环消化后续待办更正，直到没有待办为止。"""
    with Session() as db:
        interrupted=db.scalars(select(AssemblyBatch.id).where(AssemblyBatch.report_id==report_id,AssemblyBatch.status=='processing').order_by(AssemblyBatch.id)).all()
    for bid in interrupted:_compute_and_publish(bid)
    while True:
        with Session() as db:batch_id=_create_batch(db,report_id)
        if not batch_id:break
        _compute_and_publish(batch_id)

def recover_incomplete():
    """扫描需要恢复的报告：存在中断批次或未应用更正。启动与周期调用。"""
    with Session() as db:
        ids=set(db.scalars(select(AssemblyBatch.report_id).where(AssemblyBatch.status=='processing')))
        ids|=set(db.scalars(select(Correction.report_id).where(Correction.status=='pending')))
    for rid in sorted(ids):process_report(rid)
