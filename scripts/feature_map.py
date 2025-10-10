
FEATURES = {
    "payee_vendor":     ["bank_account","subentity","bank_cc_num","description","extended_description"],
    "cf_account":       ["payee_vendor"],
    "dashboard_1":      ["payee_vendor"],
    "budget_owner":     ["dashboard_1"],
    "entity_qbo":       ["payee_vendor","bank_cc_num"],
    "qbo_account":      ["payee_vendor","entity_qbo"],
    "qbo_sub_account":  ["bank_cc_num","entity_qbo"],
}

TARGET = {
    "payee_vendor":     "payee_vendor",
    "cf_account":       "cf_account",
    "dashboard_1":      "dashboard_1",
    "budget_owner":     "budget_owner",
    "entity_qbo":       "entity_qbo",
    "qbo_account":      "qbo_account",
    "qbo_sub_account":  "qbo_sub_account",
}
