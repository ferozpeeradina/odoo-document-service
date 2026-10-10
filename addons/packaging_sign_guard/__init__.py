from . import models, controllers

def post_init_hook(env):
    env['ir.attachment'].sudo().search([('res_model', '=', 'sign.oca.request'), ('access_token', '!=', False)]).write({'access_token': False})
