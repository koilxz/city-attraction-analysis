# -*- coding: utf-8 -*-
"""
clean.py — 数据清洗与质量修复（v2）

═══ 为什么有 v2 ═══
原始数据的「跨城市污染」比 v1 判断的更严重：
  · 同一景点被重复抓进多个城市的列表页（sight_id 相同）—— 123 条
  · v1 只用 34 个地标关键词，检出 44 条，明显低估
  · v1 曾设想「用经纬度反查城市」，但复核发现
    latitude/longitude 是【随机生成】的（见 spider_real.py），前提不成立

═══ v2 的算法 ═══
步骤 1  字段审计：识别出哪些字段不可信
步骤 2  从 description 提取「定位信号」（锚定省份 / 锚定城市）
步骤 3  按 sight_id 分组（同一景点被多次抓取）→ 评分选出「真身」城市，
        其余判为污染剔除
步骤 4  单条记录：若定位信号与标注城市冲突 → 判为污染剔除
步骤 5  删除伪造字段（latitude / longitude / distance）
步骤 6  常规修复：伪零分 → 缺失填补 → 派生字段

输入：data/raw/scenic_spots_raw.xlsx
输出：data/processed/scenic_spots_clean.xlsx
      data/processed/quality_report.txt
"""
import os
import re
import pandas as pd
import numpy as np

RAW = "data/raw/scenic_spots_raw.xlsx"
OUT = "data/processed/scenic_spots_clean.xlsx"
REPORT = "data/processed/quality_report.txt"

# ---------------------------------------------------------------
# 常量
# ---------------------------------------------------------------
# 10 个目标城市 → 所属省级行政区
CITY_PROV = {
    "北京": "北京", "上海": "上海", "重庆": "重庆",
    "武汉": "湖北", "成都": "四川", "西安": "陕西",
    "青岛": "山东", "济南": "山东", "杭州": "浙江", "南京": "江苏",
}
CITIES = list(CITY_PROV)

PROVINCES = [
    "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "台湾",
    "内蒙古", "广西", "西藏", "宁夏", "新疆", "香港", "澳门",
]
PROV_ALT = "|".join(sorted(PROVINCES, key=len, reverse=True))

# 10 城下辖的县级市/区（避免把「都江堰市」误判为外地）
SUBCITY = {
    "都江堰", "崇州", "邛崃", "彭州", "简阳",           # 成都
    "胶州", "平度", "莱西", "即墨",                    # 青岛
    "章丘", "济阳", "莱芜", "长清",                    # 济南
    "溧阳", "高淳", "溧水",                            # 南京
    "临安", "建德", "桐庐", "淳安", "富阳",            # 杭州
    "嘉鱼", "咸宁", "黄石", "孝感", "黄冈", "荆州",    # 湖北
    "宝山", "嘉定", "松江", "青浦", "奉贤", "崇明",    # 上海
    "昌平", "怀柔", "密云", "延庆", "房山", "通州",    # 北京
    "临潼", "长安", "鄠邑", "周至", "蓝田",            # 西安
    "永川", "合川", "江津", "长寿", "綦江", "大足",    # 重庆
}

# 定位动词：只有出现在这些词之后的省份/城市才被认为描述「本景点所在地」
LOC_VERB = (r"(?:位于|坐落于|座落于|地处|隶属(?:于)?|现属|归属|属于|"
            r"屹立于|处在|毗邻|横跨|在)")
RE_PROV = re.compile(LOC_VERB + r"[^。；;\n]{0,18}?(" + PROV_ALT + r")(?:省|市|自治区|壮族自治区|回族自治区|维吾尔自治区)")
RE_CITY_RAW = re.compile(LOC_VERB + r"[^。；;\n]{0,18}?([\u4e00-\u9fa5]{2,5}?)市")

# 非目标城市（数据里出现过的外地地级市），用于名称判定
OTHER_CITIES = {
    "南昌", "九江", "岳阳", "苏州", "无锡", "常州", "嘉兴", "泰安", "黄山",
    "张家界", "保定", "秦皇岛", "忻州", "广安", "三亚", "承德", "洛阳",
    "扬州", "镇江", "绍兴", "宁波", "芜湖", "蚌埠", "襄阳", "宜昌", "荆州",
}

