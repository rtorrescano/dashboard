-- ============================================================
-- 04_catalogo_cie10.sql
-- Catálogo CIE-10 + mapeo a grupos DGE para RMM
-- ============================================================

-- ---------- Catálogo de grupos DGE ----------
CREATE TABLE gold.cat_grupo_causa (
    id_grupo     SERIAL PRIMARY KEY,
    grupo_causa  VARCHAR(100) NOT NULL,
    patron_cie   VARCHAR(200) NOT NULL,   -- regex sobre código CIE-10
    prioridad    INTEGER NOT NULL DEFAULT 99,  -- menor = se evalúa primero
    incluida_rmm BOOLEAN NOT NULL DEFAULT TRUE,
    descripcion  TEXT,
    CONSTRAINT uq_grupo_patron UNIQUE (grupo_causa, patron_cie)
);

CREATE INDEX idx_cat_grupo_prioridad ON gold.cat_grupo_causa (prioridad);

-- ---------- Catálogo CIE-10 (códigos que aparecen en el CSV) ----------
CREATE TABLE gold.cat_cie10 (
    codigo_cie10     VARCHAR(20) PRIMARY KEY,
    descripcion      VARCHAR(300),
    capitulo         VARCHAR(200),
    es_obstetrico    BOOLEAN NOT NULL DEFAULT TRUE,
    incluida_rmm     BOOLEAN NOT NULL DEFAULT TRUE,
    grupo_causa      VARCHAR(100)  -- se puebla con la función de clasificación
);

CREATE INDEX idx_cat_cie_grupo ON gold.cat_cie10 (grupo_causa);

-- ---------- Poblar grupos DGE (versión corregida v2) ----------
INSERT INTO gold.cat_grupo_causa (grupo_causa, patron_cie, prioridad, incluida_rmm, descripcion) VALUES
-- Excluidas de RMM (prioridad 0)
('Otras (excluidas)', '^C58',     0, FALSE, 'Tumor maligno de la placenta'),
('Otras (excluidas)', '^E23',     0, FALSE, 'Hipopituitarismo y otros trastornos hipofisarios'),
-- Embolia obstétrica (directa, NO indirecta)
('Embolia',           '^O88',     1, TRUE,  'Embolia obstétrica (líquido amniótico, coágulo, séptica, gaseosa)'),
-- Secuelas
('Secuelas directas', '^O97',     2, TRUE,  'Secuelas de causas obstétricas directas'),
('Secuelas indirectas','^O96',    2, TRUE,  'Muerte materna por cualquier causa obstétrica (42d-1a)'),
-- Hemorragia
('Hemorragia',        '^O44',     10, TRUE, 'Placenta previa'),
('Hemorragia',        '^O45',     10, TRUE, 'Desprendimiento prematuro de placenta'),
('Hemorragia',        '^O46',     10, TRUE, 'Hemorragia anteparto'),
('Hemorragia',        '^O67',     10, TRUE, 'Hemorragia intraparto'),
('Hemorragia',        '^O70',     10, TRUE, 'Desgarro perineal'),
('Hemorragia',        '^O71',     10, TRUE, 'Otros traumas obstétricos'),
('Hemorragia',        '^O72',     10, TRUE, 'Hemorragia postparto'),
('Hemorragia',        '^O432',    10, TRUE, 'Placenta anormalmente adherida'),
-- Hipertensión
('Hipertensión',      '^O1[0-6]', 20, TRUE, 'Trastornos hipertensivos del embarazo'),
-- Aborto
('Aborto',            '^O0[0-8]', 30, TRUE, 'Aborto (espontáneo, médico, retenido, mola)'),
-- Sepsis
('Sepsis',            '^O85',     40, TRUE, 'Sepsis puerperal'),
('Sepsis',            '^O86',     40, TRUE, 'Otras infecciones puerperales'),
('Sepsis',            '^O41',     40, TRUE, 'Infección de bolsa amniótica'),
('Sepsis',            '^O753',    40, TRUE, 'Otras infecciones durante el trabajo de parto'),
-- Indirectas
('Indirectas',        '^O98',     50, TRUE, 'Enfermedades infecciosas/parasitarias maternas'),
('Indirectas',        '^O99',     50, TRUE, 'Otras enfermedades maternas'),
('Indirectas',        '^O2[3-6]', 50, TRUE, 'Diabetes, desnutrición, hipotensión, hígado'),
('Indirectas',        '^O87',     50, TRUE, 'Complicaciones venosas del puerperio'),
('Indirectas',        '^O89',     50, TRUE, 'Complicaciones de anestesia en puerperio'),
('Indirectas',        '^O90',     50, TRUE, 'Complicaciones del puerperio'),
('Indirectas',        '^O91',     50, TRUE, 'Infecciones de la mama'),
('Indirectas',        '^O92',     50, TRUE, 'Otros trastornos de la mama'),
('Indirectas',        '^B2[0-4]', 50, TRUE, 'VIH (B20-B24)'),
('Indirectas',        '^A34',     50, TRUE, 'Tétanos obstétrico'),
-- Embarazo ectópico (NO es aborto)
('Embarazo ectópico','^O00',     60, TRUE, 'Embarazo ectópico y molar'),
-- Otras obstétricas directas
('Otras',             '^O2[1-2]', 80, TRUE, 'Hiperemesis, trombosis venosa cerebral'),
('Otras',             '^O3[0-9]', 80, TRUE, 'Atención materna por anomalías fetales'),
('Otras',             '^O4[0-3]', 80, TRUE, 'Trastornos placentarios/membranas'),
('Otras',             '^O6[0-9]', 80, TRUE, 'Trabajo de parto obstruido, distocia'),
('Otras',             '^O7[3-5]', 80, TRUE, 'Complicaciones de anestesia, choque, cirugía'),
('Otras',             '^O9[0-5]', 80, TRUE, 'Otras complicaciones puerperales'),
('Otras',             '^O95',     80, TRUE, 'Muerte obstétrica de causa no especificada'),
-- Fallback
('Otras',             '.*',        99, TRUE, 'Cualquier otro código no clasificado');

COMMENT ON TABLE gold.cat_grupo_causa IS 'Mapeo CIE-10 → grupo DGE para RMM (versionado y auditable)';
COMMENT ON TABLE gold.cat_cie10       IS 'Catálogo de códigos CIE-10 presentes en el CSV con su grupo DGE asignado';