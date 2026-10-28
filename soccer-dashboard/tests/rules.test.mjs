// Firestore セキュリティルールのテスト（エミュレーター上で実行: npm run test:rules）
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import { readFileSync } from 'node:fs';

const OWNER = 'owner@example.com';
const rules = readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8').replaceAll('__ALLOWED_EMAIL__', OWNER);
const env = await initializeTestEnvironment({ projectId: 'demo-match-lens', firestore: { rules, host: '127.0.0.1', port: 8085 } });

const owner = env.authenticatedContext('uid-owner', { email: OWNER, email_verified: true }).firestore();
const other = env.authenticatedContext('uid-other', { email: 'someone@example.com', email_verified: true }).firestore();
const unverified = env.authenticatedContext('uid-owner', { email: OWNER, email_verified: false }).firestore();
const anon = env.unauthenticatedContext().firestore();
const mine = 'users/uid-owner/datasets/current';

const cases = [
  ['本人は自分のデータを書ける', () => owner.doc(mine).set({ aoa: '[]' }), true],
  ['本人は自分のデータを読める', () => owner.doc(mine).get(), true],
  ['他のアカウントは本人のデータを読めない', () => other.doc(mine).get(), false],
  ['他のアカウントは自分の領域も読めない', () => other.doc('users/uid-other/datasets/current').get(), false],
  ['他のアカウントは自分の領域にも書けない', () => other.doc('users/uid-other/datasets/current').set({ aoa: '[]' }), false],
  ['未ログインでは読めない', () => anon.doc(mine).get(), false],
  ['メール未確認のアカウントは読めない', () => unverified.doc(mine).get(), false],
  ['本人は保存した分析を書ける', () => owner.doc('users/uid-owner/analyses/a1').set({ name: 'x', aoa: '[]' }), true],
  ['本人は保存した分析の一覧を読める', () => owner.collection('users/uid-owner/analyses').get(), true],
  ['他のアカウントは保存した分析を読めない', () => other.collection('users/uid-owner/analyses').get(), false],
  ['他のアカウントは保存した分析を削除できない', () => other.doc('users/uid-owner/analyses/a1').delete(), false],
  ['本人は表示設定を保存できる', () => owner.doc('users/uid-owner/settings/display').set({ bg: '#ffffff', pattern: 'dots' }), true],
  ['他のアカウントは表示設定を読めない', () => other.doc('users/uid-owner/settings/display').get(), false],
  ['本人でも他の uid の領域には書けない', () => owner.doc('users/uid-other/datasets/current').set({ aoa: '[]' }), false],
  ['本人でも決められた場所以外には書けない', () => owner.doc('public/x').set({ a: 1 }), false],
];
let failed = 0;
for (const [label, run, ok] of cases) {
  try { await (ok ? assertSucceeds(run()) : assertFails(run())); console.log('PASS', label); }
  catch (e) { failed++; console.log('FAIL', label, '-', e.message); }
}
await env.cleanup();
process.exit(failed ? 1 : 0);
