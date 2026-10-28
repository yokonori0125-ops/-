// Firestore セキュリティルールのテスト（エミュレーター上で実行: npm run test:rules）
import { initializeTestEnvironment, assertSucceeds, assertFails } from '@firebase/rules-unit-testing';
import firebase from 'firebase/compat/app';
import 'firebase/compat/firestore';
import { readFileSync } from 'node:fs';

const ADMIN = 'admin@example.com';
const rules = readFileSync(new URL('../firestore.rules', import.meta.url), 'utf8').replaceAll('__ADMIN_EMAIL__', ADMIN);
const env = await initializeTestEnvironment({ projectId: 'demo-match-lens', firestore: { rules, host: '127.0.0.1', port: 8085 } });

const google = { sign_in_provider: 'google.com' };
const ctx = (uid, email, extra = {}) => env.authenticatedContext(uid, { email, email_verified: true, firebase: google, ...extra }).firestore();
const admin = ctx('uid-admin', 'Admin@Example.com');        // 大文字が混ざっていても管理者として扱う
const userA = ctx('uid-a', 'a@example.com');
const userB = ctx('uid-b', 'b@example.com');
const userC = ctx('uid-c', 'c@example.com');
const userD = ctx('uid-d', 'd@example.com');
const stranger = ctx('uid-s', 's@example.com');
const unverified = ctx('uid-u', 'u@example.com', { email_verified: false });
const password = ctx('uid-p', 'p@example.com', { firebase: { sign_in_provider: 'password' } });
const anon = env.unauthenticatedContext().firestore();

const { Timestamp, FieldValue } = firebase.firestore;
const ts = () => FieldValue.serverTimestamp();
const days = n => Timestamp.fromMillis(Date.now() + n * 864e5);
const T = { ok: 'tok_valid_aaaaaaaaaaaaaaaa', solo: 'tok_single_bbbbbbbbbbbbbbb', exp: 'tok_expired_ccccccccccccc', rev: 'tok_revoked_ddddddddddddd', mail: 'tok_email_eeeeeeeeeeeeeeee', new: 'tok_created_by_admin_ffffff' };
const invite = (o = {}) => ({ label: 'x', email: null, maxUses: 5, uses: 0, revoked: false, expiresAt: days(7), createdAt: Timestamp.now(), ...o });
await env.withSecurityRulesDisabled(async c => {
  const db = c.firestore();
  await db.doc(`invites/${T.ok}`).set(invite());
  await db.doc(`invites/${T.solo}`).set(invite({ maxUses: 1 }));
  await db.doc(`invites/${T.exp}`).set(invite({ expiresAt: Timestamp.fromMillis(Date.now() - 1000) }));
  await db.doc(`invites/${T.rev}`).set(invite({ revoked: true }));
  await db.doc(`invites/${T.mail}`).set(invite({ email: 'd@example.com' }));
});
// 招待リンクで参加する：メンバー登録と使用回数 +1 を 1 回の書き込みで行う（アプリと同じ手順）
const join = (db, uid, email, token, o = {}) => {
  const b = db.batch();
  if (!o.skipUses) b.update(db.doc(`invites/${token}`), { uses: FieldValue.increment(o.by || 1) });
  if (!o.skipMember) b.set(db.doc(`members/${uid}`), { role: o.role || 'member', email, invite: token, joinedAt: ts() });
  return b.commit();
};
const sheet = { aoa: '[]', fileName: 'x.xlsx' };

