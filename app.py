# app.py
import streamlit as st
import openai
import json
import re
import requests
from datetime import datetime

# --- APIキーの読み込み（環境変数から） ---
openai.api_key = st.secrets["OPENAI_API_KEY"]
hotpepper_api_key = st.secrets["HOTPEPPER_API_KEY"]

# --- ページ設定 ---
st.set_page_config(page_title="AI", layout="wide")

# --- セッション状態の初期化 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []

# --- サイドバー ---
with st.sidebar:
    st.title("設定")
    st.subheader("推薦レベル")
    level = st.radio(
        "どのレベルの推薦を希望しますか？",
        ["Level 1: 基本推薦", "Level 2: 条件付き推薦", "Level 3: パーソナライズ推薦"],
        index=1
    )
    with st.expander("レベルの説明"):
        st.markdown("""
        **Level 1**: 基本的な飲食店情報の提供（〇〇料理ならこのお店があります）

        **Level 2**: 予算、人数など基本条件に合わせた推薦

        **Level 3**: 個人の好み、過去の訪問履歴などを考慮した高度なパーソナライズ推薦
        """)
    if "Level 3" in level:
        st.subheader("パーソナル情報")
        with st.expander("好みの登録"):
            fav_cuisine = st.multiselect("好きな料理のジャンル", ["日本食", "中華", "イタリアン", "フレンチ", "韓国料理", "エスニック", "ファストフード"])
            fav_atmosphere = st.multiselect("好みの雰囲気", ["静かな場所", "賑やかな場所", "おしゃれな場所", "カジュアルな場所", "高級店", "個室あり"])
            dietary_restrictions = st.multiselect("食事制限", ["ビーガン", "グルテンフリー", "アレルギー配慮"])
        with st.expander("過去の訪問履歴"):
            visited_places = st.text_area("過去に訪れて良かったお店（店名を改行区切りで入力）")

# --- メイン画面 ---
st.title("Pekorin AI")

