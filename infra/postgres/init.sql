CREATE EXTENSION IF NOT EXISTS vector;

DO $role_bootstrap$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesys_migration') THEN
        CREATE ROLE thesys_migration
            LOGIN PASSWORD 'thesys-migration-local'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION BYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesys_api') THEN
        CREATE ROLE thesys_api
            LOGIN PASSWORD 'thesys-api-local'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesys_worker') THEN
        CREATE ROLE thesys_worker
            LOGIN PASSWORD 'thesys-worker-local'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesys_readonly') THEN
        CREATE ROLE thesys_readonly
            LOGIN PASSWORD 'thesys-readonly-local'
            NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
END
$role_bootstrap$;

ALTER ROLE thesys_migration
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION BYPASSRLS;
ALTER ROLE thesys_api
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE thesys_worker
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
ALTER ROLE thesys_readonly
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO thesys_migration;
GRANT USAGE, CREATE ON SCHEMA public TO thesys_migration;
GRANT USAGE ON SCHEMA public TO thesys_api, thesys_worker, thesys_readonly;

DO $database_grants$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO thesys_migration, thesys_api, thesys_worker, thesys_readonly',
        current_database()
    );
END
$database_grants$;
