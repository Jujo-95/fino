import csv
import hashlib
import io
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from ..config import atomic_write_text
from ..engine.schema import COLUMNS
from .focus import enrich
from .scenarios import Scenario, events, truth


def money(value: float) -> str:
    return str(Decimal(str(value)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP))


def noise(seed: int, client: str, resource: str, day: date) -> float:
    value = hashlib.sha256(f'{seed}:{client}:{resource}:{day}'.encode()).hexdigest()
    return .97 + int(value[:8],16)/0xffffffff*.06


def base_row(s: Scenario, day: date, resource: str, service: str, category: str,
             quantity: float, rate: float, tags: dict[str, str]) -> dict[str, object]:
    listed = quantity*rate
    return dict(BillingAccountId=s.client_id+'-billing',SubAccountId=tags.get('service','shared'),
        SubAccountName=tags.get('service','shared'),ServiceName=service,ServiceCategory=category,
        ResourceId=f'{s.client_id}/{resource}',ResourceName=resource,RegionId='us-east-1',
        ChargeCategory='Usage',PricingCategory='On-Demand',CommitmentDiscountId='',
        CommitmentDiscountType='',CommitmentDiscountStatus='',BillingCurrency='USD',
        BillingPeriodStart=day.replace(day=1).isoformat(),ChargePeriodStart=day.isoformat(),
        ChargePeriodEnd=(day+timedelta(days=1)).isoformat(),ConsumedQuantity=money(quantity),ConsumedUnit='hours',
        BilledCost=money(listed*.95),EffectiveCost=money(listed*.95),ListCost=money(listed),
        ContractedCost=money(listed*.95),Tags=json.dumps(tags,sort_keys=True))


def commitment_rows(s: Scenario, day: date, index: int, seed: int) -> list[dict[str, object]]:
    tags = dict(owner='platform',env='prod',cost_center='CC-PLATFORM',service='platform')
    capacity = 2400*s.scale
    used = min(capacity,capacity*(.95 if index>=84 else .60)*noise(seed,s.client_id,'compute',day))
    result = []
    for status,quantity in [('Used',used),('Unused',capacity-used)]:
        row = base_row(s,day,'compute-'+status.lower(),'Amazon EC2','Compute',quantity,.28,tags)
        cost = money(quantity*.18)
        row.update(CommitmentDiscountId=s.client_id+'-savings-01',CommitmentDiscountType='Spend',
            CommitmentDiscountStatus=status,PricingCategory='Committed',EffectiveCost=cost,BilledCost=cost,
            ListCost=money(quantity*.28 if status=='Used' else 0),
            ContractedCost=money(quantity*.266 if status=='Used' else 0),
            ConsumedQuantity=money(quantity if status=='Used' else 0))
        result.append(row)
    return result


def daily_rows(s: Scenario, start: date, index: int, seed: int) -> list[dict[str, object]]:
    day = start+timedelta(days=index)
    seasonal = s.weekend if day.weekday()>=5 else 1
    growth = 1+index*.0015
    result = commitment_rows(s,day,index,seed)
    for resource,service,category,quantity,rate,owner in [
        ('web','Amazon ECS','Compute',2200,.22,'commerce'),
        ('ai',s.ai_service,'AI',700,.42,'ml'),
        ('storage','Amazon S3','Storage',1800,.07,'shared'),
        ('database','Amazon RDS','Database',960,.31,'platform')]:
        factor = noise(seed,s.client_id,resource,day)*growth
        if resource in ('web','ai'):
            factor *= seasonal
        if resource=='ai' and 75<=index<80:
            factor *= 4
        if resource=='web' and 65<=index<69:
            factor *= 1.8
        tags = dict(owner=owner,env='prod',cost_center='CC-'+owner.upper(),service=owner)
        if resource=='storage' and index<82:
            tags = {k:v for k,v in tags.items() if k not in ('owner','cost_center')}
        row = base_row(s,day,resource,service,category,quantity*s.scale*factor,rate,tags)
        if resource=='storage':
            row['ConsumedUnit']='GB-month'
        result.append(row)
    return result


def generate(s: Scenario, root: Path, start: date, days: int = 90, seed: int = 42) -> dict[str, object]:
    if not 1<=days<=366:
        raise ValueError('days must be between 1 and 366')
    directory = root/s.client_id
    manifest = []
    for index in range(days):
        day = start+timedelta(days=index)
        key = day.strftime('focus/v2/%Y/%m/%d/usage.csv')
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer,fieldnames=list(COLUMNS),lineterminator='\n')
        writer.writeheader()
        rows = daily_rows(s,start,index,seed)
        writer.writerows(enrich(row) for row in rows)
        text = buffer.getvalue()
        atomic_write_text(directory/key,text)
        manifest.append(dict(day=day.isoformat(),key=key,rows=len(rows),sha256=hashlib.sha256(text.encode()).hexdigest()))
    document = dict(version=2,synthetic=True,client_id=s.client_id,start=start.isoformat(),days=days,seed=seed,
                    schema='FOCUS cost and usage dimensions with community compatibility aliases; synthetic, not certified',partitions=manifest)
    atomic_write_text(directory/'manifest.json',json.dumps(document,indent=2))
    atomic_write_text(directory/'known-events.json',json.dumps(events(start),indent=2,ensure_ascii=False))
    atomic_write_text(directory/'expected-results.json',json.dumps(truth(start),indent=2,ensure_ascii=False))
    return document