const cases = [
  // 管理者
  ['管理者は自分を管理者として登録できる', () => admin.doc('members/uid-admin').set({ role: 'admin', email: 'Admin@Example.com', joinedAt: ts() }), true],
  ['管理者は自分のデータを使える', () => admin.doc('users/uid-admin/datasets/current').set(sheet), true],
  ['管理者は招待リンクを作れる', () => admin.doc(`invites/${T.new}`).set({ ...invite({ expiresAt: days(30) }), createdAt: ts() }), true],
  ['管理者は招待リンクの一覧を読める', () => admin.collection('invites').get(), true],
  ['管理者は招待リンクを取り消せる', () => admin.doc(`invites/${T.new}`).update({ revoked: true }), true],
  ['管理者でも取り消し以外の書き換え（回数の追加）はできない', () => admin.doc(`invites/${T.ok}`).update({ maxUses: 50 }), false],
  ['使用回数が 0 でない招待は作れない', () => admin.doc('invites/tok_bad_uses_gggggggggggggg').set({ ...invite({ uses: 1 }), createdAt: ts() }), false],
  ['使える回数が 50 を超える招待は作れない', () => admin.doc('invites/tok_bad_max_hhhhhhhhhhhhhhh').set({ ...invite({ maxUses: 100 }), createdAt: ts() }), false],
  ['有効期限が 31 日を超える招待は作れない', () => admin.doc('invites/tok_bad_exp_iiiiiiiiiiiiiii').set({ ...invite({ expiresAt: days(40) }), createdAt: ts() }), false],
  ['推測しやすい短い ID の招待は作れない', () => admin.doc('invites/abc').set({ ...invite(), createdAt: ts() }), false],
  ['管理者以外は管理者として登録できない', () => stranger.doc('members/uid-s').set({ role: 'admin', email: 's@example.com', joinedAt: ts() }), false],
  ['管理者以外は招待リンクを作れない', () => stranger.doc('invites/tok_by_stranger_jjjjjjjjjj').set({ ...invite(), createdAt: ts() }), false],
  // 招待リンクで参加する
  ['招待されていない人は自分のデータも使えない', () => stranger.doc('users/uid-s/datasets/current').set(sheet), false],
  ['招待リンクの ID を知っていれば 1 件読める', () => stranger.doc(`invites/${T.ok}`).get(), true],
  ['未ログインでは招待リンクを読めない', () => anon.doc(`invites/${T.ok}`).get(), false],
  ['有効な招待リンクで参加できる', () => join(userA, 'uid-a', 'a@example.com', T.ok), true],
  ['参加したメンバーは自分のデータを使える', () => userA.doc('users/uid-a/datasets/current').set(sheet), true],
  ['参加したメンバーは自分の登録を読める', () => userA.doc('members/uid-a').get(), true],
  ['使用回数を増やさずに参加することはできない', () => join(userB, 'uid-b', 'b@example.com', T.ok, { skipUses: true }), false],
  ['使用回数を 2 増やして参加することはできない', () => join(userB, 'uid-b', 'b@example.com', T.ok, { by: 2 }), false],
  ['参加せずに使用回数だけ増やすことはできない', () => join(userB, 'uid-b', 'b@example.com', T.ok, { skipMember: true }), false],
  ['招待リンクで管理者として参加することはできない', () => join(userB, 'uid-b', 'b@example.com', T.ok, { role: 'admin' }), false],
  ['他人の名前で参加することはできない', () => join(userB, 'uid-c', 'b@example.com', T.ok), false],
  ['有効期限が切れた招待では参加できない', () => join(userB, 'uid-b', 'b@example.com', T.exp), false],
  ['取り消された招待では参加できない', () => join(userB, 'uid-b', 'b@example.com', T.rev), false],
  ['1 回限りの招待で 1 人目は参加できる', () => join(userB, 'uid-b', 'b@example.com', T.solo), true],
  ['1 回限りの招待で 2 人目は参加できない', () => join(userC, 'uid-c', 'c@example.com', T.solo), false],
  ['宛先が別のアカウントの招待では参加できない', () => join(userC, 'uid-c', 'c@example.com', T.mail), false],
  ['宛先のアカウントなら参加できる', () => join(userD, 'uid-d', 'd@example.com', T.mail), true],
  ['参加済みの人は使用回数を増やせない', () => join(userA, 'uid-a', 'a@example.com', T.ok, { skipMember: true }), false],
  ['メンバーは自分の登録を書き換えられない', () => userA.doc('members/uid-a').update({ role: 'admin' }), false],
  ['メンバーは招待リンクの一覧を読めない', () => userA.collection('invites').get(), false],
  ['メンバーは招待リンクを取り消せない', () => userA.doc(`invites/${T.ok}`).update({ revoked: true }), false],
  ['メンバーはメンバーの一覧を読めない', () => userA.collection('members').get(), false],
  ['メンバーはほかの人の登録を読めない', () => userA.doc('members/uid-b').get(), false],
  // プライバシー：各自の領域はほかの誰からも読めない
  ['メンバーはほかのメンバーのデータを読めない', () => userB.doc('users/uid-a/datasets/current').get(), false],
  ['メンバーはほかのメンバーのデータを書き換えられない', () => userB.doc('users/uid-a/datasets/current').set(sheet), false],
  ['メンバーはほかのメンバーの保存した分析を読めない', () => userB.collection('users/uid-a/analyses').get(), false],
  ['管理者もメンバーのデータは読めない', () => admin.doc('users/uid-a/datasets/current').get(), false],
  ['メンバーは管理者のデータを読めない', () => userA.doc('users/uid-admin/datasets/current').get(), false],
  ['利用者一覧（users）は誰も読めない', () => admin.collection('users').get(), false],
  // メンバーの管理
  ['管理者はメンバーの一覧を読める', () => admin.collection('members').get(), true],
  ['メンバーは自分の登録を消せない', () => userB.doc('members/uid-b').delete(), false],
  ['管理者はメンバーの利用を停止できる', () => admin.doc('members/uid-b').delete(), true],
  ['利用を停止された人は自分のデータも使えない', () => userB.doc('users/uid-b/datasets/current').set(sheet), false],
  // ログインの条件
  ['未ログインではデータを読めない', () => anon.doc('users/uid-a/datasets/current').get(), false],
  ['メール未確認のアカウントは参加できない', () => join(unverified, 'uid-u', 'u@example.com', T.ok), false],
  ['Google 以外のログインは参加できない', () => join(password, 'uid-p', 'p@example.com', T.ok), false],
  // 保存できる内容の制限
  ['決められた場所以外には書けない', () => userA.doc('users/uid-a/other/x').set({ a: 1 }), false],
  ['最上位の場所には書けない', () => admin.doc('public/x').set({ a: 1 }), false],
  ['保存した分析を保存・一覧・削除できる', async () => { await userA.doc('users/uid-a/analyses/a1').set({ name: 'x', aoa: '[]' }); await userA.collection('users/uid-a/analyses').get(); return userA.doc('users/uid-a/analyses/a1').delete(); }, true],
  ['試合の選択だけを更新できる', () => userA.doc('users/uid-a/datasets/current').update({ excluded: ['2026-10-27|x'] }), true],
  ['大きすぎるシートは保存できない', () => userA.doc('users/uid-a/analyses/big').set({ aoa: 'x'.repeat(960000) }), false],
  ['シートのないデータは保存できない', () => userA.doc('users/uid-a/datasets/current').set({ fileName: 'x' }), false],
  ['表示設定を保存できる', () => userA.doc('users/uid-a/settings/display').set({ bg: '#ffffff', accent: null, pattern: 'dots', strength: 'mid' }), true],
  ['表示設定に余計な項目は保存できない', () => userA.doc('users/uid-a/settings/display').set({ bg: '#fff', script: 'x' }), false],
];
let failed = 0;
for (const [label, run, ok] of cases) {
  try { await (ok ? assertSucceeds(run()) : assertFails(run())); console.log('PASS', label); }
  catch (e) { failed++; console.log('FAIL', label, '-', e.message); }
}
console.log(`${cases.length - failed} / ${cases.length} passed`);
await env.cleanup();
process.exit(failed ? 1 : 0);
