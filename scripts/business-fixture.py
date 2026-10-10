# Minimal synthetic source business records, not an ERP migration.
import json
customer = env['res.partner'].create({'name': 'Synthetic Alder Boxes Ltd', 'is_company': True, 'email': 'alder@example.test', 'comment': 'Synthetic demonstration only; no obligations.'})
supplier = env['res.partner'].create({'name': 'Synthetic Birch Packaging Ltd', 'is_company': True, 'email': 'birch@example.test'})
snapshot = {'synthetic': True, 'currency': 'CAD', 'customer': customer.name, 'supplier': supplier.name, 'description': '100 demonstration cartons', 'quantity': 100, 'totalCents': 125000, 'terms': customer.comment}
env.cr.commit()
print(json.dumps({'customerId': customer.id, 'supplierId': supplier.id, 'snapshot': snapshot}))
