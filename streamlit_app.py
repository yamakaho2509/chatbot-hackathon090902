import streamlit as st
import sys

# google-generativeaiモジュールのインポートを試行
try:
    import google.generativeai as genai
except ImportError:
    st.error(
        "必要なライブラリが見つかりません。以下のコマンドでインストールしてください："
    )
    st.code("pip install google-generativeai")
    st.info(
        "ターミナルでこのコマンドを実行し、アプリを再起動してください。"
    )
    st.stop()

# StreamlitのUI設定
st.title("💬 Chatbot with Gemini Flash 2.5")
st.write(
    "このシンプルなチャットボットは、GoogleのGemini Flash 2.5モデルを使用して応答を生成します。 "
    "APIキーはStreamlitのsecrets.tomlファイルから読み込まれます。"
)

# secretsからAPIキーを読み込む
try:
    gemini_api_key = st.secrets["google_api_key"]
    if not gemini_api_key:
        raise KeyError
except KeyError:
    st.error("APIキーがStreamlitのsecretsに設定されていません。")
    st.info(
        "プロジェクトのルートディレクトリに`.streamlit/secrets.toml`ファイルを作成し、"
        "以下の形式でAPIキーを追加してください。\n\n"
        "```toml\n"
        "google_api_key = \"YOUR_API_KEY_HERE\"\n"
        "```"
        "\n`YOUR_API_KEY_HERE`を実際のAPIキーに置き換えてください。"
    )
    st.stop()

# Gemini APIクライアントの初期化
genai.configure(api_key=gemini_api_key)
model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')

# メッセージを保存するためのセッション状態変数の作成
if "messages" not in st.session_state:
    st.session_state.messages = []

# 既存のチャットメッセージの表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザー入力のチャットフィールド
if prompt := st.chat_input("何ができますか？"):

    # ユーザーのプロンプトを保存して表示
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    try:
        # Gemini APIに渡すためにメッセージ形式を変換
        history = []
        for msg in st.session_state.messages:
            role = "user" if msg["role"] == "user" else "model"
            history.append({'role': role, 'parts': [msg["content"]]})

        # Gemini APIを使用して応答を生成（ストリーミング）
        response_stream = model.generate_content(
            history,
            stream=True
        )

        # 応答をチャットにストリーミング表示し、セッション状態に保存
        full_response = ""
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            for chunk in response_stream:
                if chunk.parts:
                    text_part = chunk.parts[0].text
                    full_response += text_part
                    message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

    except Exception as e:
        st.error("エラーが発生しました。詳細はコンソールを確認してください。")
        print(f"エラーの詳細: {e}", file=sys.stderr)
        st.session_state.messages.append({"role": "assistant", "content": "申し訳ありません、応答の生成中にエラーが発生しました。"})
