"""得点・失点と各指標の相関・重回帰分析（自チーム・相手の両チーム行を使用）"""
import itertools, sys, warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor
import prep

warnings.filterwarnings('ignore')
pd.set_option('display.width', 200, 'display.max_columns', 30, 'display.unicode.east_asian_width', True)
RNG = np.random.default_rng(0)

# 過程指標（チームの行動。得点に至る前段）
PROCESS = {
    '保持率': 'ボール保持率(%)|', 'パス数': 'パス|合計', 'パス成功率': 'パス|成功率(%)',
    '前線へのパス成功率': '前線へのパス|成功率(%)', 'ロングパス': 'ロングパス|合計',
    '1/3へのパス成功': '1/3へのパス|成功', '縦パス成功': '縦パス|成功', 'スマートパス': 'スマートパス|合計',
    'クロス': 'クロス|合計', 'ポジショナル攻撃': 'ポジショナルアタック|合計', 'カウンター攻撃': 'カウンターアタック|合計',
    'ボールロス': 'ボールロス（ゾーン別）|合計', 'ボールロス(低)': 'ボールロス（ゾーン別）|低',
    'リカバリー': 'リカバリー（ゾーン別）|合計', 'リカバリー(高)': 'リカバリー（ゾーン別）|高',
    'インターセプト': 'インターセプト|', 'クリア': 'クリア|', '競り合い勝率': '競り合い（全体）|勝率(%)',
    '空中戦勝率': '空中競り合い|勝率(%)', '守り競り合い勝率': '守り競り合い|勝率(%)', 'ファウル': 'ファウル|', 'CK': 'CK|合計',
}
# チャンス指標（過程と得点の間にある媒介変数）
CHANCE = {'シュート': 'シュート|合計', '枠内シュート': 'シュート|枠内', 'xG': 'xG|'}

# 使い方: python3 regression.py [チームスタッツ.xlsx | シート.json]
df = prep.load(*sys.argv[1:2])
for name, key in {**PROCESS, **CHANCE}.items():
    df[name] = df[key]
df['strength'] = df['jleague'] - df['opp_jleague']   # +1: Jリーグ勢 vs 豪州勢, −1: 逆, 0: 同格
df['GD'] = df['GF'] - df['GA']
jets = df[df['own'] == 1].sort_values('日付').reset_index(drop=True)
P = list(PROCESS)

def r_crit(n, alpha=.05):
    t = stats.t.ppf(1 - alpha / 2, n - 2)
    return t / np.sqrt(n - 2 + t * t)

def section(t):
    print('\n' + '=' * 100 + f'\n{t}\n' + '=' * 100)

# ---------------------------------------------------------------- 1. Jets 6試合の相関
section(f'1. 自チーム {len(jets)}試合: 単相関（|r| の有意水準5%の臨界値 = {r_crit(6):.3f}）')
print(jets[['日付', 'チーム', 'GF', 'GA', 'xG', 'xGA']].assign(相手=df[df.own == 0].sort_values('日付')['チーム'].values))
rows = []
for v in P + list(CHANCE):
    rec = {'指標': v}
    for y in ['GF', 'GA', 'GD']:
        r, p = stats.pearsonr(jets[v], jets[y]); rho, _ = stats.spearmanr(jets[v], jets[y])
        rec[f'r({y})'] = r; rec[f'p({y})'] = p; rec[f'ρ({y})'] = rho
    rows.append(rec)
c6 = pd.DataFrame(rows).set_index('指標')
print(c6.round(2).sort_values('r(GD)', key=abs, ascending=False).to_string())
for y in ['GF', 'GA', 'GD']:
    sig = c6[c6[f'p({y})'] < .05].index.tolist()
    print(f'p<.05 ({y}): {sig}   ※検定数 {len(c6)} → 偶然でも期待される偽陽性 ≈ {len(c6) * .05:.1f} 件')
print('Jets 6試合の目的変数のばらつき: GF =', jets.GF.tolist(), ' GA =', jets.GA.tolist())

# ---------------------------------------------------------------- 2. 12行プール: 得点とxG
section('2. 両チーム12行プール: 得点 ~ xG（チャンスの質が得点をどこまで説明するか）')
for y, x in [('GF', 'xG'), ('GA', 'xGA')]:
    m = sm.OLS(df[y], sm.add_constant(df[[x]])).fit()
    print(f'{y} ~ {x}: 係数 {m.params[x]:.2f} (p={m.pvalues[x]:.3f}), R² = {m.rsquared:.2f}')
m = sm.OLS(df['GF'], sm.add_constant(df[['xG', 'strength']])).fit()
print(f"GF ~ xG + strength: xG {m.params['xG']:.2f} (p={m.pvalues['xG']:.3f}), strength {m.params['strength']:.2f} (p={m.pvalues['strength']:.3f}), R² = {m.rsquared:.2f}")
print('得点 − xG（チーム別）:'); print(df.assign(差=df.GF - df.xG)[['チーム', '日付', 'GF', 'xG', '差']].round(2).to_string(index=False))

# ---------------------------------------------------------------- 3. 12行プール: 単相関
section(f'3. 12行プール: 過程指標 × 目的変数の単相関（|r| 臨界値 = {r_crit(12):.3f}）、strength を統制した偏相関')
def partial(x, y, z):
    rx = sm.OLS(df[x], sm.add_constant(df[z])).fit().resid
    ry = sm.OLS(df[y], sm.add_constant(df[z])).fit().resid
    return stats.pearsonr(rx, ry)[0]
