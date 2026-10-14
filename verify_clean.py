# -*- coding: utf-8 -*-
"""verify_clean.py — 清洗结果全量验证（改完 clean.py 必跑）"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
sys.stdout.reconfigure(encoding="utf-8")
from foreign_map import FOREIGN  # noqa: E402

XLSX = "data/processed/scenic_spots_clean.xlsx"
df = pd.read_excel(XLSX)
raw = pd.read_excel("data/raw/scenic_spots_raw.xlsx")

ok, bad = [], []


def chk(cond, msg):
    (ok if cond else bad).append(msg)


print("=" * 70)
print("清洗结果验证")
print("=" * 70)

# ---- 1. 无残留外地景点 ----
hit = [n for n in df["name"] if str(n) in FOREIGN]
chk(len(hit) == 0, f"① 核验表外地景点残留 = {len(hit)}（应为 0）  {hit[:5]}")

# ---- 2. 无跨城市重复 sight_id ----
g = df.groupby("sight_id")["city"].nunique()
chk((g > 1).sum() == 0, f"② 跨城市重复 sight_id = {int((g>1).sum())} 组（应为 0）")

# ---- 3. 城市数 = 10 ----
chk(df["city"].nunique() == 10, f"③ 城市数 = {df['city'].nunique()}（应为 10）")

# ---- 4. 每城景点数平衡 ----
vc = df["city"].value_counts()
chk(vc.min() >= 8, f"④ 每城景点数 {vc.min()}~{vc.max()}（最少应 ≥8）")

# ---- 5. 无伪造字段 ----
fake = [c for c in ["latitude", "longitude", "distance"] if c in df.columns]
chk(len(fake) == 0, f"⑤ 伪造字段残留 = {fake}（应为空）")

# ---- 6. 无伪零分 ----
chk(int(((df["rating"] == 0) & (df["comment_count"] == 0)).sum()) == 0,
    "⑥ 伪零分记录（评分=0 且评论=0）= 0")

# ---- 7. 同城同名重复 ----
chk(int(df.duplicated(subset=["city", "name"]).sum()) == 0, "⑦ 同城同名重复 = 0")

# ---- 8. 关键景点抽查（应保留） ----
KEEP = ["上海迪士尼度假区充满欢乐童真的梦幻乐园", "黄鹤楼", "都江堰景区",
        "秦始皇帝陵博物院(兵马俑)", "崂山风景区", "趵突泉景区", "千岛湖景区",
        "中山陵" , "杜甫草堂", "大足石刻", "红山森林动物园"]
rows = df["name"].astype(str).tolist()
miss = [k for k in KEEP if not any(k in n or n in k for n in rows)]
chk(len(miss) == 0, f"⑧ 关键景点误杀 = {len(miss)} {miss}")

# ---- 9. 关键污染样本（应已剔除） ----
FOREIGN_SAMPLES = ["蜈支洲岛", "稻城亚丁", "武陵源", "神农顶风景区", "蓬莱阁",
                   "乐山大佛", "乌镇东栅景区", "大九湖国家湿地公园", "太白山国家森林公园",
                   "孔庙", "刘公岛景区", "隐水洞", "九寨沟风景区"]
left = [k for k in FOREIGN_SAMPLES if any(k == n for n in rows)]
chk(len(left) == 0, f"⑨ 污染样本残留 = {len(left)} {left}")

# ---- 10. 覆盖统计 ----
n_c = int(df["comment_count"].sum())
n_price = int((df["price"] > 0).sum())
print(f"\n概览：{len(raw)} → {len(df)} 条（保留 {len(df)/len(raw)*100:.1f}%）")
print(f"  城市 {df['city'].nunique()} 个 | 唯一 sight_id {df['sight_id'].nunique()} 个")
print(f"  评论总数 {n_c:,} | 有价格 {n_price} 条 | 有评分 {int(df['rating'].notna().sum())} 条")
print("\n各城市：")
for c in ["北京", "上海", "重庆", "武汉", "成都", "西安", "青岛", "济南", "杭州", "南京"]:
    sub = df[df["city"] == c]
    print(f"  {c}: {len(sub):2d} 个景点 | 评论 {int(sub['comment_count'].sum()):>8,}")

print("\n" + "=" * 70)
for m in ok:
    print("  ✅", m)
for m in bad:
    print("  ❌", m)
print("=" * 70)
print(f"结果：{len(ok)} 通过 / {len(bad)} 失败")
sys.exit(1 if bad else 0)
