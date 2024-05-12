import hashlib
import threading
import socket
import os
import time
import requests
import math
import json
import pprint
import random
from contextlib import suppress
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sv_ttk


TRACKER_URL = 'http://192.168.0.102:8000'


class File:
    def __init__(self, path: str, ip, log_callback=None):
        self.piece_size = 102400
        self.block_size = self.piece_size // 2
        self.path = path
        self.peer_ip = ip
        self.log_callback = log_callback

    def calculate_sha1(self, data):
        sha1_hash = hashlib.sha1()
        if isinstance(data, str):
            data = data.encode()
        sha1_hash.update(data)
        sha1_digest = sha1_hash.hexdigest()
        return sha1_digest

    def divide_file_into_pieces(self):
        name = os.path.basename(self.path)
        pieces = []
        total_data = bytearray()
        file_info = {}
        piece_mappings = []
        current_offset = 0

        if os.path.isdir(self.path):
            total_size = sum(os.path.getsize(os.path.join(root, file))
                             for root, _, files in os.walk(self.path) for file in files)
        elif os.path.isfile(self.path):
            total_size = os.path.getsize(self.path)
        else:
            error_msg = "Provided path is neither a file nor a directory."
            self.update_gui_log(error_msg, "red")
            raise ValueError(error_msg)

        if os.path.isdir(self.path):
            for root, dirs, files in os.walk(self.path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, start=self.path)
                    full_path = os.path.join(name, relative_path)
                    file_size = os.path.getsize(file_path)
                    file_info[full_path] = file_size
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        total_data.extend(file_data)
                        start_piece_index = current_offset // self.piece_size
                        end_piece_index = (current_offset + file_size - 1) // self.piece_size
                        piece_mappings.append({
                            'file_path': full_path,
                            'start_piece': start_piece_index,
                            'end_piece': end_piece_index,
                            'start_offset': current_offset,
                            'end_offset': (current_offset + file_size - 1)
                        })
                        current_offset += file_size
                        self.show_progress(name, current_offset, total_size)
        elif os.path.isfile(self.path):
            with open(self.path, 'rb') as f:
                file_data = f.read()
                total_data.extend(file_data)
                full_path = name
                file_info[full_path] = total_size
                self.show_progress(name, total_size, total_size)
        for i in range(0, len(total_data), self.piece_size):
            piece = total_data[i:i + self.piece_size]
            pieces.append(piece)
        return {
            'name': name,
            'pieces': pieces,
            'info': {
                'file_info': file_info,
                'piece_mappings': piece_mappings
            }
        }

    def show_progress(self, filename, processed, total):
        progress = int(50 * processed / total)
        progress_bar = '#' * progress + '-' * (50 - progress)
        # print(f"\rPeer {self.peer_ip}~{filename} {progress_bar} {int(100 * processed / total)}%", end='')
        msg = f"\rPeer {self.peer_ip}~{filename} \n{progress_bar} {int(100 * processed / total)}%"
        self.update_gui_log(msg, None)
        if processed >= total:
            print()
        time.sleep(0.5)

    def create_torrent_file(self, file_data):
        pieces_hash = ''.join([self.calculate_sha1(piece) for piece in file_data['pieces']])
        torrent_data = {
            'announce': TRACKER_URL,
            'info': {
                'piece length': self.piece_size,
                'pieces': pieces_hash
            }
        }
        if 'piece_mappings' in file_data['info'] and len(file_data['info']['piece_mappings']) > 0:
            torrent_data['info']['files'] = []
            torrent_data['info']['name'] = file_data['name']
            for mapping in file_data['info']['piece_mappings']:
                file_length = file_data['info']['file_info'].get(mapping['file_path'])
                if file_length is None:
                    error_msg = f"File size missing for {mapping['file_path']}"
                    self.update_gui_log(error_msg, None)
                    raise ValueError(f"File size missing for {mapping['file_path']}")
                file_entry = {
                    'length': file_length,
                    'path': mapping['file_path'].split(os.sep),
                    'mapping': {
                        'start_piece': mapping['start_piece'],
                        'end_piece': mapping['end_piece'],
                        'start_offset': mapping['start_offset'],
                        'end_offset': mapping['end_offset']
                    }
                }
                torrent_data['info']['files'].append(file_entry)
        else:
            single_file_key = next(iter(file_data['info']['file_info']))
            torrent_data['info']['name'] = single_file_key
            torrent_data['info']['length'] = file_data['info']['file_info'][single_file_key]
        return torrent_data

    def update_gui_log(self, msg, color=None):
        if self.log_callback:
            if color:
                self.log_callback(msg, color)
            else:
                self.log_callback(msg)

