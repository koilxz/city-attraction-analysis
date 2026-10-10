# -*- coding: utf-8 -*-
"""
visualize.py — 基于清洗后数据生成全部图表

输入：data/processed/scenic_spots_clean.xlsx（由 clean.py 产出）
输出：results/figures/*.png

设计原则：清洗（clean.py）与可视化（visualize.py）职责分离，
本脚本不做任何数据清洗，只负责把干净数据画出来。
"""
import os
import warnings
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# 中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.bbox"] = "tight"

DATA = "data/processed/scenic_spots_clean.xlsx"
OUT = "results/figures"
os.makedirs(OUT, exist_ok=True)

df = pd.read_excel(DATA)
print(f"读入清洗数据: {len(df)} 条 × {len(df.columns)} 列")

# ---------- 配色 ----------
NAVY, ORANGE, TEAL, RED, GREEN = "#2E4057", "#E8871E", "#2A9D8F", "#C73E1D", "#4C956C"
sns.set_palette("Set2")


# ---------- 图 01：各城市景点数 ----------
def fig01():
    vc = df["city"].value_counts()
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(vc.index[::-1], vc.values[::-1], color=NAVY)
    ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_xlabel("景点数量", fontsize=11)
    ax.set_title("各城市景点数量分布", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlim(0, vc.max() * 1.15)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/01_city_spot_count.png")
    plt.close()
    print("  ✓ 01_city_spot_count.png")


# ---------- 图 02：评论数 Top15 ----------
def fig02():
    top = df.nlargest(15, "comment_count")[["name", "city", "comment_count"]]
    top["label"] = top["name"].str[:14] + "（" + top["city"] + "）"
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top["label"][::-1], top["comment_count"][::-1], color=ORANGE)
    ax.bar_label(bars, padding=3, fontsize=9)
    ax.set_xlabel("评论数", fontsize=11)
    ax.set_title("评论数最高的 15 个景点", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlim(0, top["comment_count"].max() * 1.18)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/02_top15_comments.png")
    plt.close()
    print("  ✓ 02_top15_comments.png")


# ---------- 图 03：各城市评分箱线图 ----------
def fig03():
    order = df.groupby("city")["rating"].median().sort_values(ascending=False).index
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.boxplot(data=df, x="city", y="rating", order=order, ax=ax,
                palette="Set3", width=0.6)
    ax.axhline(df["rating"].mean(), color=RED, linestyle="--", linewidth=1.5,
               label=f"全网均值 {df['rating'].mean():.2f}")
    ax.set_xlabel("城市", fontsize=11)
    ax.set_ylabel("评分", fontsize=11)
    ax.set_title("各城市景点评分分布（箱线图）", fontsize=14, fontweight="bold", pad=15)
    ax.legend()
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/03_rating_boxplot.png")
    plt.close()
    print("  ✓ 03_rating_boxplot.png")


# ---------- 图 04：价格 vs 评分散点 ----------
def fig04():
    paid = df[df["price"] > 0]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(paid["price"], paid["rating"], s=70, alpha=0.7,
               color=TEAL, edgecolors="white", linewidths=1.2)
    if len(paid) > 2:
        z = np.polyfit(paid["price"], paid["rating"], 1)
        xs = np.linspace(paid["price"].min(), paid["price"].max(), 50)
        ax.plot(xs, np.polyval(z, xs), color=RED, linestyle="--", linewidth=2,
                label=f"趋势线 (r = {paid['price'].corr(paid['rating']):.3f})")
        ax.legend()
    ax.set_xlabel("门票价格（元）", fontsize=11)
    ax.set_ylabel("评分", fontsize=11)
    ax.set_title("门票价格 vs 口碑评分（有价格的景点）", fontsize=14,
                 fontweight="bold", pad=15)
    ax.grid(alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/04_price_rating_scatter.png")
    plt.close()
    print("  ✓ 04_price_rating_scatter.png")


# ---------- 图 05：景点类型占比 ----------
def fig05():
    vc = df["primary_tag"].value_counts().head(8)
    fig, ax = plt.subplots(figsize=(8, 8))
    wedges, texts, autotexts = ax.pie(
        vc.values, labels=vc.index, autopct="%1.1f%%",
        colors=sns.color_palette("Set2", len(vc)),
        startangle=90, textprops={"fontsize": 11})
    for t in autotexts:
        t.set_fontweight("bold")
    ax.set_title("景点主要类型占比", fontsize=14, fontweight="bold", pad=15)
    plt.savefig(f"{OUT}/05_tag_pie.png")
    plt.close()
    print("  ✓ 05_tag_pie.png")


# ---------- 图 06：城市 × 类型热力图 ----------
def fig06():
    ct = pd.crosstab(df["city"], df["primary_tag"])
    top_tags = df["primary_tag"].value_counts().head(6).index
    ct = ct[top_tags]
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(ct, annot=True, fmt="d", cmap="YlGnBu", ax=ax,
                linewidths=0.5, cbar_kws={"label": "景点数"})
    ax.set_title("城市 × 景点类型 分布热力图", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlabel("景点类型", fontsize=11)
    ax.set_ylabel("城市", fontsize=11)
    plt.savefig(f"{OUT}/06_city_tag_heatmap.png")
    plt.close()
    print("  ✓ 06_city_tag_heatmap.png")


# ---------- 图 07：价格区间 vs 评分小提琴图 ----------
def fig07():
    order = ["免费", "低价(≤50)", "中价(51-100)", "高价(>100)"]
    order = [o for o in order if o in df["price_level"].unique()]
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.violinplot(data=df, x="price_level", y="rating", order=order,
                   ax=ax, palette="Set2", inner="quartile")
    ax.set_xlabel("价格区间", fontsize=11)
    ax.set_ylabel("评分", fontsize=11)
    ax.set_title("不同价格区间的评分分布", fontsize=14, fontweight="bold", pad=15)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/07_price_rating_violin.png")
    plt.close()
    print("  ✓ 07_price_rating_violin.png")


# ---------- 图 08：各城市高评分占比 ----------
def fig08():
    g = df.groupby("city").agg(总数=("name", "size"), 高分=("is_high_rated", "sum"))
    g["高评分占比"] = g["高分"] / g["总数"] * 100
    g = g.sort_values("高评分占比", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(g.index, g["高评分占比"], color=GREEN)
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.set_xlabel("高评分（≥4.5）景点占比", fontsize=11)
    ax.set_title("各城市高评分景点占比", fontsize=14, fontweight="bold", pad=15)
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/08_rating_segment_stacked.png")
    plt.close()
    print("  ✓ 08_rating_segment_stacked.png")


# ---------- 图 13：城市 × 价格区间 堆叠 ----------
def fig13():
    ct = pd.crosstab(df["city"], df["price_level"])
    order = [c for c in ["免费", "低价(≤50)", "中价(51-100)", "高价(>100)"] if c in ct.columns]
    ct = ct[order]
    fig, ax = plt.subplots(figsize=(10, 5))
    ct.plot(kind="bar", stacked=True, ax=ax,
            color=sns.color_palette("Set2", len(order)))
    ax.set_xlabel("城市", fontsize=11)
    ax.set_ylabel("景点数", fontsize=11)
    ax.set_title("各城市景点价格区间构成", fontsize=14, fontweight="bold", pad=15)
    ax.legend(title="价格区间", fontsize=9)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.xticks(rotation=0)
    plt.savefig(f"{OUT}/13_tag_stacked.png")
    plt.close()
    print("  ✓ 13_tag_stacked.png")


# ---------- 图 11：地理分布 ----------
def fig11():
    fig, ax = plt.subplots(figsize=(9, 6))
    c = df.groupby("city")["rating"].mean().sort_values(ascending=False)
    sizes = df["city"].value_counts().reindex(c.index)
    scatter = ax.scatter(range(len(c)), c.values, s=sizes.values * 18,
                         c=c.values, cmap="RdYlGn", alpha=0.8,
                         edgecolors="white", linewidths=1.5)
    ax.set_xticks(range(len(c)))
    ax.set_xticklabels(c.index, fontsize=10)
    for i, (city, v) in enumerate(c.items()):
        ax.annotate(f"{v:.2f}", (i, v), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9)
    ax.set_ylabel("平均评分", fontsize=11)
    ax.set_title("各城市口碑分布（气泡大小 = 景点数）", fontsize=14,
                 fontweight="bold", pad=15)
    plt.colorbar(scatter, ax=ax, label="平均评分")
    ax.grid(alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    ax.set_ylim(c.min() - 0.15, c.max() + 0.15)
    plt.savefig(f"{OUT}/11_geo_distribution.png")
    plt.close()
    print("  ✓ 11_geo_distribution.png")


# ---------- 图 12：评分区间分布 ----------
def fig12():
    bins = [0, 3.5, 4.0, 4.5, 5.01]
    labels = ["<3.5 较差", "3.5-4.0 一般", "4.0-4.5 良好", "≥4.5 优秀"]
    df["_seg"] = pd.cut(df["rating"], bins=bins, labels=labels, right=False)
    vc = df["_seg"].value_counts().reindex(labels)
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(vc.index, vc.values, color=sns.color_palette("RdYlGn", 4))
    ax.bar_label(bars, padding=3, fontsize=10)
    ax.set_ylabel("景点数", fontsize=11)
    ax.set_title("景点评分区间分布", fontsize=14, fontweight="bold", pad=15)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    plt.savefig(f"{OUT}/12_sentiment_analysis.png")
    plt.close()
    print("  ✓ 12_sentiment_analysis.png")


if __name__ == "__main__":
    print("\n开始生成图表...")
    for fn in [fig01, fig02, fig03, fig04, fig05, fig06,
               fig07, fig08, fig11, fig12, fig13]:
        fn()
    print("\n✅ 全部图表生成完成")
