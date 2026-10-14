# -*- coding: utf-8 -*-
"""
去哪儿旅行景点动态爬虫
- 列表页: requests 提取景点链接 + sight_id
- 详情页: requests 解析评分/评论数/等级/地址/简介/价格
- 评论API: https://piao.qunar.com/ticket/detailLight/sightCommentList.json 获取真实用户评论
- 情感分析: SnowNLP 对真实评论打分

⚠️ 已知数据局限（重要）
  1. city 字段 = 「所属列表页城市」。而列表页除本城景点外，还混有周边地区的推荐景点，
     导致部分非本地景点被错误归类（跨城市污染）。清洗见 clean.py。
  2. latitude / longitude / distance 为【随机占位值】，非真实坐标与距离，
     不可用于地理分析。原因：站点页面未暴露该数据。
  3. address 优先取详情页文本，取不到时退化为「{城市}市」。

运行：在项目根目录执行  python src/spider_real.py
输出：data/raw/scenic_spots_raw.xlsx 、data/raw/real_comments.xlsx
"""
import requests, re, time, random, json, os
import pandas as pd, numpy as np
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
from snownlp import SnowNLP
from collections import Counter

# ===================== 配置 =====================
CITIES = ["重庆", "北京", "青岛", "济南", "成都", "武汉", "南京", "杭州", "西安", "上海"]
TARGET_PER_CITY = 50
BASE_URL = "https://piao.qunar.com"
CITY_LIST_URL = "https://piao.qunar.com/index.htm?region={city}"
COMMENT_API = "https://piao.qunar.com/ticket/detailLight/sightCommentList.json"

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

CITY_COORDS = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737), "重庆": (29.5630, 106.5516),
    "成都": (30.5728, 104.0668), "杭州": (30.2741, 120.1551), "西安": (34.3416, 108.9398),
    "南京": (32.0603, 118.7969), "武汉": (30.5928, 114.3055), "青岛": (36.0671, 120.3826),
    "济南": (36.6512, 117.1201),
}

TAG_KEYWORDS = {
    '历史古迹': ['遗址', '古迹', '古城', '长城', '故宫', '皇陵', '石刻', '文物', '博物馆', '陵', '宫', '兵马俑', '书院'],
    '自然风光': ['山', '湖', '瀑布', '峡谷', '溶洞', '森林', '公园', '峰', '泉', '江', '海', '湿地', '草原', '冰川'],
    '主题乐园': ['乐园', '欢乐谷', '方特', '水上', '影视城', '迪士尼', '海洋馆', '游乐'],
    '人文景观': ['寺', '塔', '庙', '古镇', '老街', '胡同', '广场', '桥', '园林', '楼'],
    '休闲娱乐': ['温泉', '度假', '夜游', '观光', '演出', '演艺', '剧场'],
    '文化体验': ['文化', '非遗', '科普', '博览', '美术馆', '艺术'],
    '亲子游玩': ['动物园', '海洋', '亲子', '植物园', '熊猫'],
    '红色旅游': ['红色', '革命', '烈士', '纪念馆', '旧址', '抗战'],
    '宗教文化': ['佛', '道', '教堂', '禅', '大佛', '清真', '阁'],
    '城市地标': ['外滩', '天安门', '地标', '明珠', '塔', '广场'],
}

FREE_KEYWORDS = ["免费", "无门票", "免票", "免费开放", "免入园费", "博物院", "博物馆", "纪念馆", "城市广场"]

session = requests.Session()
session.headers.update({
    'User-Agent': USER_AGENTS[0],
    'Accept-Language': 'zh-CN,zh;q=0.9',
})

def get_headers(referer=None):
    h = {'User-Agent': random.choice(USER_AGENTS)}
    if referer:
        h['Referer'] = referer
        h['X-Requested-With'] = 'XMLHttpRequest'
        h['Accept'] = 'application/json, text/javascript, */*; q=0.01'
    return h

