from odoo import models

class LocalMailOnly(models.Model):
    _inherit = 'ir.mail_server'

    def send_email(self, message, *args, **kwargs):
        # Hard interception: no SMTP connection and no external delivery.
        # Deliberately do not persist/print message body or bearer signing links.
        return message.get('Message-Id') or '<intercepted@packaging-poc.example.test>'
