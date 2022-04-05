# -*- coding: utf-8 -*-
import base64
import json
import logging
from datetime import date
import werkzeug
import stripe
from odoo import http
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

_logger = logging.getLogger(__name__)
class StripeConnection(http.Controller):

    @http.route('/pay/invoice', type='http', auth="public", website=True,sitemap=False)
    def index(self, **kw):
        invoice_number = kw['pay_invoice'] if kw['pay_invoice'][:3] == 'INV' else 'INV' + kw['pay_invoice']
        invoice = request.env['account.invoice'].sudo().search([('number','=',invoice_number)])
        if invoice:
            return werkzeug.utils.redirect("/my/invoices/%s" % (invoice.id))
        else:
            values = request.params.copy()
            values['error'] = "Invoice not found. Please try again."
            return request.render("website.pay-invoice",values)

class CustomPortalAccount(PortalAccount):
    @http.route(['/my/invoices/<int:invoice_id>'], type='http', auth="public", website=True)
    def portal_my_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        if access_token:
            try:
                invoice_sudo = self._document_check_access('account.invoice', invoice_id, access_token)
            except (AccessError, MissingError):
                return request.redirect('/my')
        else:
            try:
                invoice_sudo = request.env['account.invoice'].sudo().search([('id', '=', invoice_id)])
            except:
                return request.redirect('/')

        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=invoice_sudo, report_type=report_type, report_ref='account.account_invoices',
                                     download=download)

        values = self._invoice_get_page_view_values(invoice_sudo, access_token, **kw)
        PaymentProcessing.remove_payment_transaction(invoice_sudo.transaction_ids)
        return request.render("account.portal_invoice_page", values)

    @http.route('/fill/agreement', type='json', auth='public', methods=['POST'])
    def fillagreement(self, **kw):
        if kw.get('invoice_number'):
            invoice = request.env['account.invoice'].sudo().search([('number', '=', kw['invoice_number'])])
            kw['pickup_date'] = kw['pickup_date'].replace('T',' ')
            kw['logo'] = invoice.company_id.logo
            kw['image'] = bytes(kw['image'], encoding='utf-8')
            report = request.env.ref('stripe_connection.custom_pickup_form_report')
            ctx = request.env.context.copy()
            ctx['flag'] = True
            report.sudo().print_report_name = invoice.partner_id.name
            # Call report with context
            pdf = report.with_context(ctx).render_qweb_pdf(data=kw)
            if invoice:
                encoded_string = base64.b64encode(pdf[0])
                invoice[0].pickup_form = encoded_string
                return json.dumps({'success':'success'})
        else:
            return json.dumps({'invoice_not_found': 'Invoice not found'})