class Peer(threading.Thread):
    def __init__(self, port=5005, log_callback=None):
        super().__init__()
        self.host_name = socket.gethostname()
        self.peer_ip = socket.gethostbyname(self.host_name)
        self.port = port
        self.server_socket = None
        self.running = True
        self.OUTPUT_PATH = os.path.join(os.getcwd(), 'output')
        self.files = []
        self.SERVER_IP = '192.168.0.102'  # CHANGE THIS TO YOUR SERVER IP
        self.SERVER_PORT = 6000  # THIS SHOULD MATCH THE PORT IN s.py
        self.handle_file = File('', self.peer_ip, log_callback)
        self.log_callback = log_callback

    def update_gui_log(self, msg, color=None):
        if self.log_callback:
            if color:
                self.log_callback(msg, color)
            else:
                self.log_callback(msg)

    def run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.peer_ip, self.port))
        self.server_socket.listen(10)
        # msg = f"\033[33mPeer {self.peer_ip}:{self.port} listening on port {self.port}\033[0m"
        msg = f"Peer {self.peer_ip}:{self.port} listening on port {self.port}"
        self.update_gui_log(msg, "yellow")
        try:
            while self.running:
                client_socket, addr = self.server_socket.accept()
                if not self.running:
                    break
                # msg = f"\033[96mPeer {self.peer_ip}:{self.port} connected to {addr}\033[0m"
                msg = f"Peer {self.peer_ip}:{self.port} connected to {addr}"
                self.update_gui_log(msg, "cyan")
                threading.Thread(target=self.handle_client, args=(client_socket,)).start()
        finally:
            # msg = f"\033[33mPeer {self.peer_ip} listening on port {self.port}\033[0m"
            msg = f"Peer {self.peer_ip} listening on port {self.port}"
            self.update_gui_log(msg, "yellow")
            self.server_socket.close()

    def update_tracker_upload(self, torrent_data):
        piece_length = torrent_data['info']['piece length']
        if 'length' in torrent_data['info']:
            file_length = torrent_data['info']['length']
            file_details = None
        else:
            file_length = sum(file['length'] for file in torrent_data['info']['files'])
            file_details = [{'name': "/".join(f['path']), 'length': f['length']} for f in torrent_data['info']['files']]
        number_of_pieces = math.ceil(file_length / piece_length)
        payload = {
            "peer_ip": self.peer_ip,
            "peer_port": self.port,
            "file_name": torrent_data['info']['name'],
            "pieces_indices": list(range(number_of_pieces)),
            "file_details": file_details
        }
        response = requests.post(torrent_data['announce'] + '/peer-update', json=payload)
        msg = f"Peer {self.peer_ip}:{self.port} " + response.text
        self.update_gui_log(msg, None)

    def update_tracker_download(self, torrent_data):
        payload = {
            "peer_ip": self.peer_ip,
            "peer_port": self.port,
            "file_name": torrent_data['file_name'],
            "pieces_indices": torrent_data['pieces_indices'],
        }
        response = requests.post(TRACKER_URL + '/peer-update-download', json=payload)
        msg = f"Peer {self.peer_ip}:{self.port} " + response.text
        self.update_gui_log(msg, None)

    def calculate_piece_indices_for_file(self, torrent_data, filename):
        piece_length = torrent_data['info']['piece length']
        files = torrent_data['info'].get('files', [])
        total_length = 0
        file_byte_ranges = {}
        for file in files:
            file_path = '/'.join(file['path'])
            start_byte = total_length
            end_byte = start_byte + file['length'] - 1
            file_byte_ranges[file_path] = (start_byte, end_byte)
            total_length += file['length']
        if filename not in file_byte_ranges:
            if filename == torrent_data['info']['name']:
                total_length = torrent_data['info']['length'] if 'length' in torrent_data['info'] else total_length
                start_index = 0
                end_index = (total_length - 1) // piece_length
            else:
                return []
        else:
            start_byte, end_byte = file_byte_ranges[filename]
            start_index = start_byte // piece_length
            end_index = end_byte // piece_length
        return list(range(start_index, end_index + 1))

    def get_peers_for_pieces(self, tracker_url, filename, piece_indices):
        piece_indices_str = ','.join(map(str, piece_indices))
        url = f"{tracker_url}/get-peer?filename={filename}&piece_indices={piece_indices_str}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            peer_data = response.json()
            # msg = f"\033[34mReceived peer-set: \033[0m{peer_data}\033[0m"
            msg = f"Received peer-set: {peer_data}"
            self.update_gui_log(msg, "blue")
            return peer_data
        except requests.RequestException as e:
            msg = f"Failed to get peer data: {e}"
            self.update_gui_log(msg, None)
            return {}

    def handle_client(self, client_socket):
        with client_socket:
            while True:
                data = client_socket.recv(1024).decode()
                response = 'Response OK'
                if not data:
                    break
                parts = data.split()
                file, cmd = data.rsplit(' ', 1)
                if (cmd == 'download'):
                    first_part = file.split('/')[0]
                    torrent_data = self.get_torrent(first_part)
                    requested_pieces = self.calculate_piece_indices_for_file(torrent_data, file)
                    peer_set = self.get_peers_for_pieces(torrent_data['announce'], first_part, requested_pieces)
                    info = {first_part: {}}
                    is_success = [True]
                    threads = []
                    for piece_index, peer_ips in peer_set.items():
                        thread = threading.Thread(target=self.request_piece_from_peer,
                                                  args=(piece_index, peer_ips, first_part, info, is_success))
                        thread.start()
                        threads.append(thread)
                    for thread in threads:
                        thread.join()
                    if is_success[0]:
                        temp = dict(sorted(info[first_part].items()))
                        temp_hash = ''
                        for index in temp:
                            temp_hash += self.handle_file.calculate_sha1(temp[index])
                        msg = f"Downloaded pieces hash: {temp_hash}"
                        self.update_gui_log(msg, "blue")
                        if temp_hash == torrent_data['info']['pieces']:
                            msg = "Downloaded pieces match the hash in the torrent file."
                            self.update_gui_log(msg, "blue")
                            self.files.append(info)
                            data_update = {
                                "file_name": first_part,
                                "pieces_indices": requested_pieces
                            }
                            self.update_tracker_download(data_update)
                            self.reconstruct_file(file, torrent_data)
                            client_socket.sendall(response.encode())
                            msg = f"Peer {self.peer_ip}:{self.port} has downloaded: {file}"
                            self.update_gui_log(msg, "blue")
                        else:
                            msg = f"Downloaded pieces do not match the hash in the torrent file."
                            self.update_gui_log(msg, "red")

                            response = 'Response Failed'
                            client_socket.sendall(response.encode())
                    else:
                        response = 'Response Failed'
                        msg = f"Failed to download pieces, there seems to be an issue with the peer."
                        self.update_gui_log(msg, "red")
                        client_socket.sendall(response.encode())
                elif (cmd == 'upload'):
                    self.handle_file.path = file
                    res = self.handle_file.divide_file_into_pieces()
                    self.files.append({res['name']: {str(i): value for i, value in enumerate(res['pieces'])}})
                    for each in self.files:
                        for key, value in each.items():
                            for k, v in value.items():
                                msg = f"Piece {k} of file {key} has length: {len(v)}"
                                self.update_gui_log(msg, "blue")
                    torrent_data = self.handle_file.create_torrent_file(res)
                    self.update_tracker_upload(torrent_data)
                    json_str = json.dumps(torrent_data)
                    self.update_torrent_server(f"{json_str} add")
                    client_socket.sendall(response.encode())
                    msg = f"Peer {self.peer_ip}:{self.port} has uploaded: {file}"
                    self.update_gui_log(msg, "blue")
                elif (cmd == 'block'):
                    index, offset = parts[0].split('-')
                    parts = file.split(' ', 1)
                    filename = parts[1]
                    response = bytearray()
                    for each in self.files:
                        if filename in each:
                            if index in each[filename]:
                                piece = each[filename].get(index)
                                piece_length = len(piece)
                                offset = int(offset)
                                if (offset < piece_length):
                                    end = min(offset + self.handle_file.block_size, piece_length)
                                    response = piece[offset:end]
                                break
                            else:
                                error_msg = f"Piece {index} not found for file {filename}"
                                self.update_gui_log(error_msg, None)
                                raise ValueError(f"Piece {index} not found for file {filename}")
                    client_socket.sendall(response)
                elif (cmd == 'length'):
                    filename, index = file.rsplit(' ', 1)
                    piece_length = 0
                    for each in self.files:
                        if filename in each:
                            piece = each[filename].get(index)
                            piece_length = len(piece)
                            break
                    client_socket.sendall(str(piece_length).encode())
                elif (cmd == 'construct'):
                    self.reconstruct_file(file)
                    client_socket.sendall('Response OK'.encode())

    def stop(self):
        self.running = False
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp_socket.connect((self.peer_ip, self.port))
        temp_socket.close()

    def get_torrent(self, file):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect((self.SERVER_IP, self.SERVER_PORT))
        peer_socket.sendall(f"{file} get".encode())
        response = peer_socket.recv(1024).decode()
        peer_socket.close()

        torrent = json.loads(response)
        msg = f"Peer {self.peer_ip}:{self.port} has received torrent file:"
        self.update_gui_log(msg, "blue")
        pprint.pprint(torrent)
        return torrent

    def request_block_from_peer(self, piece_index, block_offset, peer_ips, file, index, blocks, info):
        temp = peer_ips

        while True:
            value = random.choice(temp)
            try:
                peer_ip, peer_port = value
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer_ip, peer_port))
                sock.sendall(f"{piece_index}-{block_offset} {file} block".encode())
                response = sock.recv(self.handle_file.block_size)
                sock.close()
                blocks[index] = response
                break
            except:
                with suppress(ValueError):
                    temp.remove(value)
                if len(temp) == 0:
                    info['is_success'] = False
                    break

    def request_piece_from_peer(self, piece_index, peer_ips, file, piece_info, is_success):
        piece_size = 0
        temp = peer_ips
        while True:
            value = random.choice(temp)
            try:
                peer_ip, peer_port = value
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer_ip, peer_port))
                sock.sendall(f"{file} {piece_index} length".encode())
                piece_size = sock.recv(1024)
                sock.close()
                if (piece_size):
                    break
                else:
                    with suppress(ValueError):
                        temp.remove(value)
                    if len(temp) == 0:
                        return {'is_success': False}
            except:
                with suppress(ValueError):
                    temp.remove(value)
                if len(temp) == 0:
                    return {'is_success': False}
        piece = bytearray()
        blocks = {}
        block_offset = 0
        info = {'is_success': True}
        num = math.ceil(int(piece_size.decode()) / self.handle_file.block_size)
        pool = []
        for index in range(num):
            block_offset = index * self.handle_file.block_size
            thread = threading.Thread(target=self.request_block_from_peer,
                                      args=(piece_index, block_offset, peer_ips, file, index, blocks, info))
            thread.start()
            pool.append(thread)

        for thread in pool:
            thread.join()

        blocks = dict(sorted(blocks.items()))
        for index in blocks:
            piece.extend(blocks[index])
        info['piece'] = piece
        is_success[0] = info['is_success']
        piece_info[file][piece_index] = piece

    def reconstruct_file(self, target_filename, torrent_data):
        root = target_filename.split('/')[0]

        for file_dict in self.files:
            if root in file_dict:
                pieces = file_dict[root]
                sorted_piece_keys = sorted(pieces.keys(), key=int)
                complete_file_data = bytearray()
                for key in sorted_piece_keys:
                    complete_file_data.extend(pieces[key])
                if not os.path.exists(self.OUTPUT_PATH):
                    os.makedirs(self.OUTPUT_PATH)
                if ('length' in torrent_data['info']):
                    output_path = os.path.join(self.OUTPUT_PATH, root)
                    with open(output_path, 'wb') as file:
                        file.write(complete_file_data)
                    msg = f"File successfully reconstructed and saved to "
                    self.update_gui_log(msg, "blue")
                    msg = output_path
                    self.update_gui_log(msg, None)
                else:
                    name = torrent_data['info']['name']
                    files = torrent_data['info']['files']
                    for file_info in files:
                        file_path = os.path.join(*file_info['path'])
                        if target_filename == file_path:
                            dirs = file_info['path'][:-1]
                            output_dir = os.path.join(*dirs)
                            os.makedirs(output_dir, exist_ok=True)
                            output_path = os.path.join(self.OUTPUT_PATH, file_info['path'][-1])
                            with open(output_path, 'wb') as file:
                                start = file_info['mapping']['start_offset']
                                end = file_info['mapping']['end_offset']
                                file.write(complete_file_data[start:end])
                            msg = f"File successfully reconstructed and saved to "
                            self.update_gui_log(msg, "blue")
                            msg = output_path
                            self.update_gui_log(msg, None)
                            return
                    if target_filename == name:
                        for file_info in files:
                            dirs = file_info['path'][:-1]
                            output_dir = os.path.join(self.OUTPUT_PATH, *dirs)
                            os.makedirs(output_dir, exist_ok=True)
                            output_path = os.path.join(output_dir, file_info['path'][-1])
                            with open(output_path, 'wb') as file:
                                start = file_info['mapping']['start_offset']
                                end = file_info['mapping']['end_offset']
                                file.write(complete_file_data[start:end])
                        msg = f"File successfully reconstructed and saved to "
                        self.update_gui_log(msg, "blue")
                        msg = target_filename
                        self.update_gui_log(msg, None)

                return
        msg = f"File {target_filename} not found in the provided data."
        self.update_gui_log(msg, None)

    def update_torrent_server(self, data):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect((self.SERVER_IP, self.SERVER_PORT))
        peer_socket.sendall(data.encode())
        response = peer_socket.recv(1024).decode()
        peer_socket.close()