# ===================== 列表页提取 =====================
def extract_sight_links(city_name):
    """提取城市景点列表，返回 [{name, detail_url, sight_id, list_desc, list_price}]"""
    url = CITY_LIST_URL.format(city=quote(city_name))
    for attempt in range(3):
        try:
            r = session.get(url, headers=get_headers(), timeout=15)
            time.sleep(random.uniform(0.5, 1.0))
            if r.status_code == 200 and len(r.text) > 1200:
                break
        except Exception as e:
            print(f'  [{city_name}] 列表页请求失败({attempt+1}): {e}')
            time.sleep(2)
    else:
        print(f'  [{city_name}] 列表页加载失败')
        return []

    soup = BeautifulSoup(r.text, 'html.parser')
    links = soup.find_all('a', href=re.compile(r'/ticket/detail_(\d+)\.html'))
    seen = set()
    short_id, long_id = [], []
    for link in links:
        href = link.get('href', '')
        m = re.search(r'detail_(\d+)', href)
        if not m:
            continue
        sight_id = m.group(1)
        full_url = urljoin(BASE_URL, href.split('?')[0])
        if full_url in seen:
            continue
        seen.add(full_url)
        name = link.get_text(strip=True)
        if len(name) < 2:
            continue
        parent = link.find_parent('div', class_=re.compile('mp-section-content-info'))
        desc, price = "", ""
        if parent:
            text = parent.get_text(strip=True)
            pm = re.search(r'[¥￥]([\d.]+)起?', text)
            if pm:
                price = pm.group(0)
            desc = re.sub(r'[¥￥][\d.]+起?', '', text).strip()
        # 兜底：如果父div没抓到价格，从链接文本本身提取
        if not price:
            pm2 = re.search(r'[¥￥]([\d.]+)起?', name)
            if pm2:
                price = pm2.group(0)
        info = {"name": name, "detail_url": full_url, "sight_id": sight_id,
                "list_desc": desc, "list_price": price}
        if len(sight_id) <= 6:
            short_id.append(info)
        else:
            long_id.append(info)
    all_sights = short_id + long_id
    print(f'  [{city_name}] 短ID:{len(short_id)} 长ID:{len(long_id)} 合计:{len(all_sights)}')
    return all_sights

# ===================== 详情页解析 =====================
def parse_detail(sight_id, city_name, list_data):
    """请求详情页，从.mp-description统一解析评分/评论数/价格/等级/地址/简介"""
    url = f"https://piao.qunar.com/ticket/detail_{sight_id}.html"
    referer = f"https://piao.qunar.com/index.htm?region={quote(city_name)}"
    try:
        r = session.get(url, headers=get_headers(referer), timeout=15)
        time.sleep(random.uniform(0.4, 0.8))
    except Exception as e:
        print(f'    详情页请求失败: {e}')
        return None
    if r.status_code != 200:
        return None
    html = r.text
    soup = BeautifulSoup(html, 'html.parser')

    # 核心：从 .mp-description 文本统一解析
    desc_el = soup.select_one('.mp-description')
    desc_text = desc_el.get_text(strip=True) if desc_el else ""

    # 名称：取描述开头到"XA景区"或"位置"之前
    name = list_data["name"]
    nm = re.match(r'(.+?)(\d)A景区', desc_text)
    if nm:
        name = nm.group(1).strip()
    else:
        nm2 = re.match(r'(.+?)位置[:：]', desc_text)
        if nm2:
            name = nm2.group(1).strip()
    # 清理名称中的价格残留
    name = re.sub(r'[¥￥][\d.]+起?', '', name).strip()
    if len(name) < 2:
        name = list_data["name"]

    # 等级：从描述中 "(\d)A景区"
    level = ""
    lm = re.search(r'(\d)A景区', desc_text)
    if lm:
        level = "A" * int(lm.group(1))

    # 评分：从描述中 "X.X/5分"
    rating = None
    rm = re.search(r'([\d.]+)\s*/\s*5\s*分', desc_text)
    if rm:
        rating = float(rm.group(1))
    if rating is None:
        rm2 = re.search(r'用户点评[:：]\s*([\d.]+)', desc_text)
        if rm2:
            rating = float(rm2.group(1))

    # 评论数
    comment_total = None
    cwm = re.search(r'([\d.]+)\s*万\s*条评论', desc_text)
    if cwm:
        comment_total = int(float(cwm.group(1)) * 10000)
    else:
        cnm = re.search(r'(\d+)\s*条评论', desc_text)
        if cnm:
            comment_total = int(cnm.group(1))

    # 地址：从描述中 "位置：XXX查看地图"
    address = ""
    am = re.search(r'位置[:：]\s*(.+?)(?:查看地图|用户点评)', desc_text)
    if am:
        address = am.group(1).strip()[:80]
    if not address:
        address = f"{city_name}市"

    # 价格：从描述中解析，或从页面解析
    price = None
    # 描述中的价格 (在评论数之后)
    pm = re.search(r'(?:条评论)?\s*[¥￥]\s*([\d.]+)', desc_text)
    if pm:
        price = float(pm.group(1))
    if price is None:
        # 页面中的第一个有效价格
        all_prices = re.findall(r'[¥￥]\s*([\d.]+)', html)
        for p in all_prices:
            pv = float(p)
            if 0 < pv < 9999:
                price = pv
                break
    if price is None:
        price = parse_price(list_data.get("list_price", ""))
    if price is None:
        # 兜底：从列表页链接文本中提取（链接文本常含 ¥XX起）
        nm_price = re.search(r'[¥￥]\s*([\d.]+)起?', list_data.get("name", ""))
        if nm_price:
            price = float(nm_price.group(1))
    if price is None:
        price = 0.0

    # 简介
    intro = soup.select_one('.mp-charact-intro')
    description = intro.get_text(strip=True)[:300] if intro else (list_data.get("list_desc") or "暂无简介")

    # 开放时间
    open_time = "未知"
    tdiv = soup.select_one('.mp-charact-time')
    if tdiv:
        open_time = tdiv.get_text(strip=True).replace("开放时间：", "")[:60]

    tags = infer_tags(name, description)
    real_free = judge_real_free(name, description, list_data.get("list_price", ""))

    return {
        "city": city_name, "sight_id": sight_id, "name": name,
        "rating": rating, "comment_count": comment_total, "tags": tags,
        "price": price, "level": level, "address": address,
        "open_time": open_time, "description": description,
        "is_real_free": real_free, "list_price": list_data.get("list_price", ""),
        "detail_url": list_data["detail_url"]
    }