with st.expander("条件を指定", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        location = st.text_input("場所（駅名や地域名）", "新宿")
        cuisine_type = st.selectbox("料理のジャンル", ["指定なし", "日本食", "寿司", "焼肉", "ラーメン", "中華", "イタリアン", "フレンチ", "韓国料理", "エスニック", "ファストフード"])

    with col2:
        budget = st.select_slider("予算（一人あたり）", options=["〜1,000円", "1,000〜3,000円", "3,000〜5,000円", "5,000〜10,000円", "10,000円〜"])
        party_size = st.number_input("人数", min_value=1, max_value=20, value=2)

    occasion = st.selectbox("利用シーン", ["指定なし", "ランチ", "ディナー", "デート", "家族との食事", "友人との会食", "恩師との食事" ,"ビジネス", "特別な記念日"])
    additional_requests = st.text_area("その他のリクエスト", placeholder="例：個室希望、禁煙席希望、駅から近いなど")

user_context = ""
if "Level 3" in level and ('fav_cuisine' in locals() or 'fav_atmosphere' in locals() or 'dietary_restrictions' in locals() or 'visited_places' in locals()):
    user_context = "【ユーザー情報】\n"
    if fav_cuisine:
        user_context += f"・好きな料理: {', '.join(fav_cuisine)}\n"
    if fav_atmosphere:
        user_context += f"・好みの雰囲気: {', '.join(fav_atmosphere)}\n"
    if dietary_restrictions:
        user_context += f"・食事制限: {', '.join(dietary_restrictions)}\n"
    if visited_places:
        user_context += f"・過去に訪れて良かったお店: {visited_places}\n"

def get_hotpepper_restaurants(api_key, location, cuisine_type, budget):
    """ホットペッパーAPIから店舗情報を取得（URL必須）"""
    genre_map = {"日本食": "G004", "寿司": "G001", "焼肉": "G008", "ラーメン": "G013", "中華": "G007", "イタリアン": "G005", "フレンチ": "G006", "韓国料理": "G017", "エスニック": "G009,G010", "ファストフード": "G014"}
    budget_map = {"〜1,000円": "B009", "1,000〜3,000円": "B010", "3,000〜5,000円": "B011", "5,000〜10,000円": "B008", "10,000円〜": "B012"}
    params = {'key': api_key, 'keyword': location, 'format': 'json', 'count': 20}  # countを増やして選択肢を増やす
    if cuisine_type != "指定なし" and cuisine_type in genre_map:
        params['genre'] = genre_map[cuisine_type]
    if budget in budget_map:
        params['budget'] = budget_map[budget]
    try:
        response = requests.get('http://webservice.recruit.co.jp/hotpepper/gourmet/v1/', params=params)
        data = response.json()
        shops = data.get('results', {}).get('shop', [])
        
        # URLが存在する店舗のみをフィルタリング
        valid_shops = []
        for shop in shops:
            if 'urls' in shop and 'pc' in shop['urls'] and shop['urls']['pc']:
                valid_shops.append(shop)
        
        return valid_shops
    except Exception as e:
        st.error(f"ホットペッパーAPIエラー: {str(e)}")
        return []

def format_shop_for_gpt(shop):
    """店舗情報をGPT用にフォーマット"""
    return {
        'id': shop.get('id', ''),
        'name': shop.get('name', '不明'),
        'genre': shop.get('genre', {}).get('name', '不明'),
        'budget': shop.get('budget', {}).get('name', '不明'),
        'access': shop.get('access', '不明'),
        'address': shop.get('address', '不明'),
        'catch': shop.get('catch', '情報なし'),
        'open': shop.get('open', '不明'),
        'url': shop.get('urls', {}).get('pc', ''),
        'photo': shop.get('photo', {}).get('pc', {}).get('m', '')
    }

def get_recommendation():
    try:
        client = openai.OpenAI(api_key=openai.api_key)
        
        # ホットペッパーから実在する店舗のみを取得
        hotpepper_restaurants = get_hotpepper_restaurants(hotpepper_api_key, location, cuisine_type, budget)
        
        # 店舗が取得できない場合は推薦を行わない
        if not hotpepper_restaurants:
            st.error("条件に合う店舗が見つかりませんでした。条件を変更して再度お試しください。")
            return None
        
        # GPT用の店舗リストを作成
        shop_list = []
        for i, shop in enumerate(hotpepper_restaurants):
            formatted_shop = format_shop_for_gpt(shop)
            shop_list.append(f"""
店舗ID: {i+1}
店名: {formatted_shop['name']}
ジャンル: {formatted_shop['genre']}
予算: {formatted_shop['budget']}
アクセス: {formatted_shop['access']}
住所: {formatted_shop['address']}
キャッチ: {formatted_shop['catch']}
営業時間: {formatted_shop['open']}
""")

        system_message = {
            "Level 1": "あなたは基本的なレストラン情報を提供するAIです。",
            "Level 2": "あなたは条件付きレストラン推薦AIです。ユーザーの条件に最も適した店舗を選択してください。",
            "Level 3": "あなたは高度にパーソナライズされたレストラン推薦AIです。ユーザーの個人情報と条件を総合的に考慮して最適な店舗を選択してください。"
        }[level.split(":")[0].strip()]

        prompt = f"""
【重要】以下のリストにある実在する店舗の中からのみ推薦してください。リストにない店舗は絶対に推薦しないでください。

【検索条件】
場所: {location}
料理ジャンル: {cuisine_type if cuisine_type != '指定なし' else '指定なし'}
予算: {budget}
人数: {party_size}人
利用シーン: {occasion}
追加リクエスト: {additional_requests}

{user_context}

【利用可能な実在店舗リスト】
{''.join(shop_list)}

上記の店舗リストの中から、条件に最も適した3〜5店舗を選択し、以下の形式でJSONで出力してください:

```json
[
  {{
    "shop_id": "店舗ID番号（上記リストの番号）",
    "name": "店名（リストと完全に同じ名前）",
    "cuisine": "料理ジャンル（リストと同じ）",
    "budget": "予算の目安（リストと同じ）",
    "highlights": ["おすすめポイント1", "おすすめポイント2"],
    "atmosphere": "雰囲気の説明",
    "address": "住所（リストと同じ）",
    "reason": "このお店を推薦する理由"
  }}
]
```
"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        response_text = response.choices[0].message.content
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        json_str = json_match.group(1) if json_match else response_text
        
        try:
            gpt_recommendations = json.loads(json_str)
        except json.JSONDecodeError:
            st.error("AIからの応答を解析できませんでした。再度お試しください。")
            return None
        
        # GPTの推薦結果を実際の店舗データとマッチング
        final_recommendations = []
        for rec in gpt_recommendations:
            try:
                shop_id = int(rec.get('shop_id', 0)) - 1  # リストのインデックスに変換
                if 0 <= shop_id < len(hotpepper_restaurants):
                    actual_shop = hotpepper_restaurants[shop_id]
                    formatted_shop = format_shop_for_gpt(actual_shop)
                    
                    # 実際の店舗情報で推薦情報を補完
                    final_rec = {
                        "name": formatted_shop['name'],
                        "cuisine": formatted_shop['genre'],
                        "budget": formatted_shop['budget'],
                        "highlights": rec.get('highlights', ['美味しい料理', '良いサービス']),
                        "atmosphere": rec.get('atmosphere', '素敵な雰囲気'),
                        "address": formatted_shop['address'],
                        "access": formatted_shop['access'],
                        "open": formatted_shop['open'],
                        "catch": formatted_shop['catch'],
                        "reason": rec.get('reason', 'おすすめの店舗です'),
                        "url": formatted_shop['url'],  # 必ずURLが存在する
                        "photo": formatted_shop['photo']
                    }
                    final_recommendations.append(final_rec)
            except (ValueError, KeyError, IndexError):
                continue  # 不正な推薦は無視
        
        if not final_recommendations:
            st.error("推薦結果を生成できませんでした。条件を変更して再度お試しください。")
            return None
            
        st.session_state.recommendations = final_recommendations
        return final_recommendations
        
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return None

if st.button("レストランを探す", type="primary"):
    with st.spinner("最適なレストランを探しています..."):
        get_recommendation()

if st.session_state.recommendations:
    st.subheader("おすすめレストラン")
    st.info(f"見つかった店舗: {len(st.session_state.recommendations)}件（すべて実在する店舗です）")
    
    for rest in st.session_state.recommendations:
        with st.container():
            col1, col2 = st.columns([1, 2])
            with col1:
                st.subheader(rest.get("name", "名称不明"))
                st.caption(f"【{rest.get('cuisine', '不明')}】")
                st.write(f"💰 {rest.get('budget', '予算情報なし')}")
                if rest.get("highlights"):
                    st.write("✨ **おすすめポイント**")
                    for h in rest["highlights"]:
                        st.write(f"- {h}")
                
                # 写真があれば表示
                if rest.get("photo"):
                    st.image(rest["photo"], width=200)
                    
            with col2:
                st.write("🏠 **雰囲気**")
                st.write(rest.get("atmosphere", "情報なし"))
                
                st.write("📍 **住所・アクセス**")
                st.write(rest.get("address", "住所情報なし"))
                if rest.get("access"):
                    st.write(f"🚃 {rest['access']}")
                
                st.write("⏰ **営業時間**")
                st.write(rest.get("open", "営業時間情報なし"))
                
                if rest.get("catch"):
                    st.write("📝 **お店からのメッセージ**")
                    st.write(rest["catch"])
                
                st.write("💡 **推薦理由**")
                st.write(rest.get("reason", "理由情報なし"))
                
                # 必ずURLが存在することが保証されている
                if rest.get("url"):
                    st.write("🔗 **詳細情報**")
                    st.markdown(f"[ホットペッパーで詳細を見る]({rest['url']})")
            st.divider()
else:
    st.info("「レストランを探す」ボタンを押して、おすすめの店舗を見つけましょう！")

st.caption("Pekorin AI - 飲食店推薦サービス powered by r.yoda")
st.caption("※ すべての店舗情報はホットペッパーグルメAPIから取得した実在する店舗です")
