# app.py
import streamlit as st
import openai
import json
import re
from datetime import datetime

# ページ設定
st.set_page_config(page_title="食事処提案AI", layout="wide")

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []

# サイドバーでAPIキーを設定
with st.sidebar:
    st.title("設定")
    api_key = st.text_input("OpenAI API Key", type="password")
    if api_key:
        openai.api_key = api_key
    
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
    
    # ユーザー情報の入力（Level 3用）
    if "Level 3" in level:
        st.subheader("パーソナル情報")
        with st.expander("好みの登録"):
            fav_cuisine = st.multiselect(
                "好きな料理のジャンル",
                ["日本食", "中華", "イタリアン", "フレンチ", "韓国料理", "エスニック", "ファストフード"]
            )
            fav_atmosphere = st.multiselect(
                "好みの雰囲気",
                ["静かな場所", "賑やかな場所", "おしゃれな場所", "カジュアルな場所", "高級店", "個室あり"]
            )
            dietary_restrictions = st.multiselect(
                "食事制限",
                ["ベジタリアン", "ビーガン", "グルテンフリー", "アレルギー配慮"]
            )
            
        with st.expander("過去の訪問履歴"):
            visited_places = st.text_area("過去に訪れて良かったお店（店名を改行区切りで入力）")

# メイン画面
st.title("食事処提案AI")

# 入力パラメータ（Level 2, Level 3用）
with st.expander("条件を指定", expanded=True):
    col1, col2 = st.columns(2)
    
    with col1:
        location = st.text_input("場所（駅名や地域名）", "新宿")
        cuisine_type = st.selectbox(
            "料理のジャンル", 
            ["指定なし", "日本食", "寿司", "焼肉", "ラーメン", "中華", "イタリアン", "フレンチ", "韓国料理", "エスニック", "ファストフード"]
        )
        
    with col2:
        budget = st.select_slider(
            "予算（一人あたり）",
            options=["〜1,000円", "1,000〜3,000円", "3,000〜5,000円", "5,000〜10,000円", "10,000円〜"]
        )
        party_size = st.number_input("人数", min_value=1, max_value=20, value=2)
        
    occasion = st.selectbox(
        "利用シーン",
        ["指定なし", "ランチ", "ディナー", "デート", "家族との食事", "友人との会食", "ビジネス", "特別な記念日"]
    )
    
    additional_requests = st.text_area("その他のリクエスト", placeholder="例：個室希望、禁煙席希望、駅から近いなど")

# Level 3の場合、追加情報を生成
user_context = ""
if "Level 3" in level and (fav_cuisine or fav_atmosphere or dietary_restrictions or visited_places):
    user_context = "【ユーザー情報】\n"
    if fav_cuisine:
        user_context += f"・好きな料理: {', '.join(fav_cuisine)}\n"
    if fav_atmosphere:
        user_context += f"・好みの雰囲気: {', '.join(fav_atmosphere)}\n"
    if dietary_restrictions:
        user_context += f"・食事制限: {', '.join(dietary_restrictions)}\n"
    if visited_places:
        user_context += f"・過去に訪れて良かったお店: {visited_places}\n"

