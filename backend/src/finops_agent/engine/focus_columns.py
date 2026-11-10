"""Additional FOCUS dimensions used by the imported community use cases."""
EXTRA_COLUMNS = {
    'BillingAccountName':'VARCHAR','BillingAccountType':'VARCHAR','BillingPeriodEnd':'TIMESTAMP',
    'ProviderName':'VARCHAR','PublisherName':'VARCHAR','ServiceProviderName':'VARCHAR',
    'InvoiceIssuerName':'VARCHAR','HostProviderName':'VARCHAR','InvoiceId':'VARCHAR',
    'RegionName':'VARCHAR','AvailabilityZone':'VARCHAR','ResourceType':'VARCHAR',
    'ChargeClass':'VARCHAR','ChargeDescription':'VARCHAR','ChargeFrequency':'VARCHAR',
    'ServiceSubcategory':'VARCHAR','SkuId':'VARCHAR','SkuPriceId':'VARCHAR','SkuPriceDetails':'JSON',
    'PricingQuantity':'DOUBLE','PricingUnit':'VARCHAR','ListUnitPrice':'DOUBLE','ContractedUnitPrice':'DOUBLE',
    'PricingCurrency':'VARCHAR','PricingCurrencyEffectiveCost':'DOUBLE',
    'PricingCurrencyListUnitPrice':'DOUBLE','PricingCurrencyContractedUnitPrice':'DOUBLE',
    'CommitmentDiscountName':'VARCHAR','CommitmentDiscountCategory':'VARCHAR',
    'CommitmentDiscountQuantity':'DOUBLE','CommitmentDiscountUnit':'VARCHAR',
    'CapacityReservationId':'VARCHAR','CapacityReservationStatus':'VARCHAR',
    'AllocatedResourceId':'VARCHAR','AllocatedResourceName':'VARCHAR','AllocatedMethodId':'VARCHAR',
    'ContractApplied':'JSON','ContractCommitmentId':'VARCHAR','ContractCommitmentCategory':'VARCHAR',
    'ContractCommitmentPeriodStart':'TIMESTAMP','ContractCommitmentPeriodEnd':'TIMESTAMP',
}
