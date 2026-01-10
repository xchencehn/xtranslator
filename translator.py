import sys
import re
import os
import logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QPushButton, QTextEdit, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QPointF
from PyQt6.QtGui import (
    QCursor, QAction, QPainter, QColor, QBrush, QPainterPath, QPixmap, QIcon, QPolygonF
)
from pynput import keyboard
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('translator.log', encoding='utf-8')]
)
logger = logging.getLogger(__name__)


# API Configuration
API_KEY = "uZa_BE743Y-PrqVpp5-eJbc5RqQpM4JpxcsoW1jZPfk"
BASE_URL = "https://api.poe.com/v1"
MODEL = "gpt-5.2-instant"

# Hotkey Configuration
HOTKEY = "<alt>+1"
HOTKEY_DISPLAY = "Alt+1"


def create_icon():
    """Create a simple program icon"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw circular background
    painter.setBrush(QBrush(QColor("#8b5cf6")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    
    # Draw lightning symbol
    painter.setBrush(QBrush(QColor("white")))
    lightning = QPolygonF([
        QPointF(36, 12),
        QPointF(24, 30),
        QPointF(32, 30),
        QPointF(28, 52),
        QPointF(40, 28),
        QPointF(32, 28),
    ])
    painter.drawPolygon(lightning)
    
    painter.end()
    return QIcon(pixmap)


class TranslateThread(QThread):
    """Translation thread to avoid blocking UI"""
    finished = pyqtSignal(str, bool)
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        
    def run(self):
        try:
            result = self.translate(self.text)
            self.finished.emit(result, True)
        except Exception as e:
            self.finished.emit(str(e), False)
    
    def translate(self, text):
        """Use AI for translation or query, AI automatically identifies task type"""
        logger.info(f"Starting translation: {text[:50]}...")
        prompt = f"""Please automatically determine the task type based on the following text and output the corresponding result:

1. If it's a word or phrase query:
   - If it's an English word, provide Chinese translation, concise explanation, and phonetic transcription
   - If it's a Chinese phrase, provide English translation and concise explanation
   - Keep explanations concise

2. If it's sentence translation:
   - If it's Chinese, translate to English
   - If it's English, translate to Chinese
   - Only output the translation result, no explanations or additional content

Text content:
{text}"""
        
        system_content = """You are a professional translation and dictionary assistant. Please automatically identify whether the user input is a word/phrase or a sentence, determine the language direction (Chinese or English), and then output the corresponding result:
- Word/phrase: Provide translation and concise explanation
- Sentence: Only output translation result, no additional content
- Return only text, no markdown format, no redundant formatted text, use simple spaces and line breaks to control format"""
        
        import time
        max_retries = 3
        retry_delay = 2  # Retry delay (seconds)
        
        for attempt in range(max_retries):
            try:
                # Increase timeout to 60 seconds and add retry mechanism
                client = openai.OpenAI(
                    api_key=API_KEY, 
                    base_url=BASE_URL,
                    timeout=60.0  # Increased to 60 seconds
                )
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    extra_body={"thinking_level": "minimal"}
                )
                result = response.choices[0].message.content.strip()
                logger.info("Translation successful")
                return result
            except openai.APIConnectionError as e:
                logger.warning(f"Network connection failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))  # Incremental delay
                    continue
                logger.error(f"Network connection failed: {str(e)}")
                raise Exception(f"Network connection failed: {str(e)}")
            except openai.Timeout as e:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                logger.error(f"Request timeout (retried {max_retries} times)")
                raise Exception(f"Request timeout (retried {max_retries} times). Please check network connection or try again later")
            except openai.APIError as e:
                logger.warning(f"API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if "rate limit" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                logger.error(f"API error: {str(e)}")
                raise Exception(f"API error: {str(e)}")


# Color scheme - Soft dark theme
COLORS = {
    "bg_primary": "#0f0f0f",        # Primary background - Nearly pure black
    "bg_secondary": "#1a1a1a",      # Secondary background - Input field
    "bg_tertiary": "#141414",       # Result area background
    "border_default": "#2a2a2a",    # Default border
    "border_focus": "#8b5cf6",      # Focus border - Purple
    "text_primary": "#e4e4e7",      # Primary text - Soft white
    "text_secondary": "#a1a1aa",    # Secondary text
    "text_muted": "#52525b",        # Muted text
    "accent": "#8b5cf6",            # Accent color - Purple
    "success": "#a78bfa",           # Success - Light purple
    "warning": "#fbbf24",           # Warning - Amber
    "error": "#f87171",             # Error - Soft red
}

# Style constants
# Result box base style
RESULT_BASE_STYLE = f"""
    QTextEdit {{
        background: {COLORS['bg_tertiary']};
        border: 1px solid {COLORS['border_default']};
        border-radius: 10px;
        padding: 12px;
        font-size: 14px;
        line-height: 1.6;
    }}
