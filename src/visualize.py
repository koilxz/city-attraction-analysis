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


# ---------- 图 11：各城市口碑（气泡 = 景点数） ----------
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
    ax.set_title("各城市口碑对比（气泡大小 = 景点数）", fontsize=14,
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


# ---------- 图 09：景点简介高频词 ----------
def fig09():
    """把 description 分词后画词云。

    ⚠️ 注意：这不是"用户评论"的词云，而是**景点简介**的词云
    （原始数据里没有留存可供统计的评论文本，评论在采集时只取了数量）。
    图上已标注清楚，避免误读。
    """
    try:
        import jieba
        from wordcloud import WordCloud
    except ImportError:
        print("  · 跳过 09（需要 jieba + wordcloud）")
        return

    texts = df["description"].dropna().astype(str)
    if len(texts) == 0:
        print("  · 跳过 09（无 description 数据）")
        return

    # 收集全文
    corpus = " ".join(texts)

    # 高频词挑出来做停用词（这些词没信息量）
    stopwords = {
        "景区", "景点", "公园", "旅游", "位于", "公里", "面积", "中国", "国家",
        "一个", "这里", "可以", "以及", "是", "的", "了", "和", "与", "在",
        "有", "为", "是", "等", "被", "而", "或", "从", "到", "对", "也",
        "这个", "其中", "主要", "由于", "通过", "进行", "具有", "成为",
    }
    words = [w for w in jieba.cut(corpus)
             if len(w) >= 2 and w not in stopwords and not w.isdigit()]

    if not words:
        print("  · 跳过 09（分词后无有效词）")
        return

    from collections import Counter
    freq = Counter(words)

    # 中文字体路径
    font_path = "C:/Windows/Fonts/msyh.ttc"

    wc = WordCloud(
        font_path=font_path,
        width=1200, height=700,
        background_color="white",
        max_words=120,
        colormap="viridis",
        prefer_horizontal=0.92,
    ).generate_from_frequencies(freq)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title("景点简介高频词（Top 120）", fontsize=14,
                 fontweight="bold", pad=15)
    ax.text(0.99, -0.02, "注：统计对象为「景点简介」文本，非用户评论",
            transform=ax.transAxes, ha="right", fontsize=8.5, color="#888")
    plt.savefig(f"{OUT}/09_wordcloud.png")
    plt.close()
    print("  ✓ 09_wordcloud.png")


# ---------- 图 10：城市级交互式地图 ----------
# ⚠️ 关于坐标：原始采集未获得景点真实经纬度（spider_real.py 里是随机生成后删除的），
#    因此这里【不做景点级打点】，改为【城市级聚合】—— 城市中心坐标是真实可靠的，
#    且按城市聚合后的统计量（景点数 / 均分 / 平均评论数）本身就有意义。
CITY_CENTER = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737),
    "重庆": (29.5630, 106.5516), "武汉": (30.5928, 114.3055),
    "成都": (30.5728, 104.0668), "西安": (34.3416, 108.9398),
    "青岛": (36.0671, 120.3826), "杭州": (30.2741, 120.1551),
    "济南": (36.6512, 117.1201), "南京": (32.0603, 118.7969),
}


def fig10():
    """用 folium 生成**城市级**交互式地图（HTML）。

    ⚠️ 这是本项目唯一的**交互式**产物：鼠标可缩放、点击看城市汇总。
    注：不做景点级打点，因为景点真实经纬度不可得（见 README 局限性）。
    """
    try:
        import folium
    except ImportError:
        print("  · 跳过 10（需要 folium）")
        return

    g = df.groupby("city").agg(
        景点数=("name", "size"),
        均分=("rating", "mean"),
        平均评论=("comment_count", "mean"),
    )
    g = g[g.index.isin(CITY_CENTER)]
    if len(g) == 0:
        print("  · 跳过 10（无城市数据）")
        return

    m = folium.Map(location=[32.0, 114.0], zoom_start=5, tiles="OpenStreetMap")

    vmax = g["景点数"].max()
    for city, row in g.iterrows():
        lat, lon = CITY_CENTER[city]
        radius = 8 + 18 * (row["景点数"] / vmax)
        popup = (f"<b>{city}</b><br>"
                 f"景点数：{int(row['景点数'])}<br>"
                 f"平均评分：{row['均分']:.2f}<br>"
                 f"平均评论数：{int(row['平均评论'])}")
        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color="#2E4057",
            fill=True,
            fill_color="#E8871E",
            fill_opacity=0.65,
            popup=folium.Popup(popup, max_width=240),
            tooltip=f"{city} · {int(row['景点数'])} 个景点",
        ).add_to(m).add_child(
            folium.Marker([lat, lon], icon=folium.DivIcon(
                html=f'<div style="font-size:12px;font-weight:bold;'
                     f'color:#2E4057;white-space:nowrap">{city}</div>',
                icon_size=(40, 14), icon_anchor=(20, 26))))

    folium.LayerControl().add_to(m)
    m.save(f"{OUT}/scenic_map.html")
    print("  ✓ scenic_map.html（城市级交互式地图）")


if __name__ == "__main__":
    print("\n开始生成图表...")
    for fn in [fig01, fig02, fig03, fig04, fig05, fig06,
               fig07, fig08, fig09, fig10, fig11, fig12, fig13]:
        fn()
    print("\n✅ 全部图表生成完成")