# 地标 → 真实所在城市（v1 沿用 + 扩充；只保留高置信度的）
LANDMARKS = {
    "兵马俑": "西安", "秦始皇帝陵": "西安", "大雁塔": "西安", "华清宫": "西安",
    "黄鹤楼": "武汉",
    "东方明珠": "上海", "外滩": "上海", "豫园": "上海", "迪士尼": "上海",
    "西湖": "杭州", "灵隐寺": "杭州", "千岛湖": "杭州",
    "中山陵": "南京", "明孝陵": "南京", "总统府": "南京",
    "故宫": "北京", "八达岭": "北京", "慕田峪": "北京", "天安门": "北京", "颐和园": "北京",
    "泰山": "泰安", "黄山": "黄山", "西递": "黄山", "宏村": "黄山", "齐云山": "黄山",
    "壶口": "山西", "崂山": "青岛", "栈桥": "青岛",
    "趵突泉": "济南", "大明湖": "济南",
    "都江堰": "成都", "武侯祠": "成都", "杜甫草堂": "成都",
    "洪崖洞": "重庆", "磁器口": "重庆",
    # 以下为 v2 新增：武汉列表里混入的江西/湖南景点
    "庐山": "九江", "三叠泉": "九江", "白鹿洞": "九江",
    "滕王阁": "南昌", "南昌": "南昌",
    "岳阳楼": "岳阳", "屈子": "岳阳", "君山": "岳阳", "洞庭": "岳阳",
    "张家界": "张家界", "天门山": "张家界",
    "凤凰古城": "湘西", "芙蓉镇": "湘西", "矮寨": "湘西",
    "华蓥山": "广安",
    # 北京列表里混入的天津/河北景点
    "天津": "天津", "海河": "天津", "白洋淀": "保定", "白石山": "保定",
    "雁门关": "忻州", "五台山": "忻州", "天下第一关": "秦皇岛", "直隶总督署": "保定",
}


# ---------------------------------------------------------------
# 定位信号提取
# ---------------------------------------------------------------
def extract_signals(desc):
    """从简介提取 (锚定省份, 锚定城市)。取不到返回 (None, None)。"""
    if pd.isna(desc):
        return None, None
    s = str(desc)

    prov = None
    m = RE_PROV.search(s)
    if m:
        prov = m.group(1)

    city = None
    m2 = RE_CITY_RAW.search(s)
    if m2:
        raw = m2.group(1)
        for p in PROVINCES:                       # 去掉误吞的省份前缀
            if raw.startswith(p) and len(raw) > len(p):
                raw = raw[len(p):]
                break
        raw = raw.replace("省", "").replace("市", "")
        if raw and raw not in PROVINCES:
            city = raw

    return prov, city


def landmark_city(name):
    """名称命中地标表则返回其真实城市，否则 None"""
    for kw, c in LANDMARKS.items():
        if kw in str(name):
            return c
    return None


def name_other_place(name, own):
    """名称里是否含「其他城市名」「其他省份名」或已知外地城市名"""
    s = str(name)
    for c in CITIES:
        if c != own and c in s:
            return c
    for c in OTHER_CITIES:
        if c in s:
            return c
    own_prov = CITY_PROV[own]
    for p in PROVINCES:
        if p != own_prov and p in s:
            return p
    return None


def is_foreign(r):
    """该记录是否「明显不属于」其标注城市（强信号）"""
    if has(r["_landmark"]) and r["_landmark"] != r["city"]:
        return True
    if has(r["_name_other"]):
        return True
    if has(r["_citysig"]) and r["_citysig"] != r["city"] \
            and not is_subcity_of(r["_citysig"], r["city"]):
        return True
    if has(r["_prov"]) and r["_prov"] != r["_own_prov"]:
        return True
    return False


def is_subcity_of(city_name, own):
    """city_name 是否为 own 的下辖县级市（若是，则不视为外地）"""
    return city_name in SUBCITY


def has(x):
    """⚠️ 非空判定：注意 None 存进 DataFrame 会变成 NaN，
    而 NaN is not None 恒为 True —— 必须用 pd.isna 一起判。"""
    return x is not None and not pd.isna(x)


