"""Sobe o simulador do jeito do classificar_ligacoes_diario.py: usa a variável API_KEY (ou LLM_API_KEY/.env);
se não existir, pede a chave numa janela e NÃO salva em lugar nenhum. Testa a conexão antes de abrir.

Uso:  python iniciar.py            (abre em http://127.0.0.1:8000)
      python iniciar.py --offline  (sem GPT: só para ver telas, catálogo e estoque; o vendedor responde contingência)
"""
import os
import sys
import webbrowser


def pedir_chave() -> str:
    try:
        import tkinter as tk
        from tkinter import simpledialog
        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        chave = simpledialog.askstring("Chave do llm-gate", "Cole a chave do llm-gate (API_KEY):", show="*", parent=raiz)
        raiz.destroy()
        return chave or ""
    except Exception:  # noqa: BLE001 - sem interface gráfica: pergunta no terminal
        import getpass
        return getpass.getpass("Chave do llm-gate (API_KEY): ")


def main() -> None:
    offline = "--offline" in sys.argv
    from services import llm_client  # carrega .env, se existir

    if offline:
        os.environ["LLM_MODE"] = "mock"
    else:
        if not llm_client.api_key():
            os.environ["API_KEY"] = pedir_chave()  # só na memória deste processo
        os.environ.setdefault("LLM_MODE", "llm")
        print("Testando conexão com o llm-gate...\n")
        if llm_client.diagnosticar() != 0:
            sys.exit("\nSem conexão com o GPT. Corrija acima ou rode:  python iniciar.py --offline")
    import uvicorn
    webbrowser.open("http://127.0.0.1:8000")
    uvicorn.run("app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
