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

    # Phase 1 placeholder messages
    "phase1_heading": "نقطة البيع",
    "phase1_subheading": "النموذج الأولي - عرض الفئات والأصناف",
    "phase1_items_count": "صنفاً",
    "phase1_no_items": "لا توجد أصناف",
    "phase1_back_to_categories": "العودة إلى الفئات",

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
