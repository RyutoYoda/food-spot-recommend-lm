import streamlit as st
import openai
import ffmpeg
import pytube
import whisper
import os
import tempfile
import re
from moviepy.editor import VideoFileClip
from pydub import AudioSegment

# --- サイドバー ---
st.sidebar.title("🔧 設定")
openai_api_key = st.sidebar.text_input("OpenAI APIキー", type="password")

if not openai_api_key:
    st.warning("まずサイドバーから OpenAI APIキーを入力してください。")
    st.stop()
else:
    openai.api_key = openai_api_key

# --- タイトル ---
st.title("🎥 YouTube動画実況 + GPT-4 解説")

# --- URL入力 ---
url = st.text_input("YouTube動画のURLを入力してください")

# --- YouTube Video ID 抽出関数 ---
def get_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url)
    return match.group(1) if match else None

# --- Whisperで文字起こし ---
def transcribe_audio(audio_path):
    model = whisper.load_model("base")  # "base"モデルでOK（必要に応じて変更）
    result = model.transcribe(audio_path)
    return result["text"]

# --- 音声抽出と文字起こし ---
def process_video(url):
    # YouTube動画のダウンロード
    yt = pytube.YouTube(url)
    stream = yt.streams.filter(file_extension="mp4").first()
    video_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    stream.download(output_path=video_file.name)

    # 動画を音声に変換
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    audio_file_path = audio_file.name
    video_clip = VideoFileClip(video_file.name)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(audio_file_path)

    # Whisperで音声から文字起こし
    transcription = transcribe_audio(audio_file_path)
    
    return transcription

# --- GPTで解説生成 ---
def generate_explanation(text):
    messages = [
        {"role": "system", "content": "あなたはスポーツ実況やニュース解説を行うプロのアシスタントです。"},
        {"role": "user", "content": f"次の文字起こしを基に、リアルタイムで解説を生成してください:\n\n{text}"}
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )
    return response.choices[0].message.content

# --- メイン処理 ---
if url:
    video_id = get_video_id(url)
    if video_id:
        st.video(url)  # 動画再生

        st.subheader("📄 字幕の解説")
        
        with st.spinner("音声を文字起こし中..."):
            transcription = process_video(url)
        
        st.write("**文字起こし結果：**")
        st.write(transcription[:1500])  # 最初の1500文字だけ表示

        with st.spinner("GPTが解説中..."):
            explanation = generate_explanation(transcription)
        
        st.subheader("🎤 解説")
        st.write(explanation)  # GPTによる解説
    else:
        st.error("無効なYouTube URLです。正しいURLを入力してください。")