class myCustomCntrlr(http.Controller):
    @http.route('/register/inovice/payment', type='json', auth='public', methods=['POST'])
    def register_invoice_payment(self, **data):
        if data.get('id'):
            inv_id = int(data['id'])
            i = request.env['account.invoice'].sudo().search([('id', '=', inv_id)])
            payment_id = request.env['account.payment'].sudo().create({
                'payment_date': date.today(),
                'has_invoices': True,
                'default_invoice_ids': [(6, 0, [i.id])],
                'invoice_ids': [(6, 0, [i.id])],
                'amount': i.residual,
                'payment_method_id': 1,
                'communication': i.reference,
                'currency_id': i.company_id.currency_id.id,
                'journal_id': i.journal_id.id,
                'partner_type': 'customer',
                'partner_id': i.partner_id.id,
                'payment_type': 'inbound'
            })

            payment_id.sudo().action_validate_invoice_payment()
            template = request.env.ref('stripe_connection.custom_mail_template_data_payment_receipt')
            template.sudo().with_context().send_mail(payment_id.id, force_send=True)
            return json.dumps({
                'success': 'success',
            })
    @http.route('/new/locationData', type='http', auth='public')
    def stripe_location_func(self, **data):
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key
        conectionTokenCustom = stripe.terminal.ConnectionToken.create()
        all_locations = stripe.terminal.Location.list()
        a = {}
        a['discoveredReaders'] = all_locations['data'] # Readers is for for client side manipulations: this is is location
        for one_location in a['discoveredReaders']:
            one_location['label']= one_location['display_name']
        return json.dumps(a)
    @http.route('/note/newa', type='http', auth='public')
    def stripe_call_func(self, **data):
        a = 1
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key

        conectionTokenCustom = stripe.terminal.ConnectionToken.create()

        all_locations = stripe.terminal.Location.list()
        #commented lines Knowingly
        # my_reader = stripe.terminal.Reader.retrieve('tmr_DUkkpwYrmN1TiN')
        return json.dumps({
            # 'object': conectionTokenCustom.OBJECT_NAME,
            'secret': conectionTokenCustom.secret,
             # 'response': json.dumps(conectionTokenCustom),
        })

    @http.route('/note/newb', type='http', auth='public',csrf=False)
    def stripe_reader_call_func(self, **data):
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key

        all_locations = stripe.terminal.Location.list()
        my_reader = stripe.terminal.Reader.retrieve('tmr_DUkkpwYrmN1TiN')
        my_disc_reader = {'ip_address':my_reader['ip_address'],
                          'serial_number': my_reader['serial_number'],
                          }
        return json.dumps(my_disc_reader)


