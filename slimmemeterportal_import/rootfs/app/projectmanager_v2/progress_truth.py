from datetime import datetime, timezone

from development_build_contract import evaluate_build_contract

def _parse_time(value):
    if isinstance(value, datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try: parsed=datetime.fromisoformat(str(value or '').replace('Z','+00:00'))
    except ValueError: return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def _intervals(history):
    points=[]
    for item in history or []:
        if not isinstance(item,dict): continue
        at=_parse_time(item.get('at'))
        try: step=int(item.get('step'))
        except (TypeError,ValueError): continue
        if at is not None: points.append((at,step))
    points.sort(key=lambda x:x[0]); out=[]; actual={}
    for (a,sa),(b,sb) in zip(points,points[1:]):
        ds=sb-sa; seconds=max(0.0,(b-a).total_seconds())
        if ds>0:
            per=seconds/ds; out.append(per)
            for offset in range(ds): actual[str(sa+offset)]=int(round(per))
    return out,actual

def _trend(rates):
    if len(rates)<2: return 'insufficient_data'
    previous=sum(rates[:-1])/len(rates[:-1]); latest=rates[-1]
    if previous<=0: return 'stable'
    ratio=latest/previous
    return 'faster' if ratio<=0.85 else ('slower' if ratio>=1.15 else 'stable')

def build_task_progress(task, *, now=None):
    if not isinstance(task,dict) or not task: return None
    now=now or datetime.now(timezone.utc); now=now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    try: total=max(1,int(task.get('steps_total') or 1))
    except (TypeError,ValueError): total=1
    try: step=max(1,min(total,int(task.get('step') or 1)))
    except (TypeError,ValueError): step=1
    status=str(task.get('status') or 'ACTIVE').upper(); completed=total if status=='DONE' else max(0,step-1); remaining=max(0,total-completed)
    created=_parse_time(task.get('created_at')); elapsed=max(0,int((now-created).total_seconds())) if created else None
    rates,actual=_intervals(task.get('progress_history') or [])
    eta=0 if status=='DONE' else (max(0,int(round((sum(rates)/len(rates))*remaining))) if rates else None)
    meta=task.get('build_metadata') if isinstance(task.get('build_metadata'),dict) else {}
    original=meta.get('estimated_total_seconds'); variance=(elapsed-int(original)) if elapsed is not None and original else None
    test_actual=task.get('test_verification_actual_seconds')
    efficiency={'schema':'energie_development_efficiency_v1','step_actual_seconds':actual,'test_verification_actual_seconds':test_actual,'original_estimated_total_seconds':original,'elapsed_seconds':elapsed,'estimate_variance_seconds':variance,'planning_ratio': round(elapsed/int(original),3) if elapsed is not None and original else None,'planning_trend':_trend(rates)}
    color={'BLOCKED':'RED','WAITING_APPROVAL':'ORANGE','PAUSED':'ORANGE','DONE':'GREEN','ACTIVE':'GREEN'}.get(status,'ORANGE')
    result={'step_label':f'Stap {step}/{total}','step':step,'steps_total':total,'completed_steps':completed,'remaining_steps':remaining,'next_step':str(task.get('next_action') or ''),'elapsed_seconds':elapsed,'estimated_remaining_seconds':eta,'blockers':list(task.get('blockers') or []),'status_color':color,'progress_percent':100 if status=='DONE' else int(round((step/total)*100)),'planning_trend':_trend(rates),'step_actual_seconds':actual,'test_verification_actual_seconds':test_actual,'estimate_variance_seconds':variance,'development_efficiency':efficiency}
    contract=evaluate_build_contract(task,result)
    if contract.get('required'):
        result.update({'development_build_contract':contract,'thinking_level':contract.get('thinking_level'),'estimated_total_seconds':contract.get('estimated_total_seconds'),'estimated_test_verification_seconds':contract.get('estimated_test_verification_seconds'),'step_estimates_seconds':contract.get('step_estimates_seconds')})
    return result
