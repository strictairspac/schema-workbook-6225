import traceback,json,time
from pathlib import Path
from src.config.database import Session
from src.models.entities import Report
from src.services.reports import queue
from src.services.normalization import analyze
from src.services import assembly
last_scan=0.0
while True:
    Path('/tmp/worker-heartbeat').touch()
    item=queue.blpop(['schemaworkbook:queue','schemaworkbook:assembly'],timeout=2)
    if item:
        key,raw=item
        ident=int(raw)
        if key=='schemaworkbook:assembly':
            try:assembly.process_report(ident)
            except Exception:traceback.print_exc()
        else:
            try:
                with Session() as db:
                    obj=db.get(Report,ident);obj.status='running';db.commit();snapshot=obj.input_snapshot
                result=analyze(snapshot['relation']['attributes'],snapshot['dependencies'])
                with Session() as db:
                    obj=db.get(Report,ident);obj.result=result;obj.status='completed';db.commit()
                Path(f'/artifacts/report-{ident}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            except Exception as e:
                traceback.print_exc()
                with Session() as db:
                    obj=db.get(Report,ident)
                    if obj:obj.status='failed';obj.error=str(e);db.commit()
    if time.time()-last_scan>15:
        last_scan=time.time()
        try:assembly.recover_incomplete()  # 恢复中断批次并兜底丢失的信号
        except Exception:traceback.print_exc()
