// Uses a disposable PostgreSQL-compatible engine, never a production database.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const require = createRequire(resolve(process.env.P0_SQL_TEST_DEPS || '.', 'package.json'));
const { PGlite } = require('@electric-sql/pglite');
const db = new PGlite();
try {
  const userA = '00000000-0000-0000-0000-000000000011';
  const userB = '00000000-0000-0000-0000-000000000012';
  await db.exec(`
    CREATE ROLE anon;
    CREATE ROLE authenticated;
    CREATE SCHEMA auth;
    CREATE TABLE auth.users(id uuid PRIMARY KEY);
    INSERT INTO auth.users VALUES ('${userA}'), ('${userB}');
  `);
  const migration = readFileSync(new URL('../db/migrations/011_document_processing_limits.sql', import.meta.url), 'utf8');
  await db.exec(migration);
  await db.exec(migration);
  assert.equal((await db.query("SELECT relrowsecurity FROM pg_class WHERE oid = 'document_processing_limits'::regclass")).rows[0].relrowsecurity, true);
  assert.equal((await db.query("SELECT has_table_privilege('authenticated','document_processing_limits','UPDATE') AS allowed")).rows[0].allowed, false);
  const service = readFileSync(new URL('../app/services/document_security_service.py', import.meta.url), 'utf8');
  const sql = service.match(/"""([\s\S]*?)"""/)[1];
  const hits = await Promise.all(Array.from({ length: 12 }, () => db.query(sql, [userA, 5, 600])));
  assert.equal(hits.filter(result => result.rows[0].allowed).length, 5);
  const state = (await db.query('SELECT request_count, expires_at FROM document_processing_limits WHERE user_id=$1', [userA])).rows[0];
  assert.equal(state.request_count, 6);
  const denied = (await db.query(sql, [userA, 5, 600])).rows[0];
  assert.equal(denied.allowed, false);
  assert(denied.retry_after > 0 && denied.retry_after <= 600);
  assert.equal((await db.query('SELECT expires_at FROM document_processing_limits WHERE user_id=$1', [userA])).rows[0].expires_at.getTime(), state.expires_at.getTime());
  assert.equal((await db.query(sql, [userB, 5, 600])).rows[0].allowed, true);
  await db.query("UPDATE document_processing_limits SET expires_at=now()-interval '1 second' WHERE user_id=$1", [userA]);
  assert.equal((await db.query(sql, [userA, 5, 600])).rows[0].allowed, true);
  assert.equal((await db.query('SELECT request_count FROM document_processing_limits WHERE user_id=$1', [userA])).rows[0].request_count, 1);
  await db.query('DELETE FROM auth.users WHERE id=$1', [userA]);
  assert.equal((await db.query('SELECT count(*)::integer AS n FROM document_processing_limits')).rows[0].n, 1);
  console.log('PASS: repeatable migration, RLS/grants, atomic quota SQL, saturation, stable Retry-After window, user isolation, reset and account-deletion cleanup.');
} finally {
  await db.close();
}
