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
st.title("🎥 GPTによるYouTube動画要約・シーン解説")

# サイドバー設定
with st.sidebar:
    st.header("設定")
    openai_api_key = st.text_input("🔑 OpenAI API Key", type="password")
    
    # 詳細設定の折りたたみ
    with st.expander("詳細設定"):
        scene_interval = st.slider("シーン抽出間隔（秒）", min_value=5, max_value=60, value=15, step=5)
        max_scenes = st.slider("最大シーン数", min_value=5, max_value=50, value=20)
        include_summary = st.checkbox("動画全体の要約を生成", value=True)
        show_timestamps = st.checkbox("タイムスタンプを表示", value=True)

if not openai_api_key:
    st.warning("OpenAI APIキーを入力してください")
    st.stop()

openai.api_key = openai_api_key

# Input YouTube URL
youtube_url = st.text_input("🎬 YouTubeのURLを貼ってください")

if youtube_url:
    with st.spinner("動画情報を取得中..."):
        # まず情報だけ取得
        info_opts = {
            'skip_download': True,
            'quiet': True,
        }
        try:
            with YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                video_title = info.get('title', 'YouTube Video')
                video_duration = info.get('duration', 0)  # 秒単位
                
                # 動画時間が長すぎる場合は警告
                if video_duration > 1800:  # 30分以上
                    st.warning(f"⚠️ 動画が長いため（{video_duration//60}分）、処理に時間がかかる場合があります")

            st.subheader(f"📺 {video_title}")
            
            # シーン数を計算して表示
            estimated_scenes = min(video_duration // scene_interval, max_scenes)
            st.info(f"予想されるシーン数: 約{estimated_scenes}枚")
            
        except Exception as e:
            st.error(f"動画情報の取得に失敗しました: {e}")
            st.stop()
    
    # ダウンロードボタン
    if st.button("動画をダウンロードして解析"):
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
        
        # 動画プレビュー（小さめに表示）
        col1, col2 = st.columns([1, 2])
        with col1:
            st.video(video_path)
        
        # 全体の要約を先に生成
        if include_summary:
            with col2:
                with st.spinner("🧠 動画全体の要約を生成中..."):
                    try:
                        # 最初、中間、終わりのフレームを抽出して全体像を把握
                        summary_frames = []
                        output_dir = tempfile.mkdtemp()
                        
                        # 動画の開始、25%、50%、75%、終了付近のフレームを抽出
                        positions = [0.1, 0.25, 0.5, 0.75, 0.9]
                        for i, pos in enumerate(positions):
                            time_pos = video_duration * pos
                            output_file = os.path.join(output_dir, f"summary_{i}.jpg")
                            subprocess.run([
                                "ffmpeg", "-ss", str(time_pos), "-i", video_path,
                                "-vframes", "1", "-q:v", "2", output_file
                            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            
                            if os.path.exists(output_file):
                                with open(output_file, "rb") as img_file:
                                    summary_frames.append(base64.b64encode(img_file.read()).decode())
                        
                        # 代表フレームを使って要約を生成
                        image_contents = []
                        for i, b64_img in enumerate(summary_frames):
                            image_contents.append({
                                "type": "image_url", 
                                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                            })
                        
                        response = openai.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": f"これらは「{video_title}」というYouTube動画の異なるタイミングから抽出された画像です。これらの画像をもとに、この動画が全体的に何についての内容か、300-400字程度で要約してください。この動画から視聴者が得られる主な情報や学びはなんですか？"},
                                        *image_contents
                                    ]
                                }
                            ],
                            max_tokens=800
                        )
                        
                        summary = response.choices[0].message.content
                        st.markdown("### 📝 動画全体の要約")
                        st.markdown(summary)
                        
                        # トピックやキーポイントを抽出
                        key_points_response = openai.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": f"これらは「{video_title}」というYouTube動画の異なるタイミングから抽出された画像です。この動画で扱われている主要な5つのトピックやキーポイントを箇条書きで簡潔に教えてください。"},
                                        *image_contents
                                    ]
                                }
                            ],
                            max_tokens=500
                        )
                        
                        key_points = key_points_response.choices[0].message.content
                        st.markdown("### 🔑 主要ポイント")
                        st.markdown(key_points)
                    
                    except Exception as e:
                        st.error(f"要約生成エラー: {e}")
        
        # シーン解析処理
        st.markdown("---")
        st.markdown("## 📊 シーン別解説")
        st.info(f"画像を抽出しています... {scene_interval}秒ごとに最大{max_scenes}シーンを分析します")
        
        # シーン画像を抽出
        output_dir = tempfile.mkdtemp()
        output_pattern = os.path.join(output_dir, "scene_%03d.jpg")
        
        # シーン抽出間隔とシーン数に基づいて抽出
        command = [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{scene_interval}",
            "-vframes", str(max_scenes),
            "-q:v", "2",  # 画質設定（2は良好な画質）
            output_pattern
        ]
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        scene_files = sorted([f for f in os.listdir(output_dir) if f.endswith(".jpg")])
        st.success(f"{len(scene_files)} 枚のシーン画像を抽出しました。GPTによる解説を生成中...")
        
        # 進捗バー
        progress_bar = st.progress(0)
        
        # シーン解説の結果を格納
        all_scene_explanations = []
        
        # シーン解析結果を表示するための列を作成
        for i, scene_file in enumerate(scene_files):
            # 進捗を更新
            progress_bar.progress((i + 1) / len(scene_files))
            
            # シーンのタイムスタンプを計算
            scene_time = i * scene_interval
            minutes = scene_time // 60
            seconds = scene_time % 60
            timestamp = f"{minutes:02d}:{seconds:02d}"
            
            # 画像を読み込み
            with open(os.path.join(output_dir, scene_file), "rb") as img_file:
                img_bytes = img_file.read()
                b64_img = base64.b64encode(img_bytes).decode()
            
            # 2列レイアウトでシーンと解説を表示
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(img_bytes, caption=f"シーン {i+1} {timestamp if show_timestamps else ''}", width=320)
            
            with col2:
                with st.spinner(f"シーン {i+1} の解説を生成中..."):
                    try:
                        response = openai.chat.completions.create(
                            model="gpt-4-vision-preview",
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "この画像は動画の一場面です。何が映っていて、どのような内容が説明されている可能性が高いか、100-150字程度で簡潔に解説してください。"},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                    ]
                                }
                            ],
                            max_tokens=300
                        )
                        
                        explanation = response.choices[0].message.content
                        st.markdown(f"**🧠 GPTの解説：**\n{explanation}")
                        
                        # 結果を保存
                        all_scene_explanations.append({
                            "timestamp": timestamp,
                            "explanation": explanation
                        })
                    
                    except Exception as e:
                        st.error(f"エラー: {e}")
            
            # 区切り線を追加
            st.markdown("---")
        
        # 進捗バーを完了状態に
        progress_bar.progress(1.0)
        
        # 全ての解説が完了したらダウンロード可能なテキスト要約を提供
        if all_scene_explanations:
            summary_text = f"# {video_title} - 動画要約\n\n"
            
            if include_summary:
                summary_text += "## 全体要約\n"
                summary_text += summary + "\n\n"
                summary_text += "## 主要ポイント\n"
                summary_text += key_points + "\n\n"
            
            summary_text += "## シーン別解説\n\n"
            
            for scene in all_scene_explanations:
                summary_text += f"### {scene['timestamp']}\n"
                summary_text += f"{scene['explanation']}\n\n"
            
            # テキストファイルとしてダウンロード可能に
            st.download_button(
                label="📥 要約をテキストファイルとしてダウンロード",
                data=summary_text,
                file_name=f"{video_title}_summary.txt",
                mime="text/plain",
            )
        
        st.success("✅ すべてのシーンの解説が完了しました！")
