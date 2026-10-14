# -*- coding: utf-8 -*-
"""stats.py — 统计分析脚本（README「三、两个关键发现」全部数字的唯一来源）

用法：
    python src/stats.py

读取清洗后数据 data/processed/scenic_spots_clean.xlsx，计算：
  发现 1  评论数（热度） × 评分 的相关性，以及高/低热度分组的均值检验
  发现 2  各城市平均评分排名 + 全网统计

结果打印到屏幕，同时保存到 data/processed/stats_report.txt。
脚本末尾对关键数字做断言自检：一旦清洗逻辑变动导致 README 里的数字漂移，会立即报错。
"""
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "processed", "scenic_spots_clean.xlsx")
OUT = os.path.join(ROOT, "data", "processed", "stats_report.txt")

# README 对外公布的基准值（保留 3 位小数）。若清洗数据变化导致不一致，脚本会报错。
EXPECT = {
    "n": 151,
    "comment_total": 608423,
    "pearson_r": 0.101,
    "spearman_rho": 0.078,
    "n_hi": 31,
    "n_lo": 46,
    "hi_mean": 4.671,
    "lo_mean": 4.646,
    "ttest_p": 0.630,
    "overall_mean": 4.550,
    "pct_ge_45": 77.5,
}

df = pd.read_excel(XLSX)
cc = df["comment_count"].astype(float)
rt = df["rating"].astype(float)

lines = []


def w(s=""):
    lines.append(s)
    print(s)


w("=" * 68)
w("景点口碑分析 · 统计报告（由 src/stats.py 生成，可一键复现）")
w("数据文件：data/processed/scenic_spots_clean.xlsx")
w("=" * 68)

# ---------- 基本规模 ----------
n = len(df)
n_with_cmt = int((cc > 0).sum())
n_zero = int((cc == 0).sum())
cmt_total = int(cc.sum())
w()
w("【基本规模】")
w(f"  景点总数            : {n}")
w(f"  有评论的景点        : {n_with_cmt}")
w(f"  评论数为 0 的景点   : {n_zero}")
w(f"  评论总数            : {cmt_total:,}")

# ---------- 发现 1：热度 × 评分 ----------
pr, pp = stats.pearsonr(cc, rt)
sr, sp = stats.spearmanr(cc, rt)

q80 = float(np.percentile(cc, 80))
q20 = float(np.percentile(cc, 20))
hi = df[cc >= q80]
lo = df[cc <= q20]
hi_mean = float(hi["rating"].mean())
lo_mean = float(lo["rating"].mean())
t_p = float(stats.ttest_ind(hi["rating"], lo["rating"], equal_var=False)[1])  # Welch

w()
w("【发现 1：热度高 ≠ 评价好】")
w(f"  Pearson  r    = {pr:.4f}   (p = {pp:.4f})")
w(f"  Spearman rho  = {sr:.4f}   (p = {sp:.4f})   <- 不显著")
w(f"  高热度组 (Top 20%, 评论数 >= {q80:,.0f}) : n = {len(hi)}, 均分 = {hi_mean:.4f}")
w(f"  低热度组 (Bottom 20%, 评论数 <= {q20:,.0f}) : n = {len(lo)}, 均分 = {lo_mean:.4f}")
w(f"  两组差异 Welch t 检验 : p = {t_p:.4f}   <- 不显著")

# ---------- 发现 2：城市口碑排名 ----------
ct = df.groupby("city")["rating"].agg(["count", "mean"]).sort_values("mean", ascending=False)
overall = float(rt.mean())
pct_ge_45 = float(100 * (rt >= 4.5).mean())

w()
w("【发现 2：各城市口碑排名（按平均评分）】")
w(f"  {'排名':<4}{'城市':<6}{'景点数':<8}{'平均评分':<10}")
for i, (city, row) in enumerate(ct.iterrows(), start=1):
    w(f"  {i:<5}{city:<7}{int(row['count']):<8}{row['mean']:.4f}")
w(f"  全网均分 = {overall:.4f}   评分 >= 4.5 占比 = {pct_ge_45:.1f}%")

# ---------- 自检 ----------
checks = [
    ("景点总数", n, EXPECT["n"]),
    ("评论总数", cmt_total, EXPECT["comment_total"]),
    ("Pearson r", round(pr, 3), EXPECT["pearson_r"]),
    ("Spearman rho", round(sr, 3), EXPECT["spearman_rho"]),
    ("高热度组 n", len(hi), EXPECT["n_hi"]),
    ("低热度组 n", len(lo), EXPECT["n_lo"]),
    ("高热度组均分", round(hi_mean, 3), EXPECT["hi_mean"]),
    ("低热度组均分", round(lo_mean, 3), EXPECT["lo_mean"]),
    ("Welch p", round(t_p, 3), EXPECT["ttest_p"]),
    ("全网均分", round(overall, 3), EXPECT["overall_mean"]),
    ("评分>=4.5 占比", round(pct_ge_45, 1), EXPECT["pct_ge_45"]),
]
bad = [(name, got, exp) for name, got, exp in checks if got != exp]

w()
if bad:
    w("【自检】❌ 与 README 基准不一致：")
    for name, got, exp in bad:
        w(f"    {name}: 实测 {got} ≠ 基准 {exp}")
else:
    w(f"【自检】✅ 全部 {len(checks)} 项与 README 基准一致")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\n报告已保存：{os.path.relpath(OUT, ROOT)}")

sys.exit(1 if bad else 0)
