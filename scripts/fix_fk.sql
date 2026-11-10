-- Corrige la FK rota en la tabla 'mensajes'
ALTER TABLE mensajes DROP CONSTRAINT IF EXISTS mensajes_chat_id_fkey;
ALTER TABLE mensajes DROP CONSTRAINT IF EXISTS mensajes_trueque_id_fkey;
ALTER TABLE mensajes ADD CONSTRAINT mensajes_trueque_id_fkey
    FOREIGN KEY (trueque_id) REFERENCES trueques(id) ON DELETE CASCADE;

-- Verificar resultado
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'mensajes'::regclass AND contype = 'f';

-- Marcar migración alembic como aplicada
UPDATE alembic_version SET version_num = 'a1b2c3d4e5f6'
WHERE version_num = '9d0e1f2a3b4c';

SELECT version_num FROM alembic_version;