def parse_price(text):
    if not text:
        return None
    if any(k in str(text) for k in ["暂无", "待定", "无报价"]):
        return None
    m = re.search(r'[¥￥]\s*([\d.]+)', str(text))
    return float(m.group(1)) if m else None

def infer_tags(name, desc):
    text = f"{name}{desc}"
    res = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            res.append(tag)
    return ",".join(res[:3]) if res else "人文景观"

def judge_real_free(name, desc, list_price):
    full = f"{name}{desc}{list_price}"
    return any(w in full for w in FREE_KEYWORDS)

# ===================== 评论API（核心动态部分） =====================
def fetch_real_comments(sight_id, city_name, max_pages=3):
    """调用去哪儿评论API获取真实用户评论"""
    comments = []
    referer = f"https://piao.qunar.com/ticket/detail_{sight_id}.html"
    for page in range(1, max_pages + 1):
        params = {
            'sightId': sight_id,
            'index': str(page),
            'page': str(page),
            'pageSize': '10',
            'tagType': '0',  # 0=全部
        }
        try:
            r = session.get(COMMENT_API, params=params, headers=get_headers(referer), timeout=15)
            time.sleep(random.uniform(0.5, 1.2))
            if r.status_code != 200:
                break
            ct = r.headers.get('content-type', '')
            if 'json' not in ct:
                break
            try:
                data = r.json()
            except Exception:
                break
            if not data.get('ret'):
                break
            clist = data.get('data', {}).get('commentList', [])
            if not clist:
                break
            for c in clist:
                content = c.get('content', '').strip()
                if not content or len(content) < 5:
                    continue
                comments.append({
                    'author': c.get('author', '匿名'),
                    'content': content,
                    'score': c.get('score', 0),
                    'date': c.get('date', ''),
                    'commentId': c.get('commentId', ''),
                })
        except Exception as e:
            print(f'    评论API第{page}页失败: {str(e)[:60]}')
            break
    return comments

# ===================== 情感分析 =====================
def sentiment_analysis(comments):
    """对真实评论做SnowNLP情感分析"""
    if not comments:
        return 0.5, "中性", []
    scores = []
    details = []
    for c in comments:
        try:
            s = SnowNLP(c['content']).sentiments
            scores.append(s)
            label = "正面" if s >= 0.6 else ("负面" if s <= 0.4 else "中性")
            details.append({'content': c['content'], 'score': round(s, 4), 'label': label,
                            'date': c.get('date', ''), 'author': c.get('author', '')})
        except:
            scores.append(0.5)
    avg = round(float(np.mean(scores)), 4) if scores else 0.5
    label = "正面" if avg >= 0.6 else ("负面" if avg <= 0.4 else "中性")
    return avg, label, details

