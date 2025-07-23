import os

import yaml

from app.utils.database import AsyncSessionLocal, SettingDefinition, db


async def create_settings_definitions_if_not_exists():
    async with AsyncSessionLocal() as session:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "initial_settings.yaml"
        )
        with open(path, encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        for setting in settings:
            exists = await session.scalar(
                db.select(SettingDefinition).where(
                    SettingDefinition.key == setting["key"]
                )
            )
            if not exists:
                session.add(SettingDefinition(**setting))

        await session.commit()
