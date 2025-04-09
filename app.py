# streamlit_app.py
import streamlit as st
import openai
import base64
import os
import tempfile
import subprocess
from PIL import Image
from io import BytesIO
from yt_dlp import YoutubeDL

st.set_page_config(page_title="YouTube Scene Summarizer", layout="wide")
st.title("🎥 GPTによるYouTube動画シーン解説")

# Sidebar for API keys
openai_api_key = st.sidebar.text_input("🔑 OpenAI API Key", type="password")

if not openai_api_key:
    st.warning("OpenAI APIキーを入力してください")
    st.stop()

openai.api_key = openai_api_key

# Input YouTube URL
youtube_url = st.text_input("🎬 YouTubeのURLを貼ってください")

if youtube_url:
    with st.spinner("動画をダウンロード中..."):
        ydl_opts = {
            'format': 'mp4',
            'outtmpl': os.path.join(tempfile.gettempdir(), 'downloaded_video.%(ext)s'),
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                video_path = ydl.prepare_filename(info)
        except Exception as e:
            st.error(f"動画のダウンロードに失敗しました: {e}")
            st.stop()

    st.video(video_path)

    if st.button("シーン解析を開始"):
        st.info("画像を抽出しています... 🎞️")

        # Extract 1 image every 10 seconds
        output_dir = tempfile.mkdtemp()
        output_pattern = os.path.join(output_dir, "scene_%03d.jpg")

        command = [
            "ffmpeg", "-i", video_path,
            "-vf", "fps=1/10",
            output_pattern
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        scene_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".jpg")])

        st.success(f"{len(scene_files)} 枚の画像を抽出しました。GPTによる解説を生成中... 🧠")

        for i, scene_file in enumerate(scene_files):
            with open(os.path.join(output_dir, scene_file), "rb") as img_file:
                img_bytes = img_file.read()
                b64_img = base64.b64encode(img_bytes).decode()

            # GPT-4V解説
            st.image(img_bytes, caption=f"シーン {i+1}", width=480)
            with st.spinner("GPTが解説中..."):
                try:
                    response = openai.chat.completions.create(
                        model="gpt-4-vision-preview",
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "この画像には何が映っていて、何が起きているか日本語で簡単に説明してください。"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                ]
                            }
                        ],
                        max_tokens=300
                    )
                    explanation = response.choices[0].message.content
                    st.markdown(f"**🧠 GPTの解説：** {explanation}")
                except Exception as e:
                    st.error(f"エラー: {e}")

        st.success("✅ すべてのシーンの解説が完了しました！")
