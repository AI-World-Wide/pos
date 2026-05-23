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
    "admin_pin_required": "أدخل رقم المدير السري",

    # Floor plan / Tables
    "floor_plan": "خريطة الطاولات",
    "tables": "الطاولات",
    "table": "طاولة",
    "areas": "المناطق",
    "add_area": "إضافة منطقة",
    "add_table": "إضافة طاولة",
    "edit_table": "تعديل طاولة",
    "delete_table": "حذف طاولة",
    "table_number": "رقم الطاولة",
    "table_capacity": "السعة",
    "table_status_free": "فارغة",
    "table_status_occupied": "مشغولة",
    "table_status_reserved": "محجوزة",
    "open_table": "فتح الطاولة",
    "close_table": "إغلاق الطاولة",
    "move_table": "نقل الطاولة",
    "move_to": "نقل إلى",
    "split_items": "تقسيم الأصناف",
    "split_to_table": "تقسيم إلى طاولة",
    "partial_pay": "دفع جزئي",
    "select_items": "اختر الأصناف",
    "selected_items": "الأصناف المختارة",
    "confirm_split": "تأكيد التقسيم",
    "confirm_move": "تأكيد النقل",
    "credit_area": "الآجل",
    "total_credit": "إجمالي الآجل",
    "credit_tables": "طاولات الآجل",
    "no_tables": "لا توجد طاولات",

    # Shift / Day open-close
    "shift": "الوردية",
    "open_day": "فتح اليوم",
    "close_day": "إغلاق اليوم",
    "day_is_open": "اليوم مفتوح",
    "day_is_closed": "اليوم مغلق",
    "opening_cash": "النقد الافتتاحي",
    "closing_cash": "النقد الختامي",
    "shift_summary": "ملخص الوردية",
    "confirm_close": "تأكيد إغلاق اليوم",
    "day_opened_at": "وقت الفتح",
    "day_closed_at": "وقت الإغلاق",
    "shift_sales": "مبيعات الوردية",
    "shift_orders": "طلبات الوردية",
    "cannot_close_open_tables": "لا يمكن إغلاق اليوم مع وجود طاولات مفتوحة",

    # Enhanced analytics
    "analytics": "التحليلات",
    "revenue": "الإيرادات",
    "profit_margin": "هامش الربح",
    "peak_hours": "ساعات الذروة",
    "avg_items_per_order": "متوسط الأصناف لكل طلب",
    "payment_methods": "طرق الدفع",
    "cash_payments": "مدفوعات نقدية",
    "card_payments": "مدفوعات بطاقة",
    "credit_payments": "مدفوعات آجلة",
    "busiest_day": "أكثر يوم نشاطاً",
    "slowest_hour": "أبطأ ساعة",
    "repeat_items": "الأصناف المتكررة",
    "category_breakdown": "تفصيل الفئات",
    "daily_trend": "الاتجاه اليومي",
    "orders_sheet": "سجل الطلبات",
    "orders_sheet_desc": "جميع الطلبات",
    "export_orders_csv": "تصدير السجل CSV",
    "email_orders_sheet": "إرسال السجل بالبريد",
    "status": "الحالة",
    "status_open": "مفتوح",
    "status_sent": "تم الإرسال",
    "status_settled": "مدفوع",
    "status_voided": "ملغي",
    "open_time": "وقت الفتح",
    "close_time": "وقت الإغلاق",

    # Email / OAuth
    "email_settings": "إعدادات البريد الإلكتروني",
    "gmail_oauth": "ربط حساب Gmail",
    "email_connected": "البريد متصل",
    "email_not_connected": "البريد غير متصل",
    "connect_gmail": "ربط Gmail",
    "disconnect_gmail": "قطع اتصال Gmail",
    "email_recipients": "المستلمون",
    "add_recipient": "إضافة مستلم",
    "report_schedule": "جدول التقارير",
    "report_on_close": "إرسال عند إغلاق اليوم",
    "report_daily": "إرسال يومي",
    "report_content": "محتوى التقرير",
    "include_sales_summary": "ملخص المبيعات",
    "include_top_items": "الأصناف الأكثر مبيعاً",
    "include_category_breakdown": "تفصيل الفئات",
    "include_cashier_breakdown": "تفصيل الكاشير",
    "include_hourly_breakdown": "تفصيل الساعات",
    "include_credit_summary": "ملخص الآجل",
    "send_test_email": "إرسال بريد تجريبي",
    "send_report": "إرسال التقرير",
    "send_report_for": "إرسال تقرير لفترة",
    "last_week": "الأسبوع الماضي",
    "last_month": "الشهر الماضي",
    "email_sent": "تم إرسال البريد",
    "email_failed": "فشل إرسال البريد",

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