class stripeFunctionAPIs(http.Controller):

    @http.route('/note/stripeFunctionAPIs', type='http', auth='none', csrf=False)
    def stripe_fnc_apis_call_func(self, **data):

        fun_name = data['fncName']
        # Location APIs manipulations
        if fun_name == 'locationCreation':
            retu = {}
            ret = """ 
            <h2>Location Creation</h2>
            Line1:<br>
              <input type='text' name='line1' class='myInputField'>
              <br>
              City:<br>
              <input type='text' name='city'  class='myInputField'>
              <br>Country:<br>
              <input type='text' name='country'  class='myInputField'>
              <br>
              <br>Postal Code:<br>
              <input type='text' name='postal_code'  class='myInputField'>
              <br>
              <br>Display Name:<br>
              <input type='text' name='display_name'  class='myInputField'>
              <br>

              <br>

              <p id = 'fun_called' style= 'display:none;' class='myInputField'> locationCreation </p>
              <button onclick = 'ReturnFnCall()' > Submit</button>
              """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)

        if fun_name == 'RetrieveLocation':
            retu = {}
            ret = """ 
            <h2>Retrieve Creation</h2>

                        ID:<br>
              <input type='text' name='ID' class='myInputField'>
              <br>
              Display Name:<br>
              <input type='text' name='display_name'  class='myInputField'>
              <p id = 'fun_called' style= 'display:none;' class='myInputField'> RetrieveLocation </p>

              <br>  
              <button onclick = 'ReturnFnCall()' > Submit</button>
              """

            stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
            stripe.api_key = stripe_key

            aaa = stripe.terminal.Location.list()
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            return json.dumps(retu)
        if fun_name == 'UpdateLocation':
            retu = {}
            ret = """ 
                        <h2>Update Location</h2>
                        <br/>
                        ID:<br>
                          <input type='text' name='ID' class='myInputField'>
                          <br>
                        Line1:<br>
                          <input type='text' name='line1' class='myInputField'>
                          <br>
                          City:<br>
                          <input type='text' name='city'  class='myInputField'>
                          <br>Country:<br>
                          <input type='text' name='country'  class='myInputField'>
                          <br>
                          <br>Postal Code:<br>
                          <input type='text' name='postal_code'  class='myInputField'>
                          <br>
                        State:<br>
                          <input type='text' name='state' class='myInputField'>
                          <br>

                          <br>Display Name:<br>
                          <input type='text' name='display_name'  class='myInputField'>
                          <br>

                          <br>

                          <p id = 'fun_called' style= 'display:none;' class='myInputField'> UpdateLocation </p>
                          <button onclick = 'ReturnFnCall()' > Submit</button>
                          """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)
            pass

        if fun_name == 'DeleteLocation':
            retu = {}
            ret = """ 
                                    <h2>Delete Location</h2>
                                    <br/>
                                    ID:<br>
                                      <input type='text' name='ID' class='myInputField'>
                                      <br>                               

                                      <p id = 'fun_called' style= 'display:none;' class='myInputField'> DeleteLocation </p>
                                      <button onclick = 'ReturnFnCall()' > Submit</button>
                                      """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            return json.dumps(retu)
            pass
            pass
        if fun_name == 'ListLocation':
            retu = {}
            ret = """ 
                                                <h2>List Location</h2>
                                                <br/>
                                                Click On the following button to List all the Location Elements:<br>
                                                           <br/>                    

                                                  <p id = 'fun_called' style= 'display:none;' class='myInputField'> ListLocation </p>
                                                  <button onclick = 'ReturnFnCall()' > Continue</button>
                                                  """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            return json.dumps(retu)
            pass

        # Readers APIs manipulations
        if fun_name == 'ReaderCreation':
            retu = {}
            ret = """ 
                        <h2>Reader Creation</h2>
                        Registration Code:<br>
                          <input type='text' name='registration_code' class='myInputField'>
                          <br>
                          Label:<br>
                          <input type='text' name='label'  class='myInputField'>
                          <br>Location:<br>
                          <input type='text' name='location'  class='myInputField'>


                          <br>

                          <p id = 'fun_called' style= 'display:none;' class='myInputField'> ReaderCreation </p>
                          <button onclick = 'ReturnFnCall()' > Submit</button>
                          """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)
            pass
        if fun_name == 'RetrieveReader':
            retu = {}
            ret = """ 
                                    <h2>Reader Retrieve</h2>
                                     ID of the Reader to be Retrieve:<br>
                                      <input type='text' name='id' class='myInputField'>
                                      <br>


                                      <p id = 'fun_called' style= 'display:none;' class='myInputField'> RetrieveReader </p>
                                      <button onclick = 'ReturnFnCall()' > Submit</button>
                                      """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)
            pass
            pass
        if fun_name == 'UpdateReader':
            retu = {}
            ret = """ 
                                                <h2>Update Reader</h2>
                                                 ID of the Reader to be Update:<br>
                                                  <input type='text' name='id' class='myInputField'>
                                                  <br>
                                                  Label of the Reader to be Update:<br>
                                                  <input type='text' name='label' class='myInputField'>
                                                  <br>


                                                  <p id = 'fun_called' style= 'display:none;' class='myInputField'> UpdateReader </p>
                                                  <button onclick = 'ReturnFnCall()' > Submit</button>
                                                  """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)
            pass
        if fun_name == 'DeleteReader':
            retu = {}
            ret = """ 
                                                            <h2>Delete Reader</h2>
                                                             ID of the Reader to be Delete:<br>
                                                              <input type='text' name='id' class='myInputField'>
                                                              <br>


                                                              <p id = 'fun_called' style= 'display:none;' class='myInputField'> DeleteReader </p>
                                                              <button onclick = 'ReturnFnCall()' > Submit</button>
                                                              """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            # retu['fun_name'] = 'locationCreation'
            return json.dumps(retu)
            pass
        if fun_name == 'ListReader':
            retu = {}
            ret = """ 
                                                <h2>List Reader</h2>
                                                <br/>
                                                Click On the following button to List all the Reader Elements:<br><br/>


                                                  <p id = 'fun_called' style= 'display:none;' class='myInputField'>ListReader</p>
                                                  <button onclick = 'ReturnFnCall()' > Continue</button>
                                                  """
            ret = ''.join(ret.split('\n'))
            retu['data'] = '"'.join(ret.split('\"'))
            return json.dumps(retu)
            pass

    @http.route('/note/stripeFunctionAPIsReturn', type='http', auth='none', csrf=False)
    def stripe_fnc_apis_call_Return_func(self, **data):
        a = data
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        dict_keys = data.keys()
        dict_vals = data.values()
        # keys  = [i.split(']')[-1][1:] for i in dict_keys  ]
        keys = [i[abs((i[::-1]).find('[') - len(i)):abs((i[::-1]).find(']') - len(i)) - 1] for i in dict_keys]
        stripe.api_key = stripe_key
        if data['data[funcName]'].strip() == 'locationCreation':
            stripe.api_key = stripe_key

            try:
                stripe.terminal.Location.create(
                    address={
                        'line1': list(dict_vals)[1],
                        'city': list(dict_vals)[2],
                        'country': list(dict_vals)[3],
                        'postal_code': list(dict_vals)[4],
                    },
                    display_name=list(dict_vals)[5],
                )
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            return json.dumps({'data': 'The requested location has been created at the terminal'})
            pass
        if data['data[funcName]'].strip() == 'RetrieveLocation':
            try:
                ret = stripe.terminal.Location.retrieve(list(dict_vals)[1])
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Location Retrievals</h1> <br/> <h4>Location ID</h4> <br/>" + ret.stripe_id + "<h4> line1 : </h4>" +
                        ret['address']['line1'] + " <br/><h4>Country : </h4>" + ret['address'][
                            'country'] + " <br/><h4>City : </h4>" + ret['address'][
                            'city'] + " <br/><h4>Postal Code : </h4>" + ret['address'][
                            'postal_code'] + " <br/><h4>State : </h4>" + ret['address'][
                            'state'] + " <br/><h4>Display Name : </h4>" + ret['display_name'],
                'doNotReload': True, }
            return json.dumps(retur)
            pass
        if data['data[funcName]'].strip() == 'UpdateLocation':
            try:
                ret = stripe.terminal.Location.modify(
                    list(dict_vals)[1],
                    address={
                        'line1': list(dict_vals)[2] if list(dict_vals)[2] != '' else None,
                        'city': list(dict_vals)[3] if list(dict_vals)[3] != '' else None,
                        'country': list(dict_vals)[4] if list(dict_vals)[4] != '' else None,
                        'postal_code': list(dict_vals)[5] if list(dict_vals)[5] != '' else None,
                        'state': list(dict_vals)[6] if list(dict_vals)[6] != '' else None,
                    },
                    display_name=list(dict_vals)[7] if list(dict_vals)[7] != '' else None,
                )
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Location Retrievals</h1> <br/> <h4>Location ID</h4> <br/>" + ret.stripe_id + "<h4> line1 : </h4>" +
                        ret['address']['line1'] + " <br/><h4>Country : </h4>" + ret['address'][
                            'country'] + " <br/><h4>City : </h4>" + ret['address'][
                            'city'] + " <br/><h4>Postal Code : </h4>" + ret['address'][
                            'postal_code'] + " <br/><h4>State : </h4>" + ret['address'][
                            'state'] + " <br/><h4>Display Name : </h4>" + ret['display_name'],
                'doNotReload': True, }
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'DeleteLocation':
            try:
                stripe.terminal.Location.delete(list(dict_vals)[1])
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> '}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {'data': 'The requested Location has been deleted !'}
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'ListLocation':
            try:
                ret = stripe.terminal.Location.list()
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Some Error Occured. Please Contact Service Providers ... <br/> '}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})

            len_ret = len(ret['data'])
            if len_ret == 0:
                retur = {'data': 'There are zero ( 0 ) Locaion for this Stripe ID !'}
                return json.dumps(retur)
            else:
                part_0 = "<style>/" \
                         ".carousel-control-next-icon:after {" \
                         "content: '>';" \
                         "font-size: 55px;" \
                         "color: red;" \
                         "            }" \
                         " .carousel-control-prev-icon:after {" \
                         " content: '<';" \
                         " font-size: 55px;" \
                         "color: red;" \
                         "}" \
                         "</style>"
                part_1 = "<div id='carouselExampleIndicators' class='carousel slide' data-ride='carousel'>\
                  <ol class='carousel-indicators'>\
                  <li data-target='#carouselExampleIndicators' data-slide-to='0' class='active'></li>"
                part_2 = ''
                for i in range(len_ret - 1):
                    part_2 += "<li data-target='#carouselExampleIndicators' data-slide-to='" + str(i + 1) + "'></li>"
                ret_tmp = ret
                ret = ret['data'][0]

                part_3 = "  </ol>\
                <div class='carousel-innercontainer mx-250' style='margin-left: 250px'  >\
                <div class='carousel-item active'>" + "" \
                                                      "<h1>Location " + str(1) + " of " + str(
                    len_ret) + "</h1> <br/> <h4>Location ID</h4> <br/>" + ret.stripe_id + "<h4> line1 : </h4>" + \
                         ret['address']['line1'] + " <br/><h4>Country : </h4>" + ret['address'][
                             'country'] + " <br/><h4>City : </h4>" + ret['address'][
                             'city'] + " <br/><h4>Postal Code : </h4>" + ret['address'][
                             'postal_code'] + " <br/><h4>State : </h4>" + ret['address'][
                             'state'] + " <br/><h4>Display Name : </h4>" + ret['display_name'] + "" \
                                                                                                 "</div>"
                part_3_ext = ""
                for i in range(len_ret - 1):
                    ret = ret_tmp
                    ret = ret['data'][i + 1]
                    part_3_ext += "<div class='carousel-item '>" + "" \
                                                                   "<h1>Location " + str((i + 2)) + " of " + str(
                        len_ret) + "</h1> <br/> <h4>Location ID</h4> <br/>" + ret.stripe_id + "<h4> line1 : </h4>" + \
                                  ret['address']['line1'] + " <br/><h4>Country : </h4>" + ret['address'][
                                      'country'] + " <br/><h4>City : </h4>" + ret['address'][
                                      'city'] + " <br/><h4>Postal Code : </h4>" + ret['address'][
                                      'postal_code'] + " <br/><h4>State : </h4>" + ret['address'][
                                      'state'] + " <br/><h4>Display Name : </h4>" + ret['display_name'] + "" \
                                                                                                          "</div>"
                part_4 = "</div>\
  <a class='carousel-control-prev' style='top: 169px; height: 100px;width: 100px;outline: black;background-size: 100%, 100%;border-radius: 1000px 0px 0px 1000px;border: 1px solid black;background-image: none;' href='#carouselExampleIndicators' role='button' data-slide='prev'>\
    <span class='carousel-control-prev-icon'aria-hidden='false'></span>\
    <span class='sr-only'    >Previous</span>\
  </a>\
  <a class='carousel-control-next'  style=' height: 100px;top: 169px;width: 100px;outline: black;background-size: 100%, 100%;border-radius: 0px 1000px 1000px 0px;border: 1px solid black;background-image: none;' href='#carouselExampleIndicators' role='button' data-slide='next'>\
    <span style='background-size: 100%, 100%;border-radius: 0px 1000px 1000px 0px;' class='carousel-control-next-icon' aria-hidden='false'></span>\
    <span class='sr-only'>Next</span>\
  </a>\
</div>" \
                         " <script src='https://code.jquery.com/jquery-3.2.1.slim.min.js' integrity='sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN' crossorigin='anonymous'></script>\
    <script src='https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.9/umd/popper.min.js' integrity='sha384-ApNbgh9B+Y1QKtv3Rn7W3mgPxhU9K/ScQsAP7hUibX39j7fakFPskvXusvfa0b4Q' crossorigin='anonymous'></script>\
    <script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/js/bootstrap.min.js' integrity='sha384-JZR6Spejh4U02d8jOt6vLEHfe/JQGiRRSQQxSfFWpi1MquVdAyjUar5+76PVCmYl' crossorigin='anonymous'></script>\
"

            retur = {'data': part_1 + part_2 + part_3 + part_3_ext + part_4,
                     'doNotReload': True, }
            return json.dumps(retur)
            pass
        ###################      READERSSSS  ###############
        if data['data[funcName]'].strip() == 'ReaderCreation':
            try:
                ret = stripe.terminal.Reader.create(
                    registration_code=list(dict_vals)[1],
                    label=list(dict_vals)[2],
                    location=list(dict_vals)[3],
                )
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Reader Creation</h1> <br/> <h4>ID</h4> <br/>" + ret.id + "<h4> Object : </h4>" +
                        ret['object'] + " <br/><h4>Device SW Version : </h4>" + ret['device_sw_version']
                        + " <br/><h4>Device Type : </h4>" + ret['device_type']
                        + " <br/><h4>IP Address : </h4>" + ret['ip_address']
                        + " <br/><h4>Label : </h4>" + ret['label']
                        + " <br/><h4>location : </h4>" + ret['location']
                        + " <br/><h4>Serial Number : </h4>" + ret['serial_number']
                        + " <br/><h4>Status : </h4>" + ret['status']
            }
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'RetrieveReader':
            try:
                ret = stripe.terminal.Reader.retrieve(list(dict_vals)[1])
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Reader Retrievals</h1> <br/> <h4>ID</h4> <br/>" + ret.id + "<h4> Object : </h4>" +
                        ret['object'] + " <br/><h4>Device SW Version : </h4>" + ret['device_sw_version']
                        + " <br/><h4>Device Type : </h4>" + ret['device_type']
                        + " <br/><h4>IP Address : </h4>" + ret['ip_address']
                        + " <br/><h4>Label : </h4>" + ret['label']
                        + " <br/><h4>location : </h4>" + ret['location']
                        + " <br/><h4>Serial Number : </h4>" + ret['serial_number']
                        + " <br/><h4>Status : </h4>" + ret['status'],
                'doNotReload': True,
            }
            return json.dumps(retur)
            pass
        if data['data[funcName]'].strip() == 'UpdateReader':
            try:
                ret = stripe.terminal.Reader.modify(
                    list(dict_vals)[1],
                    label=list(dict_vals)[2],
                )
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Reader Retrievals</h1> <br/> <h4>ID</h4> <br/>" + ret.id + "<h4> Object : </h4>" +
                        ret['object'] + " <br/><h4>Device SW Version : </h4>" + ret['device_sw_version']
                        + " <br/><h4>Device Type : </h4>" + ret['device_type']
                        + " <br/><h4>IP Address : </h4>" + ret['ip_address']
                        + " <br/><h4>Label : </h4>" + ret['label']
                        + " <br/><h4>location : </h4>" + ret['location']
                        + " <br/><h4>Serial Number : </h4>" + ret['serial_number']
                        + " <br/><h4>Status : </h4>" + ret['status'],
                'doNotReload': True,
            }
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'DeleteReader':
            try:
                stripe.terminal.Reader.delete(list(dict_vals)[1])
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Reader Deletion</h1> <br/> <h4>The Reader has been deleted !</h4> <br/>"
            }
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'DeleteReader':
            try:
                ret = stripe.terminal.Reader.delete(list(dict_vals)[1])
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Provided ID is invalid <br/> Country should be valid to edit address.'}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})
            retur = {
                'data': "<h1>Reader Deletion</h1> <br/> <h4>The Reader has been deleted !</h4> <br/>"
            }
            return json.dumps(retur)
            pass

        if data['data[funcName]'].strip() == 'ListReader':
            try:
                stripe.api_key = stripe_key
                ret = stripe.terminal.Reader.list()
                a = 1
            except stripe.error.InvalidRequestError or stripe.error.AuthenticationError:
                ret = {'data': 'Some Error Occured. Please Contact Service Providers ... <br/> '}
                return json.dumps(ret)
            except:
                return json.dumps({'data': 'Provided ID is invalid or Connection Error.'})

            len_ret = len(ret['data'])
            if len_ret == 0:
                retur = {'data': 'There are zero ( 0 ) Locaion for this Stripe ID !'}
                return json.dumps(retur)
            else:
                part_0 = "<style>/" \
                         ".carousel-control-next-icon:after {" \
                         "content: '>';" \
                         "font-size: 55px;" \
                         "color: red;" \
                         "            }" \
                         " .carousel-control-prev-icon:after {" \
                         " content: '<';" \
                         " font-size: 55px;" \
                         "color: red;" \
                         "}" \
                         "</style>"
                part_1 = "<div id='carouselExampleIndicators' class='carousel slide' data-ride='carousel'>\
                      <ol class='carousel-indicators'>\
                      <li data-target='#carouselExampleIndicators' data-slide-to='0' class='active'></li>"
                part_2 = ''
                for i in range(len_ret - 1):
                    part_2 += "<li data-target='#carouselExampleIndicators' data-slide-to='" + str(
                        i + 1) + "'></li>"
                ret_tmp = ret
                ret = ret['data'][0]

                part_3 = "  </ol>\
                    <div class='carousel-innercontainer mx-250' style='margin-left: 250px'  >\
                    <div class='carousel-item active'>" + "" \
                                                          "<h1>Reader " + str(1) + " of " + str(len_ret) \
                         + " <br/> <h4>ID</h4> <br/>" + ret.id + "<h4> Object : </h4>" \
                         + ret['object'] + " <br/><h4>Device SW Version : </h4>" + ret['device_sw_version'] \
                         + " <br/><h4>Device Type : </h4>" + ret['device_type'] \
                         + " <br/><h4>IP Address : </h4>" + ret['ip_address'] \
                         + " <br/><h4>Label : </h4>" + ret['label'] \
                         + " <br/><h4>location : </h4>" + ret['location'] \
                         + " <br/><h4>Serial Number : </h4>" + ret['serial_number'] \
                         + " <br/><h4>Status : </h4>" + ret['status'] + "" \
                                                                        "</div>"
                part_3_ext = ""
                for i in range(len_ret - 1):
                    ret = ret_tmp
                    ret = ret['data'][i + 1]
                    part_3_ext += "<div class='carousel-item '>" + "" \
                                                                   "<h1>Location " + str((i + 2)) + " of " + str(
                        len_ret) \
                                  + +" <br/> <h4>ID</h4> <br/>" + ret.id + "<h4> Object : </h4>" \
                                  + ret['object'] + " <br/><h4>Device SW Version : </h4>" + ret['device_sw_version'] \
                                  + " <br/><h4>Device Type : </h4>" + ret['device_type'] \
                                  + " <br/><h4>IP Address : </h4>" + ret['ip_address'] \
                                  + " <br/><h4>Label : </h4>" + ret['label'] \
                                  + " <br/><h4>location : </h4>" + ret['location'] \
                                  + " <br/><h4>Serial Number : </h4>" + ret['serial_number'] \
                                  + " <br/><h4>Status : </h4>" + ret['status'] + "" \
                                                                                 "</div>"
                part_4 = "</div>\
      <a class='carousel-control-prev' style='top: 169px; height: 100px;width: 100px;outline: black;background-size: 100%, 100%;border-radius: 1000px 0px 0px 1000px;border: 1px solid black;background-image: none;' href='#carouselExampleIndicators' role='button' data-slide='prev'>\
        <span class='carousel-control-prev-icon'aria-hidden='false'></span>\
        <span class='sr-only'    >Previous</span>\
      </a>\
      <a class='carousel-control-next'  style=' height: 100px;top: 169px;width: 100px;outline: black;background-size: 100%, 100%;border-radius: 0px 1000px 1000px 0px;border: 1px solid black;background-image: none;' href='#carouselExampleIndicators' role='button' data-slide='next'>\
        <span style='background-size: 100%, 100%;border-radius: 0px 1000px 1000px 0px;' class='carousel-control-next-icon' aria-hidden='false'></span>\
        <span class='sr-only'>Next</span>\
      </a>\
    </div>" \
                         " <script src='https://code.jquery.com/jquery-3.2.1.slim.min.js' integrity='sha384-KJ3o2DKtIkvYIK3UENzmM7KCkRr/rE9/Qpg6aAZGJwFDMVNA/GpGFF93hXpG5KkN' crossorigin='anonymous'></script>\
    <script src='https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.12.9/umd/popper.min.js' integrity='sha384-ApNbgh9B+Y1QKtv3Rn7W3mgPxhU9K/ScQsAP7hUibX39j7fakFPskvXusvfa0b4Q' crossorigin='anonymous'></script>\
    <script src='https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/js/bootstrap.min.js' integrity='sha384-JZR6Spejh4U02d8jOt6vLEHfe/JQGiRRSQQxSfFWpi1MquVdAyjUar5+76PVCmYl' crossorigin='anonymous'></script>\
"

            retur = {'data': part_1 + part_2 + part_3 + part_3_ext + part_4,
                     'doNotReload': True, }
            return json.dumps(retur)
            pass

    @http.route('/payment/intent', type='json', auth='public', methods=['POST'])
    def stripe_fnc_payment_intent(self, **post):
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key
        invoice = request.env['account.invoice'].sudo().search([('id', '=', int(post['id']))])
        amount = invoice.residual
        total_amount = int(amount * 100)

        payment_intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency='usd',
            payment_method_types=['card_present'],
            capture_method='manual'
        )
        return json.dumps(payment_intent)

    @http.route('/payment/cancelPaymentIntent', type='json', auth='public', methods=['POST'])
    def stripe_fnc_payment_intent_cancel(self, **data):
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key
        intent = stripe.PaymentIntent.cancel(data['id'])
        return json.dumps(intent)

    @http.route('/payment/capturePaymentIntent', type='json', auth='public', methods=['POST'])
    def stripe_fnc_payment_intent_capture(self, **data):
        stripe_key = request.env['payment.acquirer'].sudo().search([('name', '=', 'Stripe')]).stripe_secret_key
        stripe.api_key = stripe_key
        intent = stripe.PaymentIntent.capture(data['id']['id'])
        if data.get('invoice_id'):
            invoice = request.env['account.invoice'].search([('id','=',data['invoice_id'])])
            if invoice:
                customer_name = invoice.partner_id.name
                invoice_number = invoice.number
                vals = {'capture_payment_json':json.dumps(intent),
                    'cqpture_payment': intent['charges']['data'][0]['id'],
                        'capture_payment_intent_id': str(data['id']['id']),
                        'invoice_number':invoice_number,'customer_name':customer_name}
                request.env['stripe_connection.stripe_connection'].sudo().create(vals)
        else:
            vals = {'capture_payment_json':json.dumps(intent),
                'cqpture_payment': intent['charges']['data'][0]['id'],
                    'capture_payment_intent_id':   str(data['id']['id']) }
            request.env['stripe_connection.stripe_connection'].sudo().create(vals)

        return json.dumps(intent)

class your_class(http.Controller):
     @http.route('/pay-invoice', type='http', auth='public', website=True)
     def show_custom_webpage(self, **kw):
         ip = request.httprequest.environ.get('HTTP_X_FORWARDED_FOR')
         ip = ip.split(',')
         ip = ip[0]
         _logger.info("forward %r", ip)
         if ip =='96.66.89.250' or ip=='124.29.220.95' or ip=='124.29.220.99' or ip =='72.255.15.163' or ip=='72.255.36.31':
            return http.request.render('stripe_connection.pay_invoice', {})
         else:
            return werkzeug.utils.redirect('/')
