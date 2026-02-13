import sqlite3

# Укажи путь к своей базе pharmacy.db
DB_PATH = "./db/models/pharmacy.db"  # Или полный путь, если она лежит глубоко


def migrate():
    print(f"🔧 Начинаю миграцию {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Проверяем, есть ли уже колонка region
        cursor.execute("PRAGMA table_info(districts)")
        columns = [info[1] for info in cursor.fetchall()]

        if "region" in columns:
            print("✅ Колонка 'region' уже существует. Пропускаю.")
        else:
            # 2. Добавляем колонку region
            print("🛠 Добавляю колонку 'region'...")
            # DEFAULT 'АЛА' означает, что все старые записи станут алматинскими
            cursor.execute("ALTER TABLE districts ADD COLUMN region TEXT DEFAULT 'АЛА'")
            conn.commit()
            print("✅ Успешно! Все текущие районы помечены как 'АЛА'.")

        conn.close()
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")


if __name__ == "__main__":
    migrate()