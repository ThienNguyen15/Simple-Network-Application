import socket
import threading
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sv_ttk

class Server(threading.Thread):
    def __init__(self, port=6000, log_callback=None):
        super().__init__()
        self.host_name = socket.gethostname()
        self.ip = socket.gethostbyname(self.host_name)
        self.port = port
        self.peers = []
        self.torrent_tracker = {}
        self.max_peers = 10
        self.running = True
        self.torrents = []
        self.log_callback = log_callback

    def handle_client(self, server_socket):
        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                if not self.running:
                    break

                msg = f"Server {self.ip}:{self.port} connected to {addr}"
                if self.log_callback:
                    self.log_callback(msg)

                while True:
                    data = client_socket.recv(1024).decode()
                    if not data:
                        break
                    parts = data.split()
                    cmd = parts.pop()
                    if cmd == 'add':
                        last_closing_brace_index = data.rfind('}')
                        json_str = data[:last_closing_brace_index + 1]
                        json_obj = json.loads(json_str)
                        self.torrents.append(json_obj)
                        msg = "Added torrent:\n" + json.dumps(json_obj, indent=4)
                        if self.log_callback:
                            self.log_callback(msg)
                        client_socket.sendall("Added".encode())
                    if cmd == 'get':
                        file = ' '.join(parts)
                        for torrent in self.torrents:
                            if torrent['info']['name'] == file:
                                client_socket.sendall(json.dumps(torrent).encode())
                                break
                        else:
                            client_socket.sendall("File not found".encode())
        finally:
            print(f"Closing server socket on {self.ip}")
            server_socket.close()

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.ip, self.port))
        server_socket.listen(self.max_peers)
        msg = f"Server is listening on {self.ip}:{self.port}"
        if self.log_callback:
            self.log_callback(msg)

        thread1 = threading.Thread(target=self.handle_client, args=(server_socket,))
        thread1.start()
        thread1.join()

    def stop(self):
        self.running = False
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_socket.connect((self.ip, self.port))
        temp_socket.close()

class MainApplication(tk.Tk):
    def __init__(self) -> None:
        tk.Tk.__init__(self)

        self.title("Simple File-Sharing Application: Server")
        self.iconbitmap('C:/Users/thien/OneDrive/Máy tính/BK/231/Project HDL/cse.ico')
        self.geometry("669x432")

        self.server = Server(log_callback=self.update_log)
        self.main_view = MainView(self)  # Pass Server instance to MainView
        self.main_view.pack()

        s = ttk.Style()
        s.theme_use("default")
        sv_ttk.use_light_theme()
        self.load_azure_theme()

        # Apply global font
        self.apply_global_font(s)

    def apply_global_font(self, style):
        global_font = ("Times New Roman", 12, "bold")
        self.option_add("*Font", global_font)
        style.configure("TLabel", font=global_font)

    def load_azure_theme(self):
        self.tk.call("source", "azure.tcl")
        self.tk.call("set_theme", "light")

    def update_log(self, msg):
        self.main_view.log_tab.update_log(msg)

class MainView(ttk.Frame):
    def __init__(self, parent: MainApplication) -> None:
        super().__init__(parent)
        self.parent = parent

        self.create_widgets()

    def create_widgets(self) -> None:
        self.tab_control = ttk.Notebook(self)

        self.log_tab = LogTab(self)
        self.tab_control.add(self.log_tab, text="Logs")

        self.tab_control.pack(expand=1, fill="both")

        # Apply global font to all tabs
        apply_global_font_to_tabs(self.tab_control)

class LogTab(ttk.Frame):
    def __init__(self, parent: MainView) -> None:
        super().__init__(parent)
        self.parent = parent
        self.log_text = tk.Text(self)
        self.create_widgets()
        self.refresh_id = None

    def create_widgets(self) -> None:
        self.log_text.pack(expand=True, fill="both")
        self.auto_refresh()

    def auto_refresh(self):
        self.refresh_id = self.after(1000, self.auto_refresh)

    def update_log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)  # Auto-scroll to the bottom

def apply_global_font_to_tabs(notebook):
    style = ttk.Style()
    style.configure("TNotebook", font=("Times New Roman", 12, "bold"))
    style.configure("TNotebook.Tab", font=("Times New Roman", 12, "bold"))

def main():
    app = MainApplication()
    app.server.start()
    app.mainloop()

    app.server.stop()
    app.server.join()

if __name__ == "__main__":
    main()
