"""分表样本行按同名属性自然连接拼回委托的增量维护引擎。

纯标准库实现，不依赖ORM，便于独立测试：
- 拼接：各分表样本行在同名属性上取值一致时合并为完整委托行；
- 增量：每条更正 = 撤回旧值行 + 加入新值行，只枚举经过被更正行的组合，
  改动前后的关联值都会重算，未受影响的拼接结果原样保留；
- 来源计数：同一委托行可被多个组合拼出，计数归零才消失，
  因此撤掉一条样本行时，只要还有别的拼接来源，委托行仍然保留。
"""
import json

def _key(values):
    return json.dumps(values,sort_keys=True,ensure_ascii=False)

def combos_through(sub_rows,fixed_sub,fixed_rid,fixed_values):
    """枚举经过指定样本行的全部自然连接组合（只触及受影响的范围）。"""
    n=len(sub_rows)
    order=[fixed_sub]+[i for i in range(n) if i!=fixed_sub]
    assignment={}
    results=[]
    def walk(k):
        if k==n:
            results.append(dict(assignment));return
        sub=order[k]
        candidates=((fixed_rid,fixed_values),) if sub==fixed_sub else tuple(sub_rows[sub].items())
        for _,values in candidates:
            if any(a in assignment and assignment[a]!=v for a,v in values.items()):continue
            added=[a for a in values if a not in assignment]
            for a in added:assignment[a]=values[a]
            walk(k+1)
            for a in added:del assignment[a]
    walk(0)
    return results

def apply_corrections(decomposition,base_rows,base_snapshot,corrections):
    """在上一发布版的状态上按序增量应用更正，返回(新拼接行,新样本快照)。

    decomposition: 分表属性列表的列表；base_rows: [{'values':..,'sources':..}]；
    base_snapshot: {行id: {'sub':分表序号,'values':取值}}；
    corrections: 按发生顺序排列的 {'row_id','subrelation','old_values','new_values','status'}。
    已标记 applied 的更正是重试残留，直接跳过，保证重试不重复应用。
    """
    sub_rows=[dict() for _ in decomposition]
    snapshot={}
    for rid,item in (base_snapshot or {}).items():
        rid=str(rid)
        snapshot[rid]={'sub':item['sub'],'values':item['values']}
        sub_rows[item['sub']][rid]=item['values']
    counts={}
    for row in base_rows or []:
        counts[_key(row['values'])]=[row['values'],row['sources']]
    for corr in corrections:
        if corr is None or corr.get('status')=='applied':continue
        sub=corr['subrelation'];rid=str(corr['row_id'])
        if sub>=len(sub_rows):continue
        old,new=corr.get('old_values'),corr.get('new_values')
        if old is not None:
            for combo in combos_through(sub_rows,sub,rid,old):
                key=_key(combo)
                if key in counts:
                    counts[key][1]-=1
                    if counts[key][1]<=0:del counts[key]
            sub_rows[sub].pop(rid,None)
            snapshot.pop(rid,None)
        if new is not None:
            sub_rows[sub][rid]=new
            snapshot[rid]={'sub':sub,'values':new}
            for combo in combos_through(sub_rows,sub,rid,new):
                key=_key(combo)
                if key in counts:counts[key][1]+=1
                else:counts[key]=[combo,1]
    rows=[{'values':value[0],'sources':value[1]} for _,value in sorted(counts.items())]
    return rows,snapshot
