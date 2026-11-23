-- Runs once, when the Docker volume is first created.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Read-only role used by the guarded SQL tool. SELECT grants on the two
-- tables are given in an `energy` migration (tables don't exist yet here).
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'wattwhere_ro') THEN
    CREATE ROLE wattwhere_ro LOGIN PASSWORD 'wattwhere_ro';
  END IF;
END
$$;
GRANT CONNECT ON DATABASE wattwhere TO wattwhere_ro;
ALTER ROLE wattwhere_ro SET default_transaction_read_only = on;
