// Copyright (c) 2025, Hybrowlabs Pvt Ltd and contributors
// For license information, please see license.txt
frappe.ui.form.on('FR Profit And Loss Template', {
    setup(frm){
        frm.set_query('account', 'profit_and_loss_template_details', function() {
            return {
                filters: {
                    "template_type": "Profit & Loss",
                }
            };
        });
    },
});