rows = []
for v in P:
    rec = {'指標': v}
    for y in ['GF', 'xG', 'GA', 'xGA']:
        rec[f'r({y})'] = stats.pearsonr(df[v], df[y])[0]
        rec[f'偏r({y})'] = partial(v, y, ['strength'])
    rows.append(rec)
c12 = pd.DataFrame(rows).set_index('指標')
print(c12.round(2).to_string())
print('\nstrength との相関（チーム力の代理変数に引きずられている指標の確認）:')
print(pd.Series({v: stats.pearsonr(df[v], df['strength'])[0] for v in P + ['GF', 'GA', 'xG', 'xGA']}).round(2).sort_values().to_string())

# ---------------------------------------------------------------- 4. 重回帰（全探索 + LOOCV）
def loocv_rmse(X, y):
    """OLS の一個抜き交差検証 RMSE（ハット行列による厳密解 e_i / (1 − h_ii)）"""
    X = sm.add_constant(X, has_constant='add').values; y = np.asarray(y, float)
    H = X @ np.linalg.pinv(X)
    e = (y - H @ y) / (1 - np.diag(H))
    return float(np.sqrt(np.mean(e ** 2)))

def search(y, k_max=2, controls=()):
    yv = df[y].values; out = []
    null = loocv_rmse(df[list(controls)] if controls else pd.DataFrame(index=df.index), yv)
    for k in range(1, k_max + 1):
        for combo in itertools.combinations(P, k):
            cols = list(combo) + list(controls)
            out.append((loocv_rmse(df[cols], yv), combo))
    out.sort(key=lambda t: t[0])
    return null, out

def loo_operator(cols):
    """LOOCV 残差 = R @ y となる行列 R（(I − H) の各行を 1 − h_ii で割ったもの）"""
    X = np.column_stack([np.ones(len(df))] + [df[c].values for c in cols])
    H = X @ np.linalg.pinv(X)
    return (np.eye(len(df)) - H) / (1 - np.diag(H))[:, None]

def perm_test(yv, controls, obs_ratio, n_perm):
    """目的変数を並べ替えて同じ全探索を行い、最良モデルの改善率が観測値以上になる割合"""
    Yp = np.column_stack([RNG.permutation(yv) for _ in range(n_perm)])
    rm = lambda R: np.sqrt(np.mean((R @ Yp) ** 2, axis=0))
    null = rm(loo_operator(list(controls)))
    best = np.full(n_perm, np.inf)
    for k in (1, 2):
        for c in itertools.combinations(P, k):
            best = np.minimum(best, rm(loo_operator(list(c) + list(controls))))
    return (np.sum(best / null <= obs_ratio) + 1) / (n_perm + 1)

def fit_report(y, combo, controls=()):
    cols = list(combo) + list(controls)
    X = sm.add_constant(df[cols]); m = sm.OLS(df[y], X).fit()
    z = (df[cols] - df[cols].mean()) / df[cols].std()
    mz = sm.OLS((df[y] - df[y].mean()) / df[y].std(), sm.add_constant(z)).fit()
    vif = {c: variance_inflation_factor(X.values, i + 1) for i, c in enumerate(cols)} if len(cols) > 1 else {cols[0]: 1.0}
    terms = ', '.join(f'{c}: b={m.params[c]:+.3f} β={mz.params[c]:+.2f} p={m.pvalues[c]:.3f} VIF={vif[c]:.1f}' for c in cols)
    return f'R²={m.rsquared:.2f} 調整R²={m.rsquared_adj:.2f} | {terms}'

N_PERM = 1000
for y in ['xG', 'GF', 'xGA', 'GA']:
    for controls in [(), ('strength',)]:
        section(f'4. 重回帰 {y} ~ 過程指標（1〜2変数の全 {len(P) + len(P) * (len(P) - 1) // 2} モデル）' + (' + strength 統制' if controls else ''))
        null, res = search(y, 2, controls)
        print(f'基準（{"strength のみ" if controls else "平均値のみ"}）の LOOCV RMSE = {null:.3f}')
        for rmse, combo in res[:5]:
            print(f'  LOOCV RMSE {rmse:.3f} ({(1 - rmse / null) * 100:+.0f}%) {" + ".join(combo):<28} {fit_report(y, combo, controls)}')
        # 選択バイアスの評価: 目的変数をシャッフルして同じ探索をしたとき、どれだけ良い「最良モデル」が偶然出るか
        p_perm = perm_test(df[y].values.astype(float), controls, res[0][0] / null, N_PERM)
        print(f'  並べ替え検定（{N_PERM}回）: 最良モデルの改善率がランダムで同等以上になる確率 p = {p_perm:.3f}')

# ---------------------------------------------------------------- 5. Jets 6試合単独の回帰（自由度の確認）
section(f'5. 自チーム {len(jets)}試合のみの単回帰（説明変数1つが上限）')
for y in ['GF', 'GA']:
    best = sorted(((loocv_rmse(jets[[v]], jets[y]), v) for v in P))[:3]
    nullj = loocv_rmse(pd.DataFrame(index=jets.index), jets[y])
    for rmse, v in best:
        m = sm.OLS(jets[y], sm.add_constant(jets[[v]])).fit()
        print(f'{y} ~ {v}: b={m.params[v]:+.3f} p={m.pvalues[v]:.3f} R²={m.rsquared:.2f} LOOCV RMSE {rmse:.3f}（基準 {nullj:.3f}）')
