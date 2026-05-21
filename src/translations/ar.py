# -*- coding: utf-8 -*-
"""Single source of truth for Arabic UI strings.

Templates must NEVER hardcode Arabic. Reference strings as `t.<key>` after
the dictionary is exposed as a Jinja global in app.py.
"""

T = {
    # App-level
    "app_title": "نقطة البيع",
    "cafe_name_default": "مقهى",

    # Navigation / shell
    "back": "رجوع",
    "home": "الرئيسية",
    "categories": "الفئات",
    "items": "الأصناف",
    "settings": "الإعدادات",
    "reports": "التقارير",

    # Cashier screen (Phase 2)
    "current_order": "الطلب الحالي",
    "qty": "الكمية",
    "item": "الصنف",
    "price": "السعر",
    "subtotal": "المجموع الفرعي",
    "vat_5": "ضريبة القيمة المضافة 5%",
    "total": "الإجمالي",
    "currency": "AED",

    # Action bar (Phase 2)
    "hold": "تعليق",
    "delete": "حذف",
    "cancel": "إلغاء",
    "pay": "دفع",
    "send": "إرسال",

    # Payment modal (Phase 3)
    "cash_received": "المدفوع نقداً",
    "change_due": "المتبقي",
    "confirm": "تأكيد",

    # Receipt (Phase 3)
    "receipt_thanks_1": "شكراً لزيارتكم",
    "receipt_thanks_2": "نتطلع لزيارتكم مجدداً",
    "receipt_date": "التاريخ",
    "receipt_number": "فاتورة رقم",
    "receipt_cashier": "الكاشير",
    "receipt_trn": "الرقم الضريبي",

    # Items count
    "items_count": "صنفاً",
    "no_items": "لا توجد أصناف",

    # Order
    "new_order": "طلب جديد",
    "order_empty": "لا توجد أصناف في الطلب",
    "order_number": "رقم الطلب",
    "order_status_open": "مفتوح",
    "order_status_sent": "تم الإرسال",
    "order_status_settled": "تم الدفع",
    "order_status_voided": "ملغي",

    # Payment
    "payment_title": "الدفع",
    "payment_cash": "نقدي",
    "payment_card": "بطاقة",
    "payment_amount": "المبلغ المدفوع",
    "payment_change": "المتبقي",
    "payment_confirm": "تأكيد الدفع",
    "payment_cancel": "إلغاء",
    "payment_success": "تم الدفع بنجاح",
    "payment_exact": "المبلغ المحدد",

    # Kitchen
    "sent_to_kitchen": "تم الإرسال للمطبخ",
    "nothing_to_send": "لا توجد أصناف جديدة للإرسال",

    # Hold
    "held_orders": "الطلبات المعلقة",
    "no_held_orders": "لا توجد طلبات معلقة",
    "resume": "استئناف",

    # Login
    "login_title": "تسجيل الدخول",
    "enter_pin": "أدخل الرقم السري",
    "login": "دخول",
    "logout": "خروج",
    "wrong_pin": "الرقم السري غير صحيح",
    "select_user": "اختر المستخدم",

    # Back office
    "back_office": "لوحة التحكم",
    "item_management": "إدارة الأصناف",
    "add_item": "إضافة صنف",
    "edit_item": "تعديل صنف",
    "delete_item": "حذف صنف",
    "save": "حفظ",
    "cancel_edit": "إلغاء",
    "item_name_ar": "اسم الصنف بالعربية",
    "item_name_en": "اسم الصنف بالإنجليزية",
    "item_price": "السعر",
    "item_category": "الفئة",
    "item_station": "المحطة",
    "item_visible": "ظاهر",
    "import_xlsx": "استيراد من إكسل",
    "import_success": "تم الاستيراد بنجاح",

    # Reports
    "reports_title": "التقارير",
    "today": "اليوم",
    "yesterday": "أمس",
    "this_week": "هذا الأسبوع",
    "this_month": "هذا الشهر",
    "custom_range": "فترة مخصصة",
    "total_sales": "إجمالي المبيعات",
    "vat_collected": "الضريبة المحصلة",
    "order_count": "عدد الطلبات",
    "top_items": "الأصناف الأكثر مبيعاً",
    "export_csv": "تصدير CSV",
    "sales_by_category": "المبيعات حسب الفئة",
    "sales_by_hour": "المبيعات حسب الساعة",
    "sales_by_cashier": "المبيعات حسب الكاشير",
    "avg_order_value": "متوسط قيمة الطلب",
    "no_data": "لا توجد بيانات",

    # Settings
    "settings_title": "الإعدادات",
    "cafe_name": "اسم المقهى",
    "tax_number": "الرقم الضريبي",
    "vat_rate": "نسبة الضريبة",
    "printer_settings": "إعدادات الطابعة",
    "printer_name": "اسم الطابعة",
    "printer_purpose": "الغرض",
    "printer_receipt": "إيصال",
    "printer_kitchen": "مطبخ",
    "printer_shisha": "شيشة",
    "discover_printers": "البحث عن الطابعات",
    "no_printers": "لم يتم العثور على طابعات",
    "kick_code": "كود فتح الدرج",
    "smtp_settings": "إعدادات البريد",
    "smtp_host": "خادم البريد",
    "smtp_port": "المنفذ",
    "smtp_user": "اسم المستخدم",
    "smtp_pass": "كلمة المرور",
    "smtp_from": "البريد المرسل",
    "smtp_to": "البريد المستقبل",
    "owner_email": "بريد المالك",
    "save_settings": "حفظ الإعدادات",
    "settings_saved": "تم حفظ الإعدادات",
    "test_print": "طباعة تجريبية",
    "logo_upload": "رفع الشعار",

    # Users
    "user_management": "إدارة المستخدمين",
    "user_name": "اسم المستخدم",
    "user_role": "الدور",
    "user_pin": "الرقم السري",
    "role_admin": "مدير",
    "role_cashier": "كاشير",
    "role_waiter": "نادل",
    "permissions": "الصلاحيات",
    "perm_take_order": "أخذ الطلبات",
    "perm_send_kitchen": "إرسال للمطبخ",
    "perm_take_payment": "استلام الدفع",
    "perm_void_line": "إلغاء صنف",
    "perm_apply_discount": "تطبيق خصم",
    "perm_view_reports": "عرض التقارير",
    "perm_edit_items": "تعديل الأصناف",
    "perm_manage_users": "إدارة المستخدمين",
    "perm_manage_settings": "إدارة الإعدادات",
    "perm_manage_printers": "إدارة الطابعات",

    # Category Arabic names (locked, used by importer)
    "cat_offers": "العروض",
    "cat_soft_drinks": "مشروبات غازية",
    "cat_hot_drinks": "مشروبات ساخنة",
    "cat_juice": "عصائر",
    "cat_shisha": "شيشة",
    "cat_extra": "إضافات",
}


# English -> Arabic category name map, used by the XLSX importer.
CATEGORY_AR_NAMES = {
    "Offers": T["cat_offers"],
    "Soft Drinks": T["cat_soft_drinks"],
    "Hot Drinks": T["cat_hot_drinks"],
    "Juice": T["cat_juice"],
    "Shisha": T["cat_shisha"],
    "Extra": T["cat_extra"],
}

# Sort order matches the brief's section ordering.
CATEGORY_SORT_ORDER = {
    "Offers": 10,
    "Soft Drinks": 20,
    "Hot Drinks": 30,
    "Juice": 40,
    "Shisha": 50,
    "Extra": 60,
}

# is_beverage=1 means: NEVER goes to the kitchen ticket, prints on receipt only.
CATEGORY_IS_BEVERAGE = {
    "Offers": 0,
    "Soft Drinks": 1,
    "Hot Drinks": 1,
    "Juice": 1,
    "Shisha": 0,
    "Extra": 0,
}
