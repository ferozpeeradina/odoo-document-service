"""Pure presentation whitelist. No commercial calculations except cents display."""
def data(entity): return entity.get('data',entity) if isinstance(entity,dict) else {}
def presentation(snapshot,kind):
    source=data(snapshot.get('source',{}).get('data',{})); parties=snapshot.get('parties',{})
    project=data(snapshot.get('project',{}))
    demo=bool(snapshot.get('taxConfigurationFixture') or snapshot.get('evidenceMode') in ('fixture','demonstration','synthetic') or project.get('taxConfigurationFixture') or project.get('evidenceMode') in ('fixture','demonstration','synthetic') or snapshot.get('demonstration') or project.get('demonstration') or source.get('taxConfigurationFixture') or source.get('evidenceMode') in ('fixture','demonstration','synthetic') or snapshot.get('synthetic') or snapshot.get('illustrative'))
    names=['business','factory'] if kind=='purchase_order' else ['business','customer']
    if kind=='ledger_statement' and data(snapshot.get('organisation',{})).get('type')=='factory': names=['business','factory']
    def text(value): return value if isinstance(value,str) else ''
    safe_parties=[dict(role=n.title(),**{k:text(parties[n].get(k,'')) for k in ('name','email','address')}) for n in names if isinstance(parties.get(n),dict)]
    currency=source.get('currency') or snapshot.get('currency') or data(snapshot.get('organisation',{})).get('currency')
    if not currency:
        currencies={data(x).get('currency') for x in snapshot.get('invoices',[]) if data(x).get('currency')}
        if len(currencies)==1: currency=next(iter(currencies))
    def amount(value):
        if not isinstance(value,(int,float)) or isinstance(value,bool): return ''
        return ('%s %.2f'%(text(currency),value/100)) if currency else ('%s cents'%value)
    lines=[]
    for raw in (source.get('items') or source.get('lines',[])) if kind=='packing_list' else source.get('lines',[]):
        item=data(raw); lines.append(dict(description=text(item.get('description') or item.get('name') or ''),quantity=item.get('quantity',''),unit=('%s %s'%(text(currency),item['unitPrice'])) if currency and isinstance(item.get('unitPrice'),str) else amount(item.get('unitPriceCents',item.get('priceCents'))),total=amount(item.get('totalCents',item.get('lineTotalCents',item.get('amountCents'))))))
    ledger=[]
    for category in (('purchaseOrders','factoryPayments','factoryAdjustments') if data(snapshot.get('organisation',{})).get('type')=='factory' else ('invoices','receipts','allocations','adjustments')):
        for raw in snapshot.get(category,[]):
            item=data(raw); ledger.append(dict(category=category.title(),number=item.get('number',item.get('invoiceNumber','')),date=item.get('date',item.get('issuedAt',item.get('receivedAt',''))),amount=amount(item.get('totalCents',item.get('amountCents')))))
    return dict(title=kind.replace('_',' ').title(),demo=demo,parties=safe_parties,status=source.get('status',''),date=source.get('date',source.get('issuedAt',source.get('approvedAt',source.get('createdAt','')))),number=source.get('number',source.get('invoiceNumber','')),lines=lines,shippingOption=text(source.get('shippingOption')),shippingDate=text(source.get('shippingDate')),deliveryDate=text(source.get('deliveryDate')),subtotal=amount(source.get('subtotalCents')),tax=amount(source.get('taxCents')),taxLabels=', '.join(text(t.get('label')) for t in source.get('taxRates',[]) if isinstance(t,dict)),total=amount(source.get('totalCents')),terms=text(source.get('terms','')) if kind in ('contract','purchase_order','invoice') else '',ledger=ledger,dateFrom=snapshot.get('dateFrom',''),dateTo=snapshot.get('dateTo',''),opening=amount(snapshot.get('openingBalanceCents')),balance=amount(snapshot.get('balanceCents')))
