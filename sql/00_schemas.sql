-- ============================================================
-- 00_schemas.sql
-- Creación de esquemas del data lake
-- ============================================================
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

COMMENT ON SCHEMA bronze IS 'Capa raw: datos tal como llegan del CSV, todo TEXT, sin transformación';
COMMENT ON SCHEMA silver IS 'Capa limpia: tipado, deduplicado, validado, con trazabilidad a bronze';
COMMENT ON SCHEMA gold   IS 'Capa analítica: modelo estrella para RMM';
