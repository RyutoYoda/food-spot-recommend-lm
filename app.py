import streamlit as st
import openai
from PIL import Image
import base64
import io

# --- サイドバー設定 ---
st.sidebar.title("🔑 APIキー設定")
openai_api_key = st.sidebar.text_input("OpenAI APIキー", type="password")
if not openai_api_key:
    st.warning("OpenAI APIキーをサイドバーから入力してください。")
    st.stop()
openai.api_key = openai_api_key

# --- タイトル ---
st.title("🎬 YouTube動画 × GPT-4V 解説アプリ")

# --- YouTube埋め込み ---
youtube_url = st.text_input("YouTube動画のURLを入力してください:")
if youtube_url:
    st.video(youtube_url)

# --- 画像アップロード ---
st.header("🖼️ 解説したい場面を画像でアップロード")
uploaded_file = st.file_uploader("動画からスクリーンショットをアップロードしてください（PNG or JPG）", type=["png", "jpg", "jpeg"])

# --- GPT-4Vに画像を送って解説 ---
def generate_caption(image: Image.Image, style: str):
    # Base64 encode
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    # GPT-4Vへリクエスト
    messages = [
        {"role": "system", "content": f"あなたは映像分析のプロです。ユーザーがアップロードした動画のワンシーンを、{style}でわかりやすく解説してください。"},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_str}"
                    }
                }
            ],
        },
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=500,
    )
    return response.choices[0].message.content

# --- 解説スタイル選択 ---
style = st.selectbox(
    "解説スタイルを選んでください",
    ["ニュース風の説明", "野球新聞の見出し", "小学生にもわかるように", "冗談交じりの解説"]
)

# --- 画像がアップされたらGPTで解説 ---
if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="アップロードされたシーン", use_column_width=True)

    with st.spinner("GPTが解説中..."):
        result = generate_caption(image, style)

    st.subheader("🧠 GPTによる解説")
    st.write(result)