"""

STYLES = {
    "button": """
        QPushButton {
            background: transparent;
            border: none;
            border-radius: 14px;
            font-size: 14px;
        }
    """,
    "button_copy": f"color: {COLORS['text_secondary']};",
    "button_copy_hover": f"background: {COLORS['bg_secondary']};",
    "button_close": f"color: {COLORS['text_secondary']};",
    "button_close_hover": f"background: #2a1a1a; color: {COLORS['error']};",
    "result_success": RESULT_BASE_STYLE + f"QTextEdit {{ color: {COLORS['text_primary']}; }}",
    "result_loading": RESULT_BASE_STYLE + f"QTextEdit {{ color: {COLORS['accent']}; }}",
    "result_error": f"""
        QTextEdit {{
            background: {COLORS['bg_tertiary']};
            border: 1px solid #3d2020;
            border-radius: 10px;
            padding: 12px;
            font-size: 14px;
            color: {COLORS['error']};
        }}
    """
}

SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        width: 0px;
        background: transparent;
    }
    QScrollBar:horizontal {
        height: 0px;
        background: transparent;
    }
"""


class TranslatorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.app_icon = create_icon()
        self.translate_thread = None
        self.drag_pos = None
        self.init_ui()
        self.setup_hotkey()
        self.setup_tray()
        
    def init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowIcon(self.app_icon)
        self.setFixedSize(400, 240)
        
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setGeometry(10, 10, 380, 220)
        self.container.setStyleSheet(f"""
            #container {{ 
                background: {COLORS['bg_primary']}; 
                border-radius: 16px; 
                border: 1px solid {COLORS['border_default']};
            }}
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)
        
        # Input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter text to translate, press Enter...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_secondary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: 10px;
                padding: 12px 14px;
                font-size: 14px;
                color: {COLORS['text_primary']};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['border_focus']};
                background: {COLORS['bg_secondary']};
            }}
            QLineEdit::placeholder {{
                color: {COLORS['text_muted']};
            }}
        """)
        self.input_field.returnPressed.connect(self.start_translate)
        layout.addWidget(self.input_field)
        
        # Result display area
        self.result_wrapper = QWidget()
        result_wrapper_layout = QVBoxLayout(self.result_wrapper)
        result_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        result_wrapper_layout.setSpacing(0)
        
        self.result_label = QTextEdit()
        self.result_label.setReadOnly(True)
        self.result_label.setPlaceholderText("Translation result will appear here...")
        self.result_label.setStyleSheet(STYLES["result_success"] + SCROLLBAR_STYLE)
        self.result_label.setMinimumHeight(80)
        self.result_label.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_label.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        result_wrapper_layout.addWidget(self.result_label)
        
        # Copy button placed at bottom right
        self.copy_btn = self._create_button("📋", "Copy translation result", STYLES["button"] + STYLES["button_copy"], 
                                       STYLES["button_copy_hover"], self.copy_result)
        self.copy_btn.setParent(self.result_label)
        self.copy_btn.raise_()
        
        layout.addWidget(self.result_wrapper)
        
        QTimer.singleShot(0, self._update_copy_button_position)
        
        # Bottom hint
        hint = QLabel(f"{HOTKEY_DISPLAY} to open | ESC to close")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
    
    def _create_button(self, text, tooltip, base_style, hover_style, slot):
        """Helper method to create buttons"""
        btn = QPushButton(text)
        btn.setFixedSize(28, 28)
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"{base_style} QPushButton:hover {{ {hover_style} }}")
        btn.clicked.connect(slot)
        return btn
        
    def paintEvent(self, event):
        # Remove shadow drawing, no more edge blur effect
        pass
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if self.drag_pos and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
    
    def mouseReleaseEvent(self, event):
        self.drag_pos = None
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_copy_button_position()
    
    def _update_copy_button_position(self):
        if hasattr(self, 'copy_btn') and hasattr(self, 'result_label'):
            btn_size = 28
            padding = 8
            x = self.result_label.width() - btn_size - padding
            y = self.result_label.height() - btn_size - padding
            self.copy_btn.move(max(0, x), max(0, y))
            self.copy_btn.raise_()
    
    def setup_hotkey(self):
        self.ctrl_pressed = False
        hotkey = keyboard.HotKey(keyboard.HotKey.parse(HOTKEY), 
                                 lambda: QTimer.singleShot(0, self.show_and_translate) if not self.ctrl_pressed else None)
        def on_press(k):
            if k in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.ctrl_pressed = True
            hotkey.press(self.listener.canonical(k))
        def on_release(k):
            if k in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                self.ctrl_pressed = False
            hotkey.release(self.listener.canonical(k))
        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.start()
    
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.app_icon)
        self.tray.setToolTip(f"Quick Translator - Press {HOTKEY_DISPLAY} to open")
        
        menu = QMenu()
        menu.addAction("Show", self.show_and_translate)
        menu.addSeparator()
        menu.addAction("Exit", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda r: self.show_and_translate() 
            if r == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )
        self.tray.show()
        self.tray.showMessage("Quick Translator started", 
                             f"Press {HOTKEY_DISPLAY} to open translation window\nUsing {MODEL} model",
                             QSystemTrayIcon.MessageIcon.Information, 2000)
    
    def quit_app(self):
        self.listener.stop()
        QApplication.quit()
    
    def show_and_translate(self):
        cursor_pos = QCursor.pos()
        screen = QApplication.primaryScreen().geometry()
        x = max(10, min(cursor_pos.x() - 200, screen.width() - 410))
        y = cursor_pos.y() + 20 if cursor_pos.y() + 240 <= screen.height() - 50 else cursor_pos.y() - 260
        
        self.move(x, y)
        self.show()
        self.activateWindow()
        self.raise_()
        self.input_field.clear()
        self.result_label.clear()
        self.input_field.setFocus()
    
    def copy_result(self):
        result = self.result_label.toPlainText()
        if result and not result.startswith(("⏳", "❌")):
            QApplication.clipboard().setText(result)
            original_style = self.result_label.styleSheet()
            # Only change text color, not border
            copy_style = original_style.replace(
                f"color: {COLORS['text_primary']}", 
                f"color: {COLORS['success']}"
            ).replace(
                f"color: {COLORS['accent']}", 
                f"color: {COLORS['success']}"
            )
            self.result_label.setStyleSheet(copy_style)
            QTimer.singleShot(300, lambda: self.result_label.setStyleSheet(original_style))
    
    def start_translate(self):
        text = self.input_field.text().strip()
        if not text or (self.translate_thread and self.translate_thread.isRunning()):
            return
        
        self.result_label.setStyleSheet(STYLES["result_loading"] + SCROLLBAR_STYLE)
        self.result_label.setText("⏳ AI translating...")
        QTimer.singleShot(10, self._update_copy_button_position)
        
        self.translate_thread = TranslateThread(text)
        self.translate_thread.finished.connect(self.on_translate_finished)
        self.translate_thread.start()
    
    def on_translate_finished(self, result, success):
        style_key = "result_success" if success else "result_error"
        self.result_label.setStyleSheet(STYLES[style_key] + SCROLLBAR_STYLE)
        self.result_label.setText(result if success else f"❌ Translation failed: {result}")
        QTimer.singleShot(10, self._update_copy_button_position)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    window = TranslatorWindow()
    window.hide()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()