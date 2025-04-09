import streamlit as st
import openai
from youtube_transcript_api import YouTubeTranscriptApi
import re
from PIL import Image
import io

# --- サイドバー ---
st.sidebar.title("🔧 設定")
openai_api_key = st.sidebar.text_input("OpenAI APIキー", type="password")

if not openai_api_key:
    st.warning("まずサイドバーから OpenAI APIキーを入力してください。")
    st.stop()
else:
    openai.api_key = openai_api_key

# --- タイトル ---
st.title("🎥 YouTube 解説 + GPT-4V ビジュアルアシスト")

# --- URL入力 ---
url = st.text_input("YouTube動画のURLを入力してください")

# --- YouTube Video ID 抽出関数 ---
def get_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

# --- 字幕取得 ---
def fetch_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ja', 'en'])
        return transcript
    except:
        return None

# --- GPT解説 ---
def generate_explanation(text):
    messages = [
        {"role": "system", "content": "あなたは教育系YouTuberです。視聴者に分かりやすく丁寧に解説してください。"},
        {"role": "user", "content": f"次の字幕を元に、内容をわかりやすく解説してください:\n\n{text[:3000]}"}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    return response.choices[0].message.content

# --- GPT-4V 画像説明 ---
def generate_image_description(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    buffered.seek(0)

    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[
            {"role": "system", "content": "あなたは画像から内容を読み取り、動画の補足説明を行うアシスタントです。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "この画像の内容を解説してください"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + buffered.getvalue().hex()}}
                ]
            }
        ],
        max_tokens=500
    )
    return response.choices[0].message.content

# --- メイン処理 ---
if url:
    video_id = get_video_id(url)
    st.video(url)

    st.subheader("📄 字幕の解説")
    transcript_data = fetch_transcript(video_id)

    if transcript_data:
        # 字幕を時間帯でチャンク化（例：30秒単位）
        chunk_size = 30
        chunks = []
        current_chunk = ""
        current_time = 0

        for entry in transcript_data:
            if entry['start'] < current_time + chunk_size:
                current_chunk += entry['text'] + " "
            else:
                chunks.append((current_time, current_chunk.strip()))
                current_time += chunk_size
                current_chunk = entry['text'] + " "

        # 最後のチャンク追加
        if current_chunk:
            chunks.append((current_time, current_chunk.strip()))

        # ユーザーに時間帯選択させる
        times = [f"{int(t//60)}:{int(t%60):02d}" for t, _ in chunks]
        selected = st.selectbox("🕐 解説を表示する時間帯を選んでください", times)
        index = times.index(selected)
        st.markdown(f"**字幕内容：** {chunks[index][1]}")
        
        with st.spinner("GPTが解説中..."):
            explanation = generate_explanation(chunks[index][1])
        st.markdown("**🧠 解説：**")
        st.write(explanation)
    else:
        st.error("字幕が取得できませんでした。動画に字幕がない可能性があります。")

    # --- 画像アップロード ---
    st.subheader("🖼️ 画像スクリーンショットで補足解説（GPT-4V）")
    uploaded_file = st.file_uploader("画像ファイルをアップロードしてください", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="アップロードされた画像", use_column_width=True)
        with st.spinner("画像から解説を生成中..."):
            description = generate_image_description(image)
        st.markdown("**📷 GPT-4Vによる画像解説：**")
        st.write(description)