def get_recommendation():
    try:
        if not api_key:
            st.error("OpenAI APIキーを入力してください")
            return
        
        # クライアントの設定
        client = openai.OpenAI(api_key=api_key)
        
        # レベルに応じたシステムメッセージを設定
        level_instructions = {
            "Level 1": "あなたは基本的なレストラン情報を提供します。料理のジャンルとロケーションに基づいた簡単な推薦を行います。",
            "Level 2": "あなたは条件付きレストラン推薦AIです。場所、料理ジャンル、予算、人数、利用シーンなどの条件に基づいた最適なレストランを提案します。",
            "Level 3": "あなたは高度にパーソナライズされたレストラン推薦AIです。ユーザーの過去の好み、訪問履歴、食事制限などの個人データと、現在の条件に基づいて最適なレストランを提案します。提案は単なる一般的な推薦ではなく、このユーザー固有の好みに合わせた内容にしてください。"
        }
        
        current_level = level.split(":")[0].strip()
        system_message = level_instructions[current_level]
        
        # プロンプトの作成
        prompt = f"""
        場所: {location}
        料理のジャンル: {cuisine_type if cuisine_type != '指定なし' else '特に指定なし'}
        予算: {budget}
        人数: {party_size}人
        利用シーン: {occasion if occasion != '指定なし' else '特に指定なし'}
        追加リクエスト: {additional_requests}
        
        {user_context}
        
        以下の形式でJSONとして回答してください:
        ```json
        [
          {{
            "name": "店名",
            "cuisine": "料理ジャンル",
            "budget": "予算の目安",
            "highlights": ["おすすめポイント1", "おすすめポイント2"],
            "atmosphere": "雰囲気の説明",
            "address": "住所",
            "reason": "このお店を推薦する理由"
          }},
          // 2-3件のレストラン情報
        ]
        ```
        
        現実に存在するレストランのみを推薦し、架空のものは含めないでください。
        特に{location}エリアのレストラン情報に詳しくなくても、一般的な知識に基づいて推薦してください。
        """
        
        # APIリクエスト
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # JSONレスポンスの抽出
        response_text = response.choices[0].message.content
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        
        if json_match:
            json_str = json_match.group(1)
        else:
            # JSONブロックが見つからない場合は、テキスト全体をJSONとして解析を試みる
            json_str = response_text
        
        try:
            recommendations = json.loads(json_str)
            st.session_state.recommendations = recommendations
            return recommendations
        except json.JSONDecodeError:
            st.error("レストラン情報の解析に失敗しました。もう一度試してください。")
            st.code(response_text)
            return None
            
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return None
    
# 検索ボタン
if st.button("レストランを探す", type="primary"):
    with st.spinner("最適なレストランを探しています..."):
        recommendations = get_recommendation()
        
        if recommendations:
            st.success(f"{len(recommendations)}件のレストランが見つかりました！")

# 推薦結果の表示
if st.session_state.recommendations:
    st.subheader("おすすめレストラン")
    
    for i, restaurant in enumerate(st.session_state.recommendations):
        with st.container():
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.subheader(restaurant.get("name", "名称不明"))
                st.caption(f"【{restaurant.get('cuisine', '不明')}】")
                st.write(f"💰 {restaurant.get('budget', '予算情報なし')}")
                
                highlight_items = restaurant.get("highlights", [])
                if highlight_items:
                    st.write("✨ **おすすめポイント**")
                    for item in highlight_items:
                        st.write(f"- {item}")
            
            with col2:
                st.write("🏠 **雰囲気**")
                st.write(restaurant.get("atmosphere", "情報なし"))
                
                st.write("📍 **住所**")
                st.write(restaurant.get("address", "住所情報なし"))
                
                st.write("💡 **推薦理由**")
                st.write(restaurant.get("reason", "理由情報なし"))
            
            st.divider()

# チャット機能
st.subheader("レストランについて質問する")
user_question = st.text_input("質問を入力してください（例：子供連れでも大丈夫？ベジタリアンメニューはある？）")

if user_question and user_question not in [m["content"] for m in st.session_state.messages if m["role"] == "user"]:
    st.session_state.messages.append({"role": "user", "content": user_question})
    
    try:
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            
            context = ""
            if st.session_state.recommendations:
                context = "以下のレストラン情報について回答してください:\n"
                for i, rest in enumerate(st.session_state.recommendations):
                    context += f"レストラン{i+1}: {rest['name']} ({rest.get('cuisine', '不明')})\n"
            
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "あなたはレストラン検索AIアシスタントです。ユーザーのレストランに関する質問に丁寧に答えてください。"},
                    {"role": "user", "content": f"{context}\n\nユーザーからの質問: {user_question}"}
                ]
            )
            
            ai_response = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
    except Exception as e:
        st.error(f"質問の処理中にエラーが発生しました: {str(e)}")

# チャット履歴の表示
for message in st.session_state.messages:
    if message["role"] == "user":
        st.write(f"🧑‍💼 **あなた**: {message['content']}")
    else:
        st.write(f"🤖 **AI**: {message['content']}")
        
# フッター
st.divider()
st.caption("食事処提案AI - レストラン推薦サービス")
st.caption(f"現在の日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