# ---------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------
def clean():
    os.makedirs("data/processed", exist_ok=True)
    df = pd.read_excel(RAW)
    n_raw = len(df)
    L = []

    def log(s=""):
        L.append(s)
        print(s)

    log("=" * 62)
    log("数据质量报告")
    log("=" * 62)
    log(f"原始记录数: {n_raw}")

    # ---------- 步骤 1：字段审计 ----------
    log("")
    log("[步骤1] 字段可信度审计")
    log("  ✅ 可信(详情页/评论API): name, rating, comment_count, price, level,")
    log("                          open_time, tags, description, all_comments")
    log("  ❌ city      = 「所属列表页城市」——推荐景点会错归")
    log("  🟡 address   = 详情页取不到时退化为「{城市}市」")
    log("  ❌ latitude / longitude = 城市中心 ± 0.4° 【随机生成】")
    log("  ❌ distance  = 随机数(2~75km)")
    log("  ⇒ 后三个字段不可用于任何分析，本脚本直接删除")

    # ---------- 步骤 2：定位信号 ----------
    df["_pos"] = df.groupby("city").cumcount() + 1
    df["_size"] = df.groupby("city")["city"].transform("size")
    sig = df["description"].apply(extract_signals)
    df["_prov"] = [x[0] for x in sig]
    df["_citysig"] = [x[1] for x in sig]
    df["_own_prov"] = df["city"].map(CITY_PROV)
    df["_landmark"] = df["name"].apply(landmark_city)
    df["_name_other"] = df.apply(lambda r: name_other_place(r["name"], r["city"]), axis=1)

    log("")
    log("[步骤2] 从简介提取定位信号")
    log(f"  提取到省份: {int(df['_prov'].notna().sum())} 条")
    log(f"  提取到城市: {int(df['_citysig'].notna().sum())} 条")

    # ---------- 步骤 3：sight_id 跨城市去重 ----------
    def score(r):
        s = 0.0
        if has(r["_landmark"]):
            s += 8.0 if r["_landmark"] == r["city"] else -10.0
        if r["city"] in str(r["name"]):
            s += 3.0
        if has(r["_name_other"]):
            s -= 6.0
        if has(r["_citysig"]):
            if r["_citysig"] == r["city"]:
                s += 3.0
            elif not is_subcity_of(r["_citysig"], r["city"]):
                s -= 6.0
        if has(r["_prov"]):
            s += 2.0 if r["_prov"] == r["_own_prov"] else -5.0
        s += (1.0 - (r["_pos"] - 1) / max(1, r["_size"] - 1))
        return s

    drop_idx, reasons = [], {}

    groups = [g for _, g in df.groupby("sight_id") if g["city"].nunique() > 1]
    dup_ids = set(g["sight_id"].iloc[0] for g in groups)
    for g in groups:
        g = g.copy()
        g["_foreign"] = g.apply(is_foreign, axis=1)
        g["_score"] = g.apply(score, axis=1)

        # 情形 A：组内所有副本都不属于各自的标注城市
        #   （如「拙政园」同时出现在杭州/上海/南京，但它其实在苏州）
        #   ⇒ 整组剔除，而不是"矮子里拔将军"
        if g["_foreign"].all():
            for idx in g.index:
                drop_idx.append(idx)
                reasons[idx] = "跨城市重复且全组归属外地"
            continue

        # 情形 B：先在「非外地」的副本里选真身，保留最优的一条
        #   ⚠️ 注意：必须把「外地副本」单独剔除，不能只在过滤后的框架里丢落选者
        for idx in g[g["_foreign"]].index:
            drop_idx.append(idx)
            reasons[idx] = "跨城市重复(外地副本)"
        gk = g[~g["_foreign"]].sort_values(["_score", "_pos"], ascending=[False, True])
        for idx in gk.index[1:]:
            drop_idx.append(idx)
            reasons[idx] = "跨城市重复(sight_id 相同)"

    # ---------- 步骤 4：单条记录的定位冲突 ----------
    def why_foreign(r):
        """给出「判为外地」的具体理由（用于报告）"""
        if has(r["_landmark"]) and r["_landmark"] != r["city"]:
            return f"地标归属冲突({r['_landmark']})"
        if has(r["_name_other"]):
            return f"名称含外地地名({r['_name_other']})"
        if has(r["_citysig"]) and r["_citysig"] != r["city"] \
                and not is_subcity_of(r["_citysig"], r["city"]):
            return f"简介定位为{r['_citysig']}"
        if has(r["_prov"]) and r["_prov"] != r["_own_prov"]:
            return f"简介定位为{r['_prov']}省"
        return None

    for idx, r in df[~df["sight_id"].isin(dup_ids)].iterrows():
        why = why_foreign(r)
        if why:
            drop_idx.append(idx)
            reasons[idx] = why
    n_dup = len([i for i in drop_idx if reasons.get(i, "").startswith("跨城市重复")])
    log("")
    log("[步骤3] 跨城市去重（按 sight_id）")
    log(f"  跨城市重复的 sight_id : {len(groups)} 组")
    log(f"  剔除记录              : {n_dup} 条")

    log("")
    log("[步骤4] 单条记录的定位冲突")
    other = [i for i in drop_idx if not reasons.get(i, "").startswith("跨城市重复")]
    log(f"  剔除记录: {len(other)} 条")
    for i in other[:18]:
        r = df.loc[i]
        log(f"    [{r['city']}] {str(r['name'])[:26]:<28} ← {reasons[i]}")

    cleaned = df.drop(index=set(drop_idx)).copy()
    log("")
    log(f"  合计剔除: {len(drop_idx)} 条   剩余: {len(cleaned)} 条")

    # ---------- 步骤 5：删除伪造字段 ----------
    fake_cols = [c for c in ["latitude", "longitude", "distance"] if c in cleaned.columns]
    cleaned = cleaned.drop(columns=fake_cols)
    log("")
    log("[步骤5] 删除伪造字段（非真实采集值）")
    log(f"  已删除: {fake_cols}")

    # ---------- 步骤 6：常规修复 ----------
    log("")
    log("[步骤6] 常规数值修复")
    pseudo = ((cleaned["rating"] == 0) & (cleaned["comment_count"] == 0))
    n_pseudo = int(pseudo.sum())
    cleaned.loc[pseudo, "rating"] = np.nan
    n_missing = int(cleaned["rating"].isna().sum())
    cleaned["rating"] = cleaned.groupby("city")["rating"].transform(
        lambda x: x.fillna(x.mean()))
    cleaned["rating"] = cleaned["rating"].fillna(cleaned["rating"].mean())
    cleaned["comment_count"] = cleaned["comment_count"].fillna(0).astype(int)
    cleaned["price"] = pd.to_numeric(cleaned["price"], errors="coerce").fillna(0)
    log(f"  伪零分修正(评分=0且评论=0 → 缺失): {n_pseudo} 条")
    log(f"  评分缺失修复(按城市均值填补)     : {n_missing} 条")

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=["city", "name"]).reset_index(drop=True)
    log(f"  去重(同城同名)                   : {before - len(cleaned)} 条")

    # ---------- 步骤 7：派生字段 ----------
    cleaned["primary_tag"] = cleaned["tags"].fillna("人文景观").str.split(",").str[0]

    def price_level(p):
        if p == 0:
            return "免费"
        if p <= 50:
            return "低价(≤50)"
        if p <= 100:
            return "中价(51-100)"
        return "高价(>100)"
    cleaned["price_level"] = cleaned["price"].apply(price_level)
    cleaned["is_high_rated"] = (cleaned["rating"] >= 4.5).astype(int)

    cleaned = cleaned[[c for c in cleaned.columns if not c.startswith("_")]]
    log("")
    log("[步骤7] 派生字段: primary_tag / price_level / is_high_rated")

    # ---------- 汇总 ----------
    log("")
    log("=" * 62)
    log(f"清洗完成: {n_raw} -> {len(cleaned)} 条")
    log(f"保留率  : {len(cleaned)/n_raw*100:.1f}%")
    log("")
    log("各城市景点数变化:")
    for c in CITIES:
        a = int((df["city"] == c).sum())
        b = int((cleaned["city"] == c).sum())
        log(f"  {c}: {a} -> {b}  (-{a-b})")
    log("=" * 62)

    cleaned.to_excel(OUT, index=False)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

    print(f"\n已输出: {OUT}")
    print(f"已输出: {REPORT}")


if __name__ == "__main__":
    clean()
