import streamlit as st
import sys
import io
import docx

# 必要なライブラリのインポートを試行
try:
    import google.generativeai as genai
    import docx
except ImportError:
    st.error(
        "必要なライブラリが見つかりません。以下のコマンドでインストールしてください："
    )
    st.code("pip install google-generativeai python-docx")
    st.info(
        "ターミナルでこのコマンドを実行し、アプリを再起動してください。"
    )
    st.stop()

# StreamlitのUI設定
st.title("💬 Chatbotと今日1日を振り返ろう！")
st.write(
    "TXTもしくはDOCX形式の学習日記をアップロードすると、その内容に関する対話ができるチャットボットです！"
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

# === ドキュメントアップローダーの追加 ===
uploaded_file = st.file_uploader(
    "ドキュメントをアップロードしてください",
    type=['txt', 'docx']
)

# === メッセージとドキュメント内容を保存するためのセッション状態変数の作成 ===
if "messages" not in st.session_state:
    st.session_state.messages = []
if "document_content" not in st.session_state:
    st.session_state.document_content = None

# アップロードされたファイルを処理する
if uploaded_file is not None:
    # ファイルを一度だけ読み込む
    if st.session_state.document_content is None:
        try:
            if uploaded_file.type == 'text/plain':
                # .txtファイルの場合、UTF-8でデコード
                document_content = uploaded_file.getvalue().decode('utf-8')
            elif uploaded_file.type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                # .docxファイルの場合、python-docxで読み込み
                document = docx.Document(uploaded_file)
                paragraphs = [p.text for p in document.paragraphs]
                document_content = "\n".join(paragraphs)
            else:
                st.error("サポートされていないファイル形式です。")
                st.stop()
            
            st.session_state.document_content = document_content
            st.success("ドキュメントが正常にアップロードされました。")
            st.session_state.messages = [] # 新しいドキュメントがアップロードされたらチャット履歴をリセット
            st.info("これで、ドキュメントの内容について質問できます。")
            
            # === ここに最初の質問を生成するロジックを追加 ===
            initial_prompt = f"これからあなたの学習をサポートします。今日の学習日記を拝見しました。\n\nドキュメント:\n{document_content}\n\nまずは、この日の学習で一番印象に残っていることについて教えていただけますか？"
            
            with st.spinner("思考中です..."):
                response = model.generate_content(
                    initial_prompt,
                    stream=False # 最初の一回はストリーミングではなくてよい
                )
                
            assistant_message = response.text
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})

            st.rerun() # UIを再描画してチャットを表示

        except Exception as e:
            st.error(f"ファイルの読み込み中にエラーが発生しました: {e}")

# === チャットUIの表示 ===
if st.session_state.document_content is None:
    st.info("チャットを開始するには、まずドキュメントをアップロードしてください。")
else:
    # 既存のチャットメッセージの表示
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力のチャットフィールド
    if prompt := st.chat_input("ドキュメントについて質問してください"):
        
        # 最大ラリー数を超えていないかチェック
        if len(st.session_state.messages) >= 10: # ユーザーとアシスタントのペアで5回なので10
            st.info("今日の振り返りはこれで終わりにしましょう。また明日も頑張ってくださいね！")
            st.stop()
            
        # ユーザーのプロンプトを保存して表示
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            # Gemini APIに渡すためにメッセージ形式を変換
            history = []
            
            # === ここでドキュメントの内容をシステム指示として最初のコンテキストに追加 ===
            # 対話終了と総括・フィードバックの指示を追加
            document_context = f"あなたは優秀なインストラクショナル・デザイナーであり、孤独の中独学をする成人学習者の自己成長を支援するコーチとしての役割を担う親しみやすいチャットボットです。ユーザーの学習日記を読み、共感を示しながら、その日の出来事や感情についてさらに深く掘り下げるような質問をしてください。結論やアドバイスを急ぐのではなく、ユーザー自身が気づきを得られるように対話を導いてください。この対話は最大5回のラリー（ユーザーの質問とあなたの応答のペア）で終えるようにしてください。最後の応答では、必ず対話の終了を告げ、**その日の学習の総括と簡単なフィードバック**を加えてください。\nドキュメント:\n{st.session_state.document_content}"
            history.append({'role': 'user', 'parts': [document_context]})
            
            # === 既存のチャット履歴も追加 ===
            for msg in st.session_state.messages:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    role = "user" if msg["role"] == "user" else "model"
                    history.append({'role': role, 'parts': [msg["content"]]})
            
            # historyが空でないことを確認
            if not history:
                st.warning("チャット履歴が空です。APIリクエストは送信されません。")
                st.stop()
                
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

    # === Wordファイル出力ボタンの追加 ===
    doc = docx.Document()
    doc.add_heading('今日の振り返り', 0)
    for message in st.session_state.messages:
        if message["role"] == "user":
            doc.add_paragraph(f"ユーザー: {message['content']}")
        else:
            doc.add_paragraph(f"チャットボット: {message['content']}")

    # メモリ上でdocxファイルを生成
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)

    st.download_button(
        label="振り返りドキュメントをダウンロード",
        data=doc_io,
        file_name="振り返り.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
