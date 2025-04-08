import streamlit as st
import openai
import cv2
import numpy as np
from PIL import Image
import io
import re
import time

# --- サイドバーでOpenAI APIキーを入力 ---
st.sidebar.title("🔧 設定")
openai_api_key = st.sidebar.text_input("OpenAI APIキー", type="password")

if not openai_api_key:
    st.warning("まずサイドバーから OpenAI APIキーを入力してください。")
    st.stop()
else:
    openai.api_key = openai_api_key

# --- タイトル ---
st.title("🎥 YouTube 動画解説")

# --- YouTube動画のURLを入力 ---
url = st.text_input("YouTube動画のURLを入力してください")

# --- YouTube Video IDを抽出する関数 ---
def get_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

# --- GPT-4Vによる動画フレーム解説 ---
def generate_video_frame_description(frame):
    buffered = io.BytesIO()
    pil_img = Image.fromarray(frame)
    pil_img.save(buffered, format="PNG")
    buffered.seek(0)

    # GPT-4Vにフレームを送信して解説を生成
    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[
            {"role": "system", "content": "動画をリアルタイムで見て解説を生成してください"},
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + buffered.getvalue().hex()}}]}
        ],
    )
    return response.choices[0].message.content

# --- 動画フレームの処理 ---
def process_video(url):
    video_id = get_video_id(url)
    cap = cv2.VideoCapture(url)
    
    # 動画のFPS（1秒ごとにフレームをキャプチャ）
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = 0

    # 動画が開けたらフレームを逐次取得
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        # 1秒ごとにフレームをキャプチャして解説
        if frame_count % int(fps) == 0:
            st.image(frame, caption=f"フレーム {frame_count}")
            with st.spinner("GPTがフレームを解説中..."):
                explanation = generate_video_frame_description(frame)
            st.write(f"**解説**: {explanation}")
        
        frame_count += 1
        time.sleep(1)  # 1秒ごとにフレームをキャプチャ

    cap.release()

# --- メイン処理 ---
if url:
    process_video(url)
