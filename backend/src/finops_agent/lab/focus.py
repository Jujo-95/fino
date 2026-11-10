"""Synthetic FOCUS enrichment, applied after scenario costs and units are final."""
import json
from datetime import date
from typing import Any


def enrich(row: dict[str, Any]) -> dict[str, Any]:
    day = date.fromisoformat(row['ChargePeriodStart'])
    next_month = day.replace(year=day.year+1,month=1,day=1) if day.month==12 else day.replace(month=day.month+1,day=1)
    provider = 'Google Cloud' if 'Vertex' in row['ServiceName'] else 'Amazon Web Services'
    used = row['CommitmentDiscountStatus']!='Unused'
    quantity = float(row['ConsumedQuantity']) if used else 0
    tags = json.loads(row['Tags'])
    tags['ApplicationId'] = tags.get('service',row['SubAccountId'])
    row.update(BillingAccountName=row['BillingAccountId'],BillingAccountType='Billing',
        BillingPeriodEnd=next_month.isoformat(),ProviderName=provider,ServiceProviderName=provider,
        PublisherName=provider,InvoiceIssuerName=provider,HostProviderName=provider,
        InvoiceId=f'{row["BillingAccountId"]}-{day:%Y-%m}',RegionName='US East (N. Virginia)',
        AvailabilityZone='us-east-1a',ResourceType=row['ServiceName'],ChargeClass=None,
        ChargeDescription=f'Synthetic daily {row["ServiceName"]} usage',ChargeFrequency='Usage-Based',
        ServiceSubcategory=row['ServiceCategory'],SkuId=row['ResourceName']+'-sku',
        SkuPriceId=row['ResourceName']+'-price',SkuPriceDetails=json.dumps({'synthetic':True}),
        PricingQuantity=str(quantity) if used else None,PricingUnit=row['ConsumedUnit'],PricingCurrency='USD',
        ListUnitPrice=str(float(row['ListCost'])/quantity) if quantity else None,
        ContractedUnitPrice=str(float(row['ContractedCost'])/quantity) if quantity else None,
        PricingCurrencyEffectiveCost=row['EffectiveCost'],Tags=json.dumps(tags,sort_keys=True),
        CommitmentDiscountCategory='Spend' if row['CommitmentDiscountId'] else None,
        CommitmentDiscountName=row['CommitmentDiscountId'] or None,
        CommitmentDiscountQuantity=str(quantity) if row['CommitmentDiscountId'] else None,
        CommitmentDiscountUnit=row['ConsumedUnit'] if row['CommitmentDiscountId'] else None)
    row.update(PricingCurrencyListUnitPrice=row['ListUnitPrice'],PricingCurrencyContractedUnitPrice=row['ContractedUnitPrice'])
    if not used:
        row.update(ConsumedQuantity=None,ConsumedUnit=None)
    for field in ('CommitmentDiscountId','CommitmentDiscountType','CommitmentDiscountStatus'):
        row[field] = row[field] or None
    if row['CommitmentDiscountType']=='Spend':
        row['CommitmentDiscountType']='Savings Plan'
    return row
