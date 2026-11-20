from pydantic import BaseModel,Field,field_validator
def _values_ok(value):
    if any(not k.strip() or len(k)>40 for k in value):raise ValueError('样本属性名不能为空且不超过40字')
    if any(not isinstance(x,str) for x in value.values()):raise ValueError('样本取值必须是字符串')
    return value
class SampleInput(BaseModel):
    subrelation:int=Field(ge=0)
    values:dict[str,str]=Field(min_length=1,max_length=10)
    @field_validator('values')
    @classmethod
    def values_valid(cls,value):return _values_ok(value)
class SampleUpdate(BaseModel):
    values:dict[str,str]=Field(min_length=1,max_length=10)
    @field_validator('values')
    @classmethod
    def values_valid(cls,value):return _values_ok(value)
