from typing import List, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.models.pharmacy import District, Road, LPU, Doctor, Medication

class PharmacyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_districts_by_region(self, region_code: str) -> List[District]:
        """Получает список районов для конкретного региона"""
        stmt = select(District).where(District.region == region_code).order_by(District.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
        """Получает объекты (Аптеки/ЛПУ) привязанные к уникальному road_id"""
        stmt = select(LPU).where(LPU.road_id == road_id).order_by(LPU.pharmacy_name)
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

    async def get_preps(self) -> List[Medication]:
        stmt = select(Medication).order_by(Medication.prep)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())