class MainApplication(tk.Tk):
    def __init__(self) -> None:
        tk.Tk.__init__(self)

        self.title("Simple File-Sharing Application: Client")
        self.iconbitmap('C:/Users/thien/OneDrive/Máy tính/BK/231/Project HDL/cse.ico')
        self.geometry("800x600")

        self.main_view = MainView(self)
        self.main_view.pack(fill='both', expand=True)

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
        self.peer = Peer(log_callback=self.update_log)
        self.peer.start()
        self.create_widgets()
        self.refresh_id = None
        self.log_text.tag_config("red", foreground="red")
        self.log_text.tag_config("blue", foreground="blue")
        self.log_text.tag_config("yellow", foreground="#F2D21E")
        self.log_text.tag_config("cyan", foreground="cyan")

    def create_widgets(self) -> None:
        # Create a frame to contain buttons and entry
        frame_buttons = ttk.Frame(self)

        # Upload button
        upload_button = ttk.Button(frame_buttons, text="Upload", command=self.upload_file)
        upload_button.grid(row=0, column=0, padx=5, pady=5)

        # Download button
        download_button = ttk.Button(frame_buttons, text="Download", command=self.download_file)
        download_button.grid(row=0, column=1, padx=5, pady=5)

        # Show button
        show_button = ttk.Button(frame_buttons, text="Show", command=self.show_files)
        show_button.grid(row=0, column=2, padx=5, pady=5)

        # File name entry
        self.file_name_entry = ttk.Entry(frame_buttons, width=80)
        self.file_name_entry.grid(row=1, column=0, columnspan=3, padx=5, pady=5)

        frame_buttons.pack(side="top", padx=10, pady=10)

        # Log text
        self.log_text.pack(expand=True, fill="both")

        self.auto_refresh()

    def auto_refresh(self):
        self.refresh_id = self.after(1000, self.auto_refresh)

    def update_log(self, msg, color=None):
        if color:
            self.log_text.insert(tk.END, msg + "\n", color)
        else:
            self.log_text.insert(tk.END, msg + "\n")

        self.log_text.see(tk.END)  # Auto-scroll to the bottom

    def upload_file(self):
        file_name = self.file_name_entry.get()
        threading.Thread(target=self.upload_file_worker, args=(file_name,)).start()

    def download_file(self):
        file_name = self.file_name_entry.get()
        threading.Thread(target=self.download_file_worker, args=(file_name,)).start()

    def show_files(self):
        threading.Thread(target=self.show_files_worker).start()

    def upload_file_worker(self, file_name):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect((self.peer.peer_ip, self.peer.port))
        peer_socket.sendall(f"{file_name} upload".encode())
        response = peer_socket.recv(1024)
        peer_socket.close()

    def download_file_worker(self, file_name):
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect((self.peer.peer_ip, self.peer.port))
        peer_socket.sendall(f"{file_name} download".encode())
        response = peer_socket.recv(1024)
        peer_socket.close()

    def show_files_worker(self):
        response = requests.get(TRACKER_URL + '/show')
        response.raise_for_status()
        data = response.json()
        if 'files' in data:
            # for name in data['files']:
            #     print(name)
            file_list = '\n'.join(data['files'])
            self.update_log(file_list, "blue")

def apply_global_font_to_tabs(notebook):
    style = ttk.Style()
    style.configure("TNotebook", font=("Times New Roman", 12, "bold"))
    style.configure("TNotebook.Tab", font=("Times New Roman", 12, "bold"))

if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()
