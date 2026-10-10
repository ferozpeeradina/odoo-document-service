for key in ("purchase_order","packing_list","invoice","ledger_statement","contract"):
    if not env["poc.template"].search([("key","=",key),("version","=","2")]): env["poc.template"]._register_service(key,"2")
env.cr.commit()
print("SAFE_RESULT fresh_schema_template_versions_registered")
