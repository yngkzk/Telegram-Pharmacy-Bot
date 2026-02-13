from typing import List, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.models.pharmacy import District, Road, LPU, Doctor, Medication, Apothecary, MainSpec

class PharmacyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_districts_by_region(self, region_code: str) -> List[District]:
        """Получает список районов для конкретного региона"""
        stmt = select(District).where(District.region == region_code).order_by(District.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_district_by_id(self, district_id: int) -> Optional[District]:
        """
        🔥 ЭТОГО МЕТОДА НЕ ХВАТАЛО
        Находит район по ID (нужно для получения имени в отчет)
        """
        stmt = select(District).where(District.id == district_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_road_id_by_data(self, district_id: int, road_num: int) -> Optional[int]:
        """
        Ищет road_id по ID района и номеру маршрута.
        Тут мы учитываем, что в таблице 'roads' колонка 'district_name' на самом деле хранит ID.
        """
        stmt = select(Road.road_id).where(
            Road.district_name == district_id, # district_name в базе — это ID
            Road.road_num == road_num
        )
        result = await self.session.execute(stmt)
        return result.scalar()

    async def get_lpus_by_road(self, road_id: int) -> List[LPU]:
        """Для раздела ВРАЧЕЙ (таблица lpu)"""
        stmt = select(LPU).where(LPU.road_id == road_id).order_by(LPU.pharmacy_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_apothecaries_by_road(self, road_id: int) -> List[Apothecary]:
        """Для раздела АПТЕК (таблица apothecary)"""
        stmt = select(Apothecary).where(Apothecary.road_id == road_id).order_by(Apothecary.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # --- Дополнительные хелперы ---
    async def get_doctors_by_lpu(self, lpu_id: int) -> List[Doctor]:
        stmt = select(Doctor).where(Doctor.lpu_id == lpu_id).order_by(Doctor.doctor)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_doctor_by_id(self, doc_id: int) -> Optional[Doctor]:
        stmt = select(Doctor).where(Doctor.id == doc_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_spec_name(self, spec_id: int) -> str:
        """
        🔥 ЭТОГО ТОЖЕ НЕ БЫЛО
        Получает название специальности.
        """
        sql = """
            SELECT ms.spec 
            FROM specs s
            JOIN main_specs ms ON s.ms_id = ms.main_spec_id
            WHERE s.spec_id = :sid
        """
        result = await self.session.execute(text(sql), {"sid": spec_id})
        row = result.fetchone()
        return row[0] if row else "Не указано"

    async def get_preps(self) -> List[Medication]:
        stmt = select(Medication).order_by(Medication.prep)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ==================================================
    # ✍️ МЕТОДЫ ДОБАВЛЕНИЯ (WRITE)
    # ==================================================

    async def add_lpu(self, road_id: int, name: str, url: str = None) -> LPU:
        """Добавляет новое ЛПУ"""
        new_lpu = LPU(road_id=road_id, pharmacy_name=name, pharmacy_url=url)
        self.session.add(new_lpu)
        await self.session.commit()
        return new_lpu

    async def add_apothecary(self, road_id: int, name: str, url: str = None) -> Apothecary:
        """Добавляет новую Аптеку"""
        new_apt = Apothecary(road_id=road_id, name=name, url=url)
        self.session.add(new_apt)
        await self.session.commit()
        return new_apt

    async def add_doctor(self, lpu_id: int, name: str, spec: str, phone: str = None) -> Doctor:
        """Добавляет нового Врача"""
        new_doc = Doctor(lpu_id=lpu_id, doctor=name, spec=spec, phone=phone)
        self.session.add(new_doc)
        await self.session.commit()
        return new_doc

    async def get_all_specs(self):
        stmt = select(MainSpec).order_by(MainSpec.spec)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_or_create_spec_id(self, spec_name: str) -> int:
        # Очищаем ввод (Убираем пробелы, делаем первую заглавной)
        clean_name = spec_name.strip().capitalize()

        # Ищем, есть ли такая уже (игнорируя регистр)
        stmt = select(MainSpec).where(func.lower(MainSpec.spec) == clean_name.lower())
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing.id

        new_spec = MainSpec(spec=clean_name)
        self.session.add(new_spec)
        await self.session.commit()
        return new_spec.id

    async def add_doctor(self, lpu_id: int, name: str, spec_id: int, numb: str = None) -> Doctor:
        new_doc = Doctor(lpu_id=lpu_id, doctor=name, spec_id=spec_id, numb=numb)
        self.session.add(new_doc)
        await self.session.commit()
        return new_doc