// Firestore セキュリティルールのテスト（エミュレーター上で実行: npm run test:rules）
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import { readFileSync } from 'node:fs';

const rules = readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8');
const env = await initializeTestEnvironment({ projectId: 'demo-match-lens', firestore: { rules, host: '127.0.0.1', port: 8085 } });

const google = { sign_in_provider: 'google.com' };
const userA = env.authenticatedContext('uid-a', { email: 'a@example.com', email_verified: true, firebase: google }).firestore();
const userB = env.authenticatedContext('uid-b', { email: 'b@example.com', email_verified: true, firebase: google }).firestore();
const unverified = env.authenticatedContext('uid-c', { email: 'c@example.com', email_verified: false, firebase: google }).firestore();
const password = env.authenticatedContext('uid-d', { email: 'd@example.com', email_verified: true, firebase: { sign_in_provider: 'password' } }).firestore();
const anon = env.unauthenticatedContext().firestore();
const dataA = 'users/uid-a/datasets/current';
const sheet = { aoa: '[]', fileName: 'x.xlsx' };

const cases = [
  // 各利用者は自分の領域を使える
  ['利用者Aは自分のデータを書ける', () => userA.doc(dataA).set(sheet), true],
  ['利用者Aは自分のデータを読める', () => userA.doc(dataA).get(), true],
  ['利用者Aは試合の選択だけを更新できる', () => userA.doc(dataA).update({ excluded: ['2026-10-27|x'] }), true],
  ['利用者Bも自分のデータを書ける', () => userB.doc('users/uid-b/datasets/current').set(sheet), true],
  ['利用者Aは分析を保存できる', () => userA.doc('users/uid-a/analyses/a1').set({ name: 'x', aoa: '[]' }), true],
  ['利用者Aは保存した分析の一覧を読める', () => userA.collection('users/uid-a/analyses').get(), true],
  ['利用者Aは保存した分析を削除できる', () => userA.doc('users/uid-a/analyses/a1').delete(), true],
  ['利用者Aは表示設定を保存できる', () => userA.doc('users/uid-a/settings/display').set({ bg: '#ffffff', accent: null, pattern: 'dots', strength: 'mid' }), true],
  // 他の利用者の領域には入れない
  ['利用者Bは利用者Aのデータを読めない', () => userB.doc(dataA).get(), false],
  ['利用者Bは利用者Aのデータを書き換えられない', () => userB.doc(dataA).set(sheet), false],
  ['利用者Bは利用者Aの保存した分析を読めない', () => userB.collection('users/uid-a/analyses').get(), false],
  ['利用者Bは利用者Aの保存した分析を削除できない', () => userB.doc('users/uid-a/analyses/a1').delete(), false],
  ['利用者Bは利用者Aの表示設定を読めない', () => userB.doc('users/uid-a/settings/display').get(), false],
  ['利用者一覧（users）は誰も読めない', () => userA.collection('users').get(), false],
  // ログインの条件
  ['未ログインでは読めない', () => anon.doc(dataA).get(), false],
  ['メール未確認のアカウントは使えない', () => unverified.doc('users/uid-c/datasets/current').set(sheet), false],
  ['Google 以外のログインは使えない', () => password.doc('users/uid-d/datasets/current').set(sheet), false],
  // 保存できる内容の制限
  ['決められた場所以外には書けない', () => userA.doc('users/uid-a/other/x').set({ a: 1 }), false],
  ['最上位の場所には書けない', () => userA.doc('public/x').set({ a: 1 }), false],
  ['大きすぎるシートは保存できない', () => userA.doc('users/uid-a/analyses/big').set({ aoa: 'x'.repeat(960000) }), false],
  ['シートのないデータは保存できない', () => userA.doc('users/uid-a/datasets/current').set({ fileName: 'x' }), false],
  ['表示設定に余計な項目は保存できない', () => userA.doc('users/uid-a/settings/display').set({ bg: '#fff', script: 'x' }), false],
];
let failed = 0;
for (const [label, run, ok] of cases) {
  try { await (ok ? assertSucceeds(run()) : assertFails(run())); console.log('PASS', label); }
  catch (e) { failed++; console.log('FAIL', label, '-', e.message); }
}
await env.cleanup();
process.exit(failed ? 1 : 0);
