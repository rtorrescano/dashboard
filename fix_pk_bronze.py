from django.db import connection

cur = connection.cursor()

# 1. Soltar FK de silver (silver está vacía, no hay riesgo)
cur.execute("""
    ALTER TABLE silver.silver_mortalidad_limpia
      DROP CONSTRAINT IF EXISTS silver_mortalidad_limpia_id_carga_origen_fkey
""")
print("FK silver → bronze dropeada")

# 2. Soltar PK antigua (id_carga sola)
cur.execute("""
    ALTER TABLE bronze.bronze_mortalidad_raw
      DROP CONSTRAINT IF EXISTS bronze_mortalidad_raw_pkey
""")
print("PK antigua dropeada")

# 3. Crear PK compuesta (id_carga, fila_origen)
cur.execute("""
    ALTER TABLE bronze.bronze_mortalidad_raw
      ADD PRIMARY KEY (id_carga, fila_origen)
""")
print("PK compuesta (id_carga, fila_origen) creada")

# 4. Limpiar huérfanas de intentos fallidos
cur.execute("DELETE FROM bronze.bronze_mortalidad_raw")
print(f"bronze_mortalidad_raw filas borradas: {cur.rowcount}")

cur.execute("DELETE FROM bronze.control_cargas")
print(f"control_cargas filas borradas: {cur.rowcount}")

cur.execute("ALTER SEQUENCE bronze.control_cargas_id_carga_seq RESTART WITH 1")
print("secuencia reiniciada a 1")

# 5. Verificación
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'bronze.bronze_mortalidad_raw'::regclass
      AND contype IN ('p','u')
""")
print("\nConstraints finales en bronze.bronze_mortalidad_raw:")
for r in cur.fetchall():
    print(" ", r)

print("\nOK")