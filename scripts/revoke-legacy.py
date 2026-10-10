# Also run explicitly when upgrading an already installed guard.
from odoo.addons.packaging_sign_guard import post_init_hook
post_init_hook(env)
env.cr.commit()
print('Legacy OCA attachment bearer tokens revoked; no token values printed.')
