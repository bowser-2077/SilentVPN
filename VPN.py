import sys
import subprocess
import threading
import os
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QMovie
from plyer import notification

class ProcessOutput(QObject):
    new_output = Signal(str)

def get_public_ip():
    try:
        return requests.get("https://checkip.amazonaws.com/", timeout=5).text.strip()
    except:
        return "Erreur"

def kill_openvpn_processes():
    subprocess.run('taskkill /F /IM openvpn.exe', shell=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def install_tap_manual():
    driver_path = os.path.abspath("tap_driver\\Oemvista.inf")
    devcon_path = os.path.abspath("tap_driver\\devcon.exe")
    subprocess.run([devcon_path, "install", driver_path, "tap0901"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)

def check_tap():
    result = subprocess.run(
        'powershell "Get-NetAdapter -Name *TAP* | Where-Object { $_.Status -eq \'Up\' }"',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    return b'TAP' in result.stdout

class VPNGui(QWidget):
    def __init__(self):
        super().__init__()

        self.status_label = QLabel("Aucun VPN connecté")
        self.status_label.setStyleSheet("font-size: 16pt; font-weight: 600; color: #e0e0e0;")

        font = QFont("Segoe UI Emoji")
        self.status_label.setFont(font)

        # Continue la suite de ta construction d'interface

        self.setWindowTitle("SilentVPN Ultra Light")
        self.setMinimumSize(600, 400)
        self.openvpn_path = "./openvpn/openvpn.exe"
        self.process = None
        self.selected_server = None
        self.output_handler = ProcessOutput()
        self.output_handler.new_output.connect(self.on_connected)

        # Layout

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        self.status_label = QLabel("Aucun VPN connecté")
        self.status_label.setStyleSheet("font-size: 16pt; font-weight: 600; color: #e0e0e0;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.ip_new_label = QLabel("Nouvelle IP : --")
        self.ip_new_label.setStyleSheet("font-size: 14pt; color: #ffffff;")
        layout.addWidget(self.ip_new_label)

        self.ip_label = QLabel("IP actuelle : --")
        self.ip_label.setStyleSheet("font-size: 14pt; color: #ffffff;")
        layout.addWidget(self.ip_label)

        self.title = QLabel("SilentVPN")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 28pt; font-weight: bold; color: #38BDF8;")
        layout.addWidget(self.title)

        self.status = QLabel("Aucun VPN connecté")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-size: 14pt; color: white;")
        layout.addWidget(self.status)

        self.ip_label = QLabel("IP actuelle : --")
        self.ip_label.setAlignment(Qt.AlignCenter)
        self.ip_label.setStyleSheet("font-size: 12pt; color: gray;")
        layout.addWidget(self.ip_label)

        self.server_list = QListWidget()
        self.servers = [
            {"name": "France", "config": "vpn_paris.ovpn"},
            {"name": "Japon", "config": "vpn_tokyo.ovpn"},
            {"name": "Etats-Unis", "config": "vpn_ny.ovpn"},
            {"name": "Australie", "config": "vpn_sydney.ovpn"},
        ]
        for server in self.servers:
            item = QListWidgetItem(server["name"])
            item.setData(Qt.UserRole, server)
            self.server_list.addItem(item)
        self.server_list.setStyleSheet("""
            QListWidget {
                background-color: #1E293B;
                border-radius: 10px;
                color: #d4d4d4;
                font-size: 14pt;
            }
            QListWidget::item:selected {
                background-color: #38BDF8;
                color: black;
                font-weight: bold;
            }
        """)
        self.server_list.itemClicked.connect(self.select_server)
        layout.addWidget(self.server_list)

        self.toggle_button = QPushButton("OFF")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setStyleSheet(self.button_style("red"))
        self.toggle_button.clicked.connect(self.toggle_vpn)
        layout.addWidget(self.toggle_button)

        self.spinner = QLabel()
        self.spinner.setAlignment(Qt.AlignCenter)
        self.movie = QMovie("loader.gif")
        self.spinner.setMovie(self.movie)
        self.spinner.setVisible(False)
        layout.addWidget(self.spinner)

        if not check_tap():
            install_tap_manual()

    def button_style(self, invert=False):
        if invert:
            return """
                QPushButton {
                    background-color: #ef4444;
                    color: white;
                    font-size: 15pt;
                    border-radius: 15px;
                    padding: 12px 25px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #dc2626;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #38BDF8;
                    color: black;
                    font-size: 15pt;
                    border-radius: 15px;
                    padding: 12px 25px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #60dbff;
                }
            """

    def select_server(self, item):
        self.selected_server = item.data(Qt.UserRole)
        self.status.setText(f"Sélectionné : {self.selected_server['name']}")

    def toggle_vpn(self):
        if self.process:
            self.disconnect_vpn()
        else:
            if not self.selected_server:
                self.status.setText("❗ Sélectionnez un serveur")
                self.toggle_button.setChecked(False)
                return
            self.connect_vpn(self.selected_server["config"])

    def connect_vpn(self, config_file):
        self.ip_old = get_public_ip()
        self.update_status(f"Connexion au VPN...\nIP avant : {self.ip_old}")
        self.ip_label.setText(f"IP actuelle : {self.ip_old}")
        self.ip_new_label.setText("Nouvelle IP : --")

        kill_openvpn_processes()

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        except:
            startupinfo = None

        def run_vpn():
            try:
                print(f"[DEBUG] Lancement de : {self.openvpn_path} --config {config_file}")
                self.process = subprocess.Popen(
                    [self.openvpn_path, '--config', config_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    startupinfo=startupinfo,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                for line in self.process.stdout:
                    print("[VPN]", line.strip())

                    if "Initialization Sequence Completed" in line:
                        self.ip_new = get_public_ip()
                        print(f"[VPN] ✅ Connexion réussie. Nouvelle IP : {self.ip_new}")
                        self.output_handler.new_output.emit(f"✅ Connecté ! Nouvelle IP : {self.ip_new}")
                        self.toggle_button.setText("Déconnecter")

                        notification.notify(
                            title="VPN connecté",
                            message="Votre VPN est maintenant actif !",
                            app_name="SilentVPN",
                            timeout=5
                        )
                        break

                self.process.stdout.close()
                self.process.wait()
                print("[VPN] ❌ VPN déconnecté")
                self.output_handler.new_output.emit("❌ VPN déconnecté")
                self.process = None
                self.toggle_button.setText("Connecter")
            except Exception as e:
                print("[VPN] Erreur :", e)
                self.output_handler.new_output.emit(f"Erreur : {e}")

        threading.Thread(target=run_vpn, daemon=True).start()

    def update_status(self, text):
        self.status_label.setText(text)

    def disconnect_vpn(self):
        self.toggle_button.setEnabled(False)  # désactive temporairement
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None  # <-- très important

        self.toggle_button.setText("Connecter")  # remet le texte
        self.toggle_button.setStyleSheet(self.button_style(invert=False))  # remet en bleu
        self.toggle_button.setEnabled(True)
        self.status_label.setText("❌ VPN déconnecté")

    def on_connected(self, _):
        ip = get_public_ip()
        self.spinner.setVisible(False)
        self.movie.stop()
        self.toggle_button.setText("ON")
        self.toggle_button.setStyleSheet(self.button_style("green"))
        self.status.setText("✅ Connecté avec succès")
        self.ip_label.setText(f"Nouvelle IP : {ip}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#0F172A"))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor("#1E293B"))
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor("#38BDF8"))
    palette.setColor(QPalette.ButtonText, Qt.black)
    app.setPalette(palette)

    window = VPNGui()
    window.show()
    sys.exit(app.exec())
