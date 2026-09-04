// Test the audit against deliberately insecure fixtures in a disposable database.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.env.P0_SQL_TEST_DEPS || '.', 'package.json'));
const { PGlite } = require('@electric-sql/pglite');
const db = new PGlite();
const source = readFileSync(new URL('../app/services/security_audit_service.py', import.meta.url), 'utf8');
const sql = name => {
  const match = source.match(new RegExp(`${name} = """([\\s\\S]*?)"""`));
  assert(match, `Missing ${name}`);
  return match[1];
};

try {
  await db.exec(`
    CREATE ROLE anon;
    CREATE ROLE authenticated;
    CREATE TABLE documents(id integer, secret text);
    ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
    CREATE VIEW leaked_view AS SELECT secret FROM documents;
    GRANT SELECT ON leaked_view TO PUBLIC;
    GRANT SELECT (secret) ON documents TO authenticated;
    CREATE FUNCTION private_definer() RETURNS integer LANGUAGE SQL SECURITY DEFINER AS 'SELECT 1';
    CREATE FUNCTION trigger_only() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS 'BEGIN RETURN NEW; END';
    ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT SELECT ON TABLES TO PUBLIC;
    CREATE TABLE r2_deletion_jobs(status text, created_at timestamptz, updated_at timestamptz);
    INSERT INTO r2_deletion_jobs VALUES
      ('pending', now() - interval '20 minutes', now()),
      ('processing', now() - interval '30 minutes', now() - interval '16 minutes'),
      ('completed', now() - interval '7 days', now());
  `);
  const rows = (await db.query(sql('RELATIONS_SQL'))).rows;
  assert(rows.find(row => row.relname === 'documents').client_access, 'Column-only privilege must be detected');
  assert(rows.find(row => row.relname === 'leaked_view').client_access, 'PUBLIC view privilege must be detected');
  assert.equal(Object.values((await db.query(sql('DEFINERS_SQL'))).rows[0])[0], 1);
  assert(Object.values((await db.query(sql('DEFAULT_GRANTS_SQL'))).rows[0])[0] > 0);
  const backlog = (await db.query(sql('BACKLOG_SQL'))).rows[0];
  assert.equal(backlog.pending, 2);
  assert.equal(backlog.stale_processing, 1);
  assert(backlog.oldest_seconds >= 1800 && backlog.oldest_seconds < 1900);
  await db.exec(`
    REVOKE SELECT (secret) ON documents FROM authenticated;
    REVOKE SELECT ON leaked_view FROM PUBLIC;
    REVOKE ALL ON FUNCTION private_definer() FROM PUBLIC;
    ALTER DEFAULT PRIVILEGES FOR ROLE postgres REVOKE SELECT ON TABLES FROM PUBLIC;
  `);
  assert.equal((await db.query(sql('RELATIONS_SQL'))).rows.find(row => row.relname === 'documents').client_access, false);
  assert.equal(Object.values((await db.query(sql('DEFINERS_SQL'))).rows[0])[0], 0);
  assert.equal(Object.values((await db.query(sql('DEFAULT_GRANTS_SQL'))).rows[0])[0], 0);
  console.log('PASS: effective column/PUBLIC view grants, default privileges, callable definers, backlog age and stale jobs.');
} finally {
  await db.close();
}
