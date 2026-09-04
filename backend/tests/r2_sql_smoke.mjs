// Isolated PostgreSQL-compatible SQL validation; never connects to production.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.env.P0_SQL_TEST_DEPS || '.', 'package.json'));
const { PGlite } = require('@electric-sql/pglite');
const { pgcrypto } = require('@electric-sql/pglite/contrib/pgcrypto');
const db = new PGlite({ extensions: { pgcrypto } });

try {
  await db.exec(`
    CREATE ROLE anon;
    CREATE ROLE authenticated;
    CREATE SCHEMA auth;
    CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
      SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid
    $$;
    GRANT USAGE ON SCHEMA auth TO authenticated;
    ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT ALL ON TABLES TO anon, authenticated;
    CREATE TABLE documents (id uuid PRIMARY KEY, user_id uuid, file_key text, status text);
    CREATE TABLE document_text(document_id uuid REFERENCES documents ON DELETE CASCADE);
    CREATE POLICY legacy_allow_all ON documents FOR ALL TO authenticated USING (true) WITH CHECK (true);
    INSERT INTO documents VALUES
      ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000011','private-a','processed'),
      ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000012','private-b','processed');
  `);
  const migration = readFileSync(new URL('../db/migrations/010_r2_lifecycle_security.sql', import.meta.url), 'utf8');
  await db.exec(migration);
  await db.exec(migration);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM documents')).rows[0].n, 2);
  const grants = (await db.query(`
    SELECT has_table_privilege('anon','documents','SELECT') AS anon,
           has_table_privilege('authenticated','r2_deletion_jobs','DELETE') AS client_delete
  `)).rows[0];
  assert.equal(grants.anon, false);
  assert.equal(grants.client_delete, false);
  await db.exec('CREATE TABLE public.future_private (id integer)');
  assert.equal((await db.query("SELECT has_table_privilege('anon','future_private','SELECT') AS allowed")).rows[0].allowed, false);
  await db.exec(`
    GRANT SELECT ON documents TO authenticated;
    SET ROLE authenticated;
    SET request.jwt.claim.sub='00000000-0000-0000-0000-000000000011';
  `);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM documents')).rows[0].n, 1);
  await db.exec('RESET ROLE');

  // Use the backend's exact parameterized SQL, not rewritten query equivalents.
  const service = readFileSync(new URL('../app/services/r2_lifecycle_service.py', import.meta.url), 'utf8');
  const queryFor = (name) => {
    const start = service.indexOf(`async def ${name}(`);
    assert.notEqual(start, -1);
    return service.slice(start).match(/"""([\s\S]*?)"""/)[1];
  };
  const params = [
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000011',
    'private-a', 'user_delete',
  ];
  const job = (await db.query(queryFor('enqueue_deletion_job'), params)).rows[0];
  assert.equal((await db.query(queryFor('claim_due_deletion_jobs'), [1, 900])).rows.length, 1);
  const duplicate = (await db.query(queryFor('enqueue_deletion_job'), params)).rows[0];
  assert.equal(duplicate.status, 'processing');
  assert.equal(duplicate.attempt_count, 1);
  assert.equal((await db.query(queryFor('claim_deletion_job'), [job.id, 900])).rows.length, 0);
  const otherOwner = [...params];
  otherOwner[1] = '00000000-0000-0000-0000-000000000012';
  assert.equal((await db.query(queryFor('enqueue_deletion_job'), otherOwner)).rows.length, 0);
  await db.query(queryFor('_fail_deletion_job'), [job.id, 'TimeoutError', 30, 1]);
  assert.equal((await db.query(queryFor('claim_due_deletion_jobs'), [1, 900])).rows.length, 0);

  console.log('PASS: repeatable migration, preserved rows, RLS/grants, future-table defaults, ownership guard, queue SQL, lease preservation and retry backoff.');
} finally {
  await db.close();
}
