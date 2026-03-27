import os
from app.ui import main

if __name__ == "__main__":
    # Hugging Face Spaces üzerinden çalışırken share=False ve host=0.0.0.0 olmalıdır.
    # Gradio HF spaces tarafında varsayılan 7860 portunu kullanır.
    main(host="0.0.0.0", port=7860, share=False)
