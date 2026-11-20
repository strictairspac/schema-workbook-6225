from fastapi import APIRouter,Depends
from src.config.database import db_session
from src.utils.security import current,writer
from src.schemas.sample import SampleInput,SampleUpdate
from src.services import assembly as service
router=APIRouter()
@router.get('/reports/{ident}/samples')
def samples(ident:int,db=Depends(db_session),user=Depends(current)):return service.samples_listing(db,ident)
@router.post('/reports/{ident}/samples',status_code=201)
def create(ident:int,data:SampleInput,db=Depends(db_session),user=Depends(writer)):return service.create_sample(db,ident,data,user)
@router.put('/samples/{sid}')
def update(sid:int,data:SampleUpdate,db=Depends(db_session),user=Depends(writer)):return service.update_sample(db,sid,data,user)
@router.delete('/samples/{sid}')
def delete(sid:int,db=Depends(db_session),user=Depends(writer)):return service.delete_sample(db,sid,user)
@router.get('/reports/{ident}/assembly')
def assembly(ident:int,db=Depends(db_session),user=Depends(current)):return service.assembly_detail(db,ident)
@router.post('/reports/{ident}/assembly/refresh',status_code=202)
def refresh(ident:int,db=Depends(db_session),user=Depends(writer)):return service.request_refresh(db,ident,user)
