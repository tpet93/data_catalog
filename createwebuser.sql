-- createwebuser.sql
\! clear
\set ECHO all
---
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'webuser') THEN
        CREATE USER webuser WITH PASSWORD 'arbormeta web user';
   END IF;
END
$$;
GRANT CONNECT ON DATABASE catalog TO webuser;
---
\c catalog
---
GRANT USAGE ON SCHEMA public TO webuser;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO webuser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO webuser;
---