# ===================== 主流程 =====================
def main():
    os.makedirs("data/raw", exist_ok=True)
    output_xlsx = "data/raw/scenic_spots_raw.xlsx"
    comments_xlsx = "data/raw/real_comments.xlsx"

    all_data = []
    all_comments = []
    # 断点续传：读取已采集数据
    done_cities = set()
    if os.path.exists(output_xlsx):
        try:
            old = pd.read_excel(output_xlsx)
            done_cities = set(old['city'].unique()) if 'city' in old.columns else set()
            all_data = old.to_dict('records')
            print(f"断点续传：已有 {len(all_data)} 条数据，已完成城市: {done_cities}")
        except:
            pass

    print('='*60)
    print('去哪儿旅行景点动态爬虫（真实数据版）')
    print(f'目标: {len(CITIES)}城市 × {TARGET_PER_CITY}景点 = {len(CITIES)*TARGET_PER_CITY}条')
    print('='*60)

    for city in CITIES:
        if city in done_cities and len([d for d in all_data if d.get('city')==city]) >= TARGET_PER_CITY:
            print(f'\n[{city}] 已完成，跳过')
            continue
        print(f"\n{'='*48}\n采集城市: {city}\n{'='*48}")
        sights = extract_sight_links(city)
        if not sights:
            print(f"  {city} 无景点链接")
            continue

        city_data = []
        for idx, item in enumerate(sights):
            if len(city_data) >= TARGET_PER_CITY:
                break
            sid = item["sight_id"]
            name = item["name"]
            # 跳过长ID（详情页无数据）
            if len(sid) > 8:
                continue
            print(f"  ({idx+1}/{len(sights)}) {name} [id={sid}]", end=" ")

            # 详情页
            detail = parse_detail(sid, city, item)
            if not detail:
                print("-> 详情页失败，跳过")
                continue

            # 真实评论
            comments = fetch_real_comments(sid, city, max_pages=3)
            senti_score, senti_label, senti_details = sentiment_analysis(comments)

            # 跳过完全无数据的景点（无评分且无评论且无简介）
            if detail["rating"] is None and len(comments) == 0 and detail["description"] == "暂无简介":
                print("-> 无有效数据，跳过")
                continue

            # 坐标
            # ⚠️ 诚实说明：列表页/详情页均未提供经纬度，此处按「城市中心 + 随机偏移」
            #    生成【占位坐标】，并非景点真实位置。因此 latitude/longitude 字段
            #    不能用于任何地理分析（详见 README「局限性」）。
            #    如需真实坐标，应接入地理编码服务（如高德/百度 Geocoding API）。
            lat_b, lng_b = CITY_COORDS.get(city, (35, 110))
            lat = round(lat_b + random.uniform(-0.4, 0.4), 4)
            lng = round(lng_b + random.uniform(-0.4, 0.4), 4)

            row = {
                "city": city, "sight_id": sid, "name": detail["name"],
                "rating": detail["rating"], "comment_count": detail["comment_count"],
                "tags": detail["tags"], "price": detail["price"], "level": detail["level"],
                "address": detail["address"],
                # ⚠️ distance 同为随机占位值（2~75km），非真实距离
                "distance": f"{random.randint(2,75)}km",
                "open_time": detail["open_time"], "description": detail["description"],
                "latitude": lat, "longitude": lng,
                "is_real_free": detail["is_real_free"],
                "comment_count_real": len(comments),
                "sentiment_score": senti_score, "sentiment_label": senti_label,
                "all_comments": "|".join([c['content'] for c in comments]),
                "detail_url": detail["detail_url"],
                "data_source": "real"
            }
            city_data.append(row)

            # 评论明细
            for cd in senti_details:
                all_comments.append({
                    "city": city, "sight_id": sid, "name": detail["name"],
                    "rating": detail["rating"], "comment": cd['content'],
                    "comment_score": cd['score'], "sentiment": cd['score'],
                    "sentiment_label": cd['label'], "date": cd['date'],
                    "author": cd['author']
                })

            print(f"-> 评分{detail['rating']} 评论{detail['comment_count']} 真实评论{len(comments)}条 情感{senti_label}({senti_score})")

            # 实时保存
            if (idx + 1) % 5 == 0:
                pd.DataFrame(all_data + city_data).drop_duplicates(subset=["city","name"]).to_excel(output_xlsx, index=False)
                if all_comments:
                    pd.DataFrame(all_comments).to_excel(comments_xlsx, index=False)

            time.sleep(random.uniform(0.3, 0.6))

        all_data = [d for d in all_data if d.get('city') != city] + city_data
        print(f"\n  {city} 完成: {len(city_data)}条")
        # 每城市保存
        pd.DataFrame(all_data).drop_duplicates(subset=["city","name"]).to_excel(output_xlsx, index=False)
        if all_comments:
            pd.DataFrame(all_comments).to_excel(comments_xlsx, index=False)
        time.sleep(random.uniform(2, 4))

    # 最终保存
    df = pd.DataFrame(all_data).drop_duplicates(subset=["city","name"]).reset_index(drop=True)
    df.to_excel(output_xlsx, index=False)
    if all_comments:
        pd.DataFrame(all_comments).to_excel(comments_xlsx, index=False)

    print(f"\n{'='*60}")
    print(f'采集完成！')
    print(f'景点数据: {len(df)}条 -> {output_xlsx}')
    print(f'评论明细: {len(all_comments)}条 -> {comments_xlsx}')
    print(f'城市分布: {df["city"].value_counts().to_dict()}')
    print(f'有评论景点数: {(df["all_comments"].astype(str).str.len()>5).sum()}')
    print("=" * 60)

if __name__ == "__main__":
    main()
