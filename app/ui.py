import argparse
import gradio as gr
import dotenv
from app.retrieval import get_answer

dotenv.load_dotenv()

def chat_interface(message, history):
    if not message:
        return ""

    # RAG sistemi 3 parametre dönüyor (Cevap, İlaç ID, Kullanılan Chunklar).
    answer, drug_id, chunks_str = get_answer(message, history)

    final_response = f"{answer}\n\n**[Tespit Edilen İlaç: {drug_id}]**"

    # Text chunklarını Colab hücresinin çıktısına (console) yazdırıyoruz
    """if chunks_str:
        print("\n" + "="*60)
        print(f"🧐 KULLANICI SORUSU: {message}")
        print("-" * 60)
        print(f"📄 MODELE GÖNDERİLEN KAYNAK METİNLER (CHUNKLAR):\n\n{chunks_str}")
        print("="*60 + "\n")  """

    return final_response

def main(host, port, share=False):
    with gr.Blocks(title="İlaç KT Chatbot") as demo:
        gr.Markdown("## İlaç Sohbet Botu RAG Q&A")

        gr.Markdown("""
        ⚠️ **ÖNEMLİ UYARI:**
        Bu asistan geçmiş sohbetleri **hatırlamaz**. Veritabanında doğru ilacı bulabilmesi için, **Lütfen HER sorunuzda ilacın tam adını belirtin.**
        *(Örn: 'Yan etkileri nelerdir?' yerine 'Parol'un yan etkileri nelerdir?' şeklinde sorunuz.)*
        """)

        gr.ChatInterface(
            fn=chat_interface,
            chatbot=gr.Chatbot(height=400),
            textbox=gr.Textbox(placeholder="İlacın adını belirterek sorunuzu girin... (Örn: Parol hamilelikte kullanılır mı?)", container=False, scale=7),
            title="Sadece İlaç KT PDF'lerine Dayanarak Cevap Veren Asistan",
        )
    demo.launch(server_name=host, server_port=port, share=share, ssr_mode=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--share", action="store_true", help="Create a public link for Gradio")
    args = parser.parse_args()
    main(args.host, args.port, True)
