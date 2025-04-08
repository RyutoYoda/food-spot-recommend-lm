import streamlit as st
import tempfile
import cv2
import os
import openai
from PIL import Image
from datetime import timedelta

# --- Sidebar: API Key 入力 ---
st.sidebar.title("🔑 API Key")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

# --- アプリのヘッダー ---
st.set_page_config(page_title="動画要約 with GPT-4V", layout="wide")
st.title("🎥 GPT-4Vで自動動画要約")
st.caption("動画内の動きが大きいシーンを検出し、画像で要約するアプリ")

# --- ファイルアップロード ---
uploaded_file = st.file_uploader("動画ファイルをアップロードしてください (mp4, mov)", type=["mp4", "mov"])

if uploaded_file and openai_api_key:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(uploaded_file.read())
        video_path = tmp.name

    st.video(uploaded_file)
    st.info("🔍 動きが大きいシーンを解析中...（少々お待ちください）")

    # --- OpenCVで動画処理 ---
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    interval = int(fps * 2)  # 2秒おきにフレーム比較
    prev_frame = None
    frame_diffs = []
    selected_frames = []

    frame_idx = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_frame is not None:
                diff = cv2.absdiff(prev_frame, gray)
                score = diff.sum()
                frame_diffs.append((frame_idx, score, frame))
            prev_frame = gray
        frame_idx += 1
    cap.release()

    # --- 動きが大きい上位5シーン抽出 ---
    top_diffs = sorted(frame_diffs, key=lambda x: x[1], reverse=True)[:5]
    st.success(f"✅ 動きが大きいシーンを {len(top_diffs)} 個検出しました")

    # --- GPT-4V で画像ごとに要約 ---
    openai.api_key = openai_api_key

    cols = st.columns(1)
    for idx, (f_idx, score, frame) in enumerate(top_diffs):
        timestamp = str(timedelta(seconds=int(f_idx / fps)))
        image_path = f"frame_{idx}.jpg"
        cv2.imwrite(image_path, frame)
        image = Image.open(image_path)

        with st.container():
            st.subheader(f"🕒 シーン {idx + 1}（{timestamp}）")
            st.image(image, caption=f"フレームタイム: {timestamp}", use_column_width=True)

            # --- GPT-4Vによる画像要約 ---
            with open(image_path, "rb") as img_file:
                response = openai.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes visual scenes."},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "このシーンでは何が起きていますか？日本語で簡単に説明してください。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_file.read().encode('base64').decode()}"}}
                            ]
                        }
                    ],
                    max_tokens=100
                )
                caption = response.choices[0].message.content
                st.info(f"🧠 GPTの解説: {caption}")

        os.remove(image_path)
else:
    st.warning("🔼 動画ファイルと OpenAI API Key を入力してください")
