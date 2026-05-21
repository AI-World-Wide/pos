# -*- coding: utf-8 -*-
"""Seed default areas and tables.

Areas:
- 3 regular areas (15 tables each): الصالة الداخلية, الصالة الخارجية, الطابق العلوي
- 1 Cabins area (6 cabins): الكبائن
- 1 Credit area (special, for unpaid): الآجل
"""
from __future__ import annotations

from src.models import Area, FloorTable

DEFAULT_AREAS = [
    {"name_en": "Area 1", "name_ar": "منطقة 1", "sort_order": 1, "tables": 15},
    {"name_en": "Area 2", "name_ar": "منطقة 2", "sort_order": 2, "tables": 15},
    {"name_en": "Area 3", "name_ar": "منطقة 3", "sort_order": 3, "tables": 15},
    {"name_en": "Cabins", "name_ar": "الكبائن", "sort_order": 4, "tables": 6},
    {"name_en": "Credit", "name_ar": "الآجل", "sort_order": 99, "tables": 0, "is_credit": True},
]


def seed_areas_and_tables(session) -> None:
    existing = {a.name_en for a in session.query(Area).all()}
    for area_def in DEFAULT_AREAS:
        if area_def["name_en"] in existing:
            continue
        area = Area(
            name_en=area_def["name_en"],
            name_ar=area_def["name_ar"],
            sort_order=area_def["sort_order"],
            is_credit=area_def.get("is_credit", False),
            visible=True,
        )
        session.add(area)
        session.flush()

        for i in range(1, area_def["tables"] + 1):
            session.add(FloorTable(
                area_id=area.id,
                number=i,
                label_ar=str(i),
                capacity=4 if area_def["name_en"] != "Cabins" else 8,
                status="free",
                visible=True,
            ))
