# -*- coding: utf-8 -*-
"""
clean.py — 数据清洗与质量修复

本项目最有价值的环节：原始数据存在严重的"跨城市污染"问题
（爬取时被网站的推荐链接干扰，导致非本地景点被错误归类）。

本脚本通过「地标-城市映射表」检测并剔除归属错误的记录，
输出可供分析使用的干净数据集。

输入：data/raw/scenic_spots_raw.xlsx
输出：data/processed/scenic_spots_clean.xlsx
      data/processed/quality_report.txt
"""
import pandas as pd
import os

RAW = "data/raw/scenic_spots_raw.xlsx"
OUT = "data/processed/scenic_spots_clean.xlsx"
REPORT = "data/processed/quality_report.txt"

# ---------------------------------------------------------------
# 地标 -> 真实所在城市 映射表
# 用于检测"名称是 A 地标，却被归到 B 城市"的污染记录
# ---------------------------------------------------------------
LANDMARKS = {
    # 西安
    "兵马俑": "西安", "秦始皇帝陵": "西安", "大雁塔": "西安", "华清宫": "西安",
    # 武汉
    "黄鹤楼": "武汉",
    # 上海
    "东方明珠": "上海", "外滩": "上海", "豫园": "上海",
    # 杭州
    "西湖": "杭州", "灵隐寺": "杭州", "千岛湖": "杭州",
    # 南京
    "中山陵": "南京", "明孝陵": "南京", "总统府": "南京",
    # 北京
    "故宫": "北京", "八达岭": "北京", "慕田峪": "北京", "天安门": "北京",
    "颐和园": "北京",
    # 泰安（不属于济南/青岛）
    "泰山": "泰安", "泰安": "泰安",
    # 黄山（不属于南京/杭州）
    "黄山": "黄山", "西递": "黄山", "宏村": "黄山",
    # 山西
    "壶口": "山西",
    # 青岛
    "崂山": "青岛", "栈桥": "青岛",
    # 济南
    "趵突泉": "济南", "大明湖": "济南",
    # 成都
    "都江堰": "成都", "武侯祠": "成都", "杜甫草堂": "成都",
    # 重庆
    "洪崖洞": "重庆", "磁器口": "重庆",
}


def guess_real_city(name: str):
    """根据景点名称猜真实城市；返回 None 表示无法判断。"""
    for kw, city in LANDMARKS.items():
        if kw in str(name):
            return city
    return None


def clean():
    os.makedirs("data/processed", exist_ok=True)
    df = pd.read_excel(RAW)
    n_raw = len(df)

    lines = []
    lines.append("=" * 50)
    lines.append("数据质量报告")
    lines.append("=" * 50)
    lines.append(f"原始记录数: {n_raw}")

    # ---- 步骤 1: 跨城市污染检测 ----
    df["_real_city"] = df["name"].apply(guess_real_city)
    polluted = df[(df["_real_city"].notna()) & (df["_real_city"] != df["city"])]
    n_polluted = len(polluted)
    lines.append("")
    lines.append(f"[步骤1] 跨城市污染检测")
    lines.append(f"  检出归属错误记录: {n_polluted} 条 ({n_polluted/n_raw*100:.1f}%)")
    if n_polluted:
        by_city = polluted.groupby("city").size().to_dict()
        lines.append(f"  分布: {by_city}")

    df = df[df["_real_city"].isna() | (df["_real_city"] == df["city"])].copy()
    df = df.drop(columns=["_real_city"])
    lines.append(f"  清洗后剩余: {len(df)} 条")

    # ---- 步骤 2: 缺失值处理 ----
    lines.append("")
    lines.append(f"[步骤2] 缺失值处理")
    n_missing = df["rating"].isna().sum()
    df["rating"] = df.groupby("city")["rating"].transform(lambda x: x.fillna(x.mean()))
    df["rating"] = df["rating"].fillna(df["rating"].mean())
    df["comment_count"] = df["comment_count"].fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    lines.append(f"  评分缺失修复: {n_missing} 条")

    # ---- 步骤 3: 去重 ----
    before = len(df)
    df = df.drop_duplicates(subset=["city", "name"]).reset_index(drop=True)
    lines.append("")
    lines.append(f"[步骤3] 去重")
    lines.append(f"  删除重复: {before - len(df)} 条")

    # ---- 步骤 4: 派生字段 ----
    df["primary_tag"] = df["tags"].fillna("人文景观").str.split(",").str[0]

    def price_level(p):
        if p == 0:
            return "免费"
        if p <= 50:
            return "低价(≤50)"
        if p <= 100:
            return "中价(51-100)"
        return "高价(>100)"
    df["price_level"] = df["price"].apply(price_level)

    df["is_high_rated"] = (df["rating"] >= 4.5).astype(int)
    lines.append("")
    lines.append(f"[步骤4] 派生字段: primary_tag / price_level / is_high_rated")

    # ---- 汇总 ----
    lines.append("")
    lines.append("=" * 50)
    lines.append(f"清洗完成: {n_raw} -> {len(df)} 条")
    lines.append(f"保留率: {len(df)/n_raw*100:.1f}%")
    lines.append("=" * 50)

    df.to_excel(OUT, index=False)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))
    print(f"\n已输出: {OUT}")
    print(f"已输出: {REPORT}")


if __name__ == "__main__":
    clean()
