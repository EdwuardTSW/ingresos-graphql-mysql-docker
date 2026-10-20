-- Verificacion en MySQL. Debe coincidir con la matriz del documento.
-- Como ejecutarlo (PowerShell, con Docker corriendo):
--   Get-Content consultas\verificacion.sql -Raw | docker compose exec -T db sh -c 'MYSQL_PWD=$MYSQL_ROOT_PASSWORD mysql -t -u root ingresos'

SELECT id, code, name, is_active FROM roles ORDER BY id;           -- 4 filas
SELECT id, code, name, is_active FROM permissions ORDER BY id;     -- 10 filas

-- Matriz: filas = permisos, columnas = roles (1 = el rol tiene el permiso activo)
SELECT p.code AS permiso,
  MAX(CASE WHEN r.code='ADMINISTRADOR' AND rp.is_active = 1 THEN 1 ELSE 0 END) AS ADMINISTRADOR,
  MAX(CASE WHEN r.code='CONTADOR'      AND rp.is_active = 1 THEN 1 ELSE 0 END) AS CONTADOR,
  MAX(CASE WHEN r.code='CAPTURISTA'    AND rp.is_active = 1 THEN 1 ELSE 0 END) AS CAPTURISTA,
  MAX(CASE WHEN r.code='CONSULTA'      AND rp.is_active = 1 THEN 1 ELSE 0 END) AS CONSULTA
FROM permissions p
LEFT JOIN role_permissions rp ON rp.permission_id = p.id
LEFT JOIN roles r ON r.id = rp.role_id
GROUP BY p.id, p.code
ORDER BY p.id;

-- Contenido crudo de role_permissions (26 filas con la matriz inicial)
SELECT rp.id, r.code AS rol, p.code AS permiso, rp.is_active
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
ORDER BY r.id, p.id;

SELECT COUNT(*) AS total_roles FROM roles;   -- 4, tambien despues de reiniciar

-- Un solo rol activo por membresia (debe devolver 0 filas)
SELECT company_user_id, COUNT(*) AS roles_activos
FROM company_user_roles WHERE is_active = 1
GROUP BY company_user_id HAVING COUNT(*) > 1;

-- Historial de roles de cada membresia (capturista -> contador deja una fila inactiva)
SELECT cur.id, cur.company_user_id, r.code AS rol, cur.is_active
FROM company_user_roles cur JOIN roles r ON r.id = cur.role_id
ORDER BY cur.company_user_id, cur.id;

-- Movimientos (el rechazado por permiso no debe aparecer)
SELECT id, company_id, account_id, company_user_id, type, amount, description FROM transactions;
