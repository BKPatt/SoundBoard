import os
import json
import pyaudio
import wave
import threading
from pynput import keyboard as pynput_keyboard
from PyQt5.QtWidgets import (QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QListWidget, QFileDialog,
                             QMessageBox, QDialog, QInputDialog, QLineEdit, QComboBox, QDesktopWidget,
                             QLabel)
from PyQt5.QtCore import QFileSystemWatcher, pyqtSlot
from PyQt5.QtGui import QIcon
import pygame
import mutagen
import logging
import audioop
import numpy as np
from HotkeyDialog import HotkeyDialog
from SoundItem import SoundItem
from util import CHUNK, CONFIG_FILE, SOUNDS_DIR, silence_pygame

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class SoundPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.speaker_stream = None
        self.virtual_cable_stream = None
        self.frames = []
        self.sounds = {}
        self.hotkeys = {}
        self.virtual_cables = self.get_virtual_cables()
        self.selected_virtual_cable = self.get_default_virtual_cable()
        self.is_playing_sound = False
        self.current_sound_data = np.array([], dtype=np.int16)
        
        icon_path = os.path.join(os.path.dirname(__file__), 'virt_soundboard.png')
        self.setWindowIcon(QIcon(icon_path))
        
        self.init_ui()
        self.load_config()
        self.setup_keyboard_listener()
        self.setup_file_watcher()
        self.setup_audio_routing()
        self.hotkey_dialog = None
        self.current_keys = set()
        
        with silence_pygame():
            pygame.init()

    def init_ui(self):
        self.setWindowTitle('Virtual Sound Board')
        self.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 4px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QListWidget {
                background-color: #34495e;
                border: 1px solid #2c3e50;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                background-color: #34495e;
                color: #ecf0f1;
                padding: 5px;
                margin: 2px 0;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: #3498db;
            }
            QLineEdit, QComboBox {
                padding: 8px;
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #2c3e50;
                border-radius: 4px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search sounds...")
        self.search_input.textChanged.connect(self.filter_sounds)
        search_layout.addWidget(self.search_input, 3)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Favorites First", "Most Played"])
        self.sort_combo.currentIndexChanged.connect(self.sort_sound_list)
        search_layout.addWidget(self.sort_combo, 1)
        
        main_layout.addLayout(search_layout)
        
        self.sound_list = QListWidget()
        self.sound_list.setDragDropMode(QListWidget.InternalMove)
        self.sound_list.itemDoubleClicked.connect(self.play_selected_sound)
        self.sound_list.itemClicked.connect(self.update_hotkey_button_text)
        self.sound_list.setAcceptDrops(True)
        self.sound_list.setDragEnabled(True)
        self.sound_list.setDropIndicatorShown(True)
        main_layout.addWidget(self.sound_list)
        
        button_layout = QHBoxLayout()        
        add_button = QPushButton(QIcon("add_icon.png"), "Add")
        add_button.clicked.connect(self.add_sound_file)
        button_layout.addWidget(add_button)
        
        play_button = QPushButton(QIcon("play_icon.png"), "Play")
        play_button.clicked.connect(self.play_selected_sound)
        button_layout.addWidget(play_button)
        
        self.assign_hotkey_button = QPushButton(QIcon("hotkey_icon.png"), "Hotkey")
        self.assign_hotkey_button.clicked.connect(self.assign_hotkey)
        button_layout.addWidget(self.assign_hotkey_button)
        
        delete_button = QPushButton(QIcon("delete_icon.png"), "Delete")
        delete_button.clicked.connect(self.delete_selected_sound)
        button_layout.addWidget(delete_button)
        
        rename_button = QPushButton(QIcon("rename_icon.png"), "Rename")
        rename_button.clicked.connect(self.rename_sound)
        button_layout.addWidget(rename_button)
        
        input_device_layout = QHBoxLayout()
        input_device_label = QLabel("Virtual Cable (8 Input Channels):")
        self.virtual_cable_combo = QComboBox()
        
        for device in self.virtual_cables:
            self.virtual_cable_combo.addItem(f"{device['name']}")
        
        if not self.virtual_cables:
            self.virtual_cable_combo.addItem("No compatible virtual cables detected")
            self.virtual_cable_combo.setEnabled(False)
        
        self.virtual_cable_combo.setCurrentIndex(self.get_default_virtual_cable_index())
        self.virtual_cable_combo.currentIndexChanged.connect(self.on_virtual_cable_changed)
        input_device_layout.addWidget(input_device_label)
        input_device_layout.addWidget(self.virtual_cable_combo)
        main_layout.addLayout(input_device_layout)
        
        favorite_button = QPushButton(QIcon("star_icon.png"), "Favorite")
        favorite_button.clicked.connect(self.toggle_favorite)
        button_layout.addWidget(favorite_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
    def setup_virtual_cable(self):
        def audio_callback(in_data, frame_count, time_info, status):
            in_data_array = np.frombuffer(in_data, dtype=np.int16)
            
            if self.is_playing_sound and len(self.current_sound_data) > 0:
                if len(self.current_sound_data) >= len(in_data_array):
                    sound_chunk = self.current_sound_data[:len(in_data_array)]
                    self.current_sound_data = self.current_sound_data[len(in_data_array):]
                else:
                    sound_chunk = np.pad(self.current_sound_data, (0, len(in_data_array) - len(self.current_sound_data)))
                    self.current_sound_data = np.array([], dtype=np.int16)

                mixed_audio = np.clip(in_data_array.astype(np.int32) + sound_chunk.astype(np.int32), -32768, 32767).astype(np.int16)
            else:
                mixed_audio = in_data_array
                self.is_playing_sound = False

            return (mixed_audio.tobytes(), pyaudio.paContinue)

        input_device_index = self.selected_input_device['index']
        output_device_index = self.get_vb_cable_output_index()

        if output_device_index is None:
            QMessageBox.warning(self, "VB-Cable Not Found", 
                                "VB-Cable was not detected. Please install it for proper audio routing.")
            output_device_index = self.audio.get_default_output_device_info()['index']

        self.virtual_cable = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            output=True,
            input_device_index=input_device_index,
            output_device_index=output_device_index,
            stream_callback=audio_callback,
            frames_per_buffer=CHUNK
        )
        self.virtual_cable.start_stream()

        self.virtual_cable = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            output=True,
            input_device_index=self.selected_input_device['index'],
            stream_callback=audio_callback,
            frames_per_buffer=CHUNK
        )
        self.virtual_cable.start_stream()
        
    def get_vb_cable_output_index(self):
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if "CABLE Input" in dev_info['name']:
                return i
        return None
        
    def get_virtual_cables(self):
        virtual_cables = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if self.is_virtual_cable(device_info['name']) and device_info['maxInputChannels'] == 8:
                virtual_cables.append(device_info)
                logging.info(f"Detected valid virtual cable: {device_info['name']}")
            elif self.is_virtual_cable(device_info['name']):
                logging.info(f"Skipped virtual cable (doesn't have 8 input channels): {device_info['name']}")

        if not virtual_cables:
            logging.warning("No virtual cables with 8 input channels detected.")
        else:
            logging.info(f"Total valid virtual cables detected: {len(virtual_cables)}")
        
        return virtual_cables
    
    def is_virtual_cable(self, device_name):
        virtual_cable_keywords = ['vb-audio', 'cable', 'virtual', 'voicemeeter']
        return any(keyword in device_name.lower() for keyword in virtual_cable_keywords)

    def get_default_virtual_cable(self):
        if self.virtual_cables:
            return self.virtual_cables[0]
        return None
    
    def get_default_virtual_cable_index(self):
        default_cable = self.get_default_virtual_cable()
        if default_cable:
            return self.virtual_cables.index(default_cable)
        return 0

    def on_virtual_cable_changed(self, index):
        self.selected_virtual_cable = self.virtual_cables[index]
        print(f"Selected virtual cable: {self.selected_virtual_cable['name']}")
        self.setup_audio_routing()

    def on_input_device_changed(self, index):
        self.selected_input_device = self.input_devices[index]
        print(f"Selected input device: {self.selected_input_device['name']}")
        self.setup_virtual_cable()

    def filter_sounds(self, text):
        for i in range(self.sound_list.count()):
            item = self.sound_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def setup_file_watcher(self):
        self.file_watcher = QFileSystemWatcher([SOUNDS_DIR])
        self.file_watcher.directoryChanged.connect(self.on_sounds_dir_changed)
        
    def setup_audio_routing(self):
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
        if hasattr(self, 'virtual_cable_stream') and self.virtual_cable_stream:
            self.virtual_cable_stream.stop_stream()
            self.virtual_cable_stream.close()
        if hasattr(self, 'speaker_stream') and self.speaker_stream:
            self.speaker_stream.stop_stream()
            self.speaker_stream.close()
        
        mic_device_index = self.audio.get_default_input_device_info()['index']
        virtual_cable_output_index = self.get_vb_cable_output_index()
        if virtual_cable_output_index is None:
            QMessageBox.warning(self, "VB-Cable Not Found", 
                                "VB-Cable was not detected. Please install it for proper audio routing.")
            virtual_cable_output_index = self.audio.get_default_output_device_info()['index']
        default_output_device_index = self.audio.get_default_output_device_info()['index']
        
        def audio_callback(in_data, frame_count, time_info, status):
            in_data_array = np.frombuffer(in_data, dtype=np.int16)
            
            if self.is_playing_sound and len(self.current_sound_data) > 0:
                if len(self.current_sound_data) >= len(in_data_array):
                    sound_chunk = self.current_sound_data[:len(in_data_array)]
                    self.current_sound_data = self.current_sound_data[len(in_data_array):]
                else:
                    sound_chunk = np.pad(self.current_sound_data, (0, len(in_data_array) - len(self.current_sound_data)))
                    self.current_sound_data = np.array([], dtype=np.int16)
                mixed_audio = np.clip(in_data_array.astype(np.int32) + sound_chunk.astype(np.int32), -32768, 32767).astype(np.int16)
            else:
                mixed_audio = in_data_array
                self.is_playing_sound = False
            
            try:
                self.virtual_cable_stream.write(mixed_audio.tobytes())
                self.speaker_stream.write(mixed_audio.tobytes())
            except Exception as e:
                logging.error(f"Error writing to output streams: {e}")
            
            return (None, pyaudio.paContinue)
        
        try:
            # Open the output streams
            self.virtual_cable_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                output_device_index=virtual_cable_output_index,
                frames_per_buffer=CHUNK
            )
            self.speaker_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                output_device_index=default_output_device_index,
                frames_per_buffer=CHUNK
            )
            # Open the input stream
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                input=True,
                input_device_index=mic_device_index,
                stream_callback=audio_callback,
                frames_per_buffer=CHUNK
            )
            self.input_stream.start_stream()
        except Exception as e:
            logging.error(f"Error setting up audio routing: {e}")
            QMessageBox.critical(self, "Audio Setup Error", 
                                f"Failed to set up audio routing: {str(e)}")

    @pyqtSlot(str)
    def on_sounds_dir_changed(self, path):
        self.refresh_sound_list()

    def add_sound_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Sound File", "", "Sound Files (*.wav *.mp3)")
        if file_path:
            file_name = os.path.basename(file_path)
            destination = os.path.join(SOUNDS_DIR, file_name)
            os.makedirs(SOUNDS_DIR, exist_ok=True)
            os.replace(file_path, destination)
            self.sounds[file_name] = {'path': destination, 'title': file_name, 'favorite': False, 'play_count': 0}
            self.save_config()
            self.refresh_sound_list()

    def delete_selected_sound(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            file_name = selected_item.filename
            reply = QMessageBox.question(self, 'Delete Sound', 
                                         f"Are you sure you want to delete '{selected_item.text()}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                file_path = self.sounds[file_name]['path']
                os.remove(file_path)
                del self.sounds[file_name]
                if file_name in self.hotkeys:
                    del self.hotkeys[file_name]
                self.save_config()
                self.refresh_sound_list()
                QMessageBox.information(self, 'Sound Deleted', 
                                        f'Sound "{selected_item.text()}" has been deleted.',
                                        QMessageBox.Ok)

    def play_selected_sound(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            sound_file = self.sounds[selected_item.filename]['path']
            self.sounds[selected_item.filename]['play_count'] = self.sounds[selected_item.filename].get('play_count', 0) + 1
            self.save_config()
            threading.Thread(target=self.play_audio, args=(sound_file,)).start()

    def play_audio(self, sound_file):
        try:
            file_extension = os.path.splitext(sound_file)[1].lower()
            
            if file_extension == '.wav':
                self.play_wav_with_routing(sound_file)
            elif file_extension == '.mp3':
                self.play_mp3_with_routing(sound_file)
            else:
                logging.error(f"Unsupported file format: {file_extension}")
        except Exception as e:
            logging.error(f"Error playing audio: {e}")
            
    def play_wav_with_routing(self, sound_file):
        with wave.open(sound_file, 'rb') as wf:
            self.current_sound_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        self.is_playing_sound = True

    def play_wav(self, sound_file):
        wf = wave.open(sound_file, 'rb')
        self.stream = self.audio.open(format=self.audio.get_format_from_width(wf.getsampwidth()),
                                      channels=wf.getnchannels(),
                                      rate=wf.getframerate(),
                                      output=True)
        data = wf.readframes(CHUNK)
        while data:
            self.stream.write(data)
            data = wf.readframes(CHUNK)
        self.stream.stop_stream()
        self.stream.close()
        wf.close()
    
    def play_mp3_with_routing(self, sound_file):
        try:
            audio = mutagen.File(sound_file)
            if audio is None:
                raise ValueError("Could not read audio file metadata")
            
            with silence_pygame():
                pygame.mixer.init(frequency=44100, channels=1)  # Force mono
                sound = pygame.mixer.Sound(sound_file)
                array_sound = pygame.sndarray.samples(sound)
                if array_sound.ndim > 1:
                    array_sound = array_sound.mean(axis=1)  # Convert stereo to mono
                self.current_sound_data = array_sound.astype(np.int16)
            self.is_playing_sound = True

        except Exception as e:
            logging.error(f"Error playing MP3 with routing: {e}")
            
    def get_loopback_device_index(self):
        for i in range(self.audio.get_device_count()):
            dev_info = self.audio.get_device_info_by_index(i)
            if "virtual audio cable" in dev_info['name'].lower():
                return i
        return None
    
    def get_default_output_device_index(self):
        return self.audio.get_default_output_device_info()['index']

    def assign_hotkey(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            sound_file = selected_item.filename
            current_hotkey = self.hotkeys.get(sound_file, "")
            self.hotkey_dialog = HotkeyDialog(current_hotkey, self)
            
            self.current_keys.clear()            
            self.hotkey_listener = pynput_keyboard.Listener(on_press=self.on_hotkey_press, on_release=self.on_hotkey_release)
            self.hotkey_listener.start()
            result = self.hotkey_dialog.exec_()
            self.hotkey_listener.stop()
            
            if result == QDialog.Accepted:
                self.finish_hotkey_assignment(sound_file)

    def on_hotkey_press(self, key):
        if self.hotkey_dialog:
            key_str = self.key_to_string(key)
            if key_str:
                if not self.current_keys:
                    self.current_keys.clear()
                
                self.current_keys.add(key_str)
                self.hotkey_dialog.current_hotkey = self.current_keys.copy()
                self.hotkey_dialog.update_hotkey_label()

    def on_hotkey_release(self, key):
        if self.hotkey_dialog:
            key_str = self.key_to_string(key)
            if key_str and key_str in self.current_keys:
                self.current_keys.discard(key_str)

    def key_to_string(self, key):
        """Convert a key press event to a string representation, including modifier keys."""
        if isinstance(key, pynput_keyboard.KeyCode):
            if key.vk is not None:
                if key.vk == 17:  # Ctrl key
                    return 'Ctrl'
                elif key.vk == 16:  # Shift key
                    return 'Shift'
                elif key.vk == 18:  # Alt key
                    return 'Alt'
                elif 65 <= key.vk <= 90:  # A-Z keys
                    return chr(key.vk)
                elif 96 <= key.vk <= 105:  # Numpad keys
                    return f'Numpad{key.vk - 96}'
                else:
                    return f'VK_{key.vk}'
            elif key.char:
                return key.char.upper()
            return None
        elif isinstance(key, pynput_keyboard.Key):
            if key == pynput_keyboard.Key.ctrl or key == pynput_keyboard.Key.ctrl_l or key == pynput_keyboard.Key.ctrl_r:
                return 'Ctrl'
            elif key == pynput_keyboard.Key.alt or key == pynput_keyboard.Key.alt_l or key == pynput_keyboard.Key.alt_r:
                return 'Alt'
            elif key == pynput_keyboard.Key.shift or key == pynput_keyboard.Key.shift_l or key == pynput_keyboard.Key.shift_r:
                return 'Shift'
            elif key == pynput_keyboard.Key.space:
                return 'Space'
            elif key == pynput_keyboard.Key.enter:
                return 'Enter'
            elif hasattr(key, 'name'):
                return key.name.capitalize()
            else:
                return str(key).replace('Key.', '').capitalize()
        return None

    def finish_hotkey_assignment(self, sound_file):
        hotkey_str = '+'.join(sorted(self.hotkey_dialog.current_hotkey))
        if hotkey_str:
            self.hotkeys[sound_file] = hotkey_str
            self.save_config()
            QMessageBox.information(self, 'Hotkey Assigned', 
                                    f'Hotkey "{hotkey_str}" assigned to "{self.sounds[sound_file]["title"]}"',
                                    QMessageBox.Ok)
        else:
            if sound_file in self.hotkeys:
                del self.hotkeys[sound_file]
                self.save_config()
                QMessageBox.information(self, 'Hotkey Removed', 
                                        f'Hotkey removed from "{self.sounds[sound_file]["title"]}"',
                                        QMessageBox.Ok)
        self.update_hotkey_button_text()

    def update_hotkey_button_text(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            sound_file = selected_item.filename
            if sound_file in self.hotkeys:
                self.assign_hotkey_button.setText(f'Reassign Hotkey ({self.hotkeys[sound_file]})')
            else:
                self.assign_hotkey_button.setText('Assign Hotkey')

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                self.sounds = config.get('sounds', {})
                self.hotkeys = config.get('hotkeys', {})
            
            for sound, value in self.sounds.items():
                if isinstance(value, str):
                    self.sounds[sound] = {
                        'path': value,
                        'title': sound,
                        'favorite': False,
                        'play_count': 0
                    }
        self.refresh_sound_list()

    def refresh_sound_list(self):
        self.sound_list.clear()
        for sound, info in self.sounds.items():
            title = info['title']
            favorite = info.get('favorite', False)
            item = SoundItem(title, sound, favorite)
            self.sound_list.addItem(item)
        
        for sound in list(self.sounds.keys()):
            path = self.sounds[sound]['path']
            if not os.path.exists(path):
                del self.sounds[sound]
                if sound in self.hotkeys:
                    del self.hotkeys[sound]
        
        self.save_config()
        self.sort_sound_list()

    def save_config(self):
        config = {
            'sounds': self.sounds,
            'hotkeys': self.hotkeys
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)

    def setup_keyboard_listener(self):
        def on_press(key):
            # print(key)
            if self.hotkey_dialog:
                return

            key_str = self.key_to_string(key)
            if key_str:
                self.current_keys.add(key_str)
                self.check_hotkeys()

        def on_release(key):
            key_str = self.key_to_string(key)
            if key_str and key_str in self.current_keys:
                self.current_keys.discard(key_str)

        self.listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()

    def check_hotkeys(self):
        for sound, hotkey in self.hotkeys.items():
            expected_keys = set(hotkey.split('+'))
            if expected_keys == self.current_keys:
                threading.Thread(target=self.play_audio, args=(self.sounds[sound]['path'],)).start()
                return

    def rename_sound(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            current_title = selected_item.text()
            dialog = QInputDialog(self)
            dialog.setWindowTitle('Rename Sound')
            dialog.setLabelText('Enter new title:')
            dialog.setTextValue(current_title)

            screen_size = QDesktopWidget().screenGeometry()
            dialog.resize(int(screen_size.width() * 0.3), int(screen_size.height() * 0.2))

            if dialog.exec_() == QDialog.Accepted:
                new_title = dialog.textValue()
                if new_title and new_title != current_title:
                    self.sounds[selected_item.filename]['title'] = new_title
                    selected_item.setText(new_title)
                    self.save_config()
                    self.sort_sound_list()
                    QMessageBox.information(self, 'Sound Renamed', 
                                            f'Sound renamed from "{current_title}" to "{new_title}"',
                                            QMessageBox.Ok)

    def toggle_favorite(self):
        selected_item = self.sound_list.currentItem()
        if selected_item:
            selected_item.is_favorite = not selected_item.is_favorite
            self.sounds[selected_item.filename]['favorite'] = selected_item.is_favorite
            selected_item.update_icon()
            self.save_config()
            self.sort_sound_list()
            status = "added to" if selected_item.is_favorite else "removed from"
            QMessageBox.information(self, 'Favorite Updated', 
                                    f'"{selected_item.text()}" has been {status} favorites.',
                                    QMessageBox.Ok)

    def sort_sound_list(self):
        sort_option = self.sort_combo.currentText()
        items = []
        for i in range(self.sound_list.count()):
            item = self.sound_list.takeItem(0)
            items.append(item)
        
        if sort_option == "Name (A-Z)":
            items.sort(key=lambda x: x.text().lower())
        elif sort_option == "Name (Z-A)":
            items.sort(key=lambda x: x.text().lower(), reverse=True)
        elif sort_option == "Favorites First":
            items.sort(key=lambda x: (not x.is_favorite, x.text().lower()))
        elif sort_option == "Most Played":
            items.sort(key=lambda x: self.sounds[x.filename].get('play_count', 0), reverse=True)
        
        for item in items:
            self.sound_list.addItem(item)

    def closeEvent(self, event):
        self.listener.stop()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        event.accept()