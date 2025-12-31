'''
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from TTS.tts.layers.xtts.tokenizer import VoiceBpeTokenizer
from qfluentwidgets import BodyLabel, PlainTextEdit, PrimaryPushButton, PushButton


class TTSTextEditWindow(QWidget):
    support_language_list = ["en", "ja"]

    confirm_signal: Signal = Signal(dict)

    def __init__(self, title: str, arg_dict: dict):
        super().__init__()
        self.arg_dict = arg_dict
        self.tokenizer = VoiceBpeTokenizer()
        self.setStyleSheet("background-color: white")
        self.setWindowFlags(Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowStaysOnTopHint)

        from fastlangid.langid import LID
        self.langid = LID()

        self._confirm_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.InsertParagraphSeparator, self)
        self._confirm_shortcut.activated.connect(self.on_confirmed)

        self._cancel_shortcut: QShortcut = QShortcut(QKeySequence.StandardKey.Cancel, self)
        self._cancel_shortcut.activated.connect(self.close)

        self.vbox_layout: QVBoxLayout = QVBoxLayout(self)
        self.hbox_layout: QHBoxLayout = QHBoxLayout()

        self._text_label: BodyLabel = BodyLabel(self)
        self._text_label.setText(title)

        self._text_edit = PlainTextEdit(self)
        self._text_edit.setMinimumWidth(300)
        self._text_edit.setMinimumHeight(200)
        self._text_edit.textChanged.connect(self.on_text_changed)

        self._text_language_predict_label = BodyLabel(self)
        self._text_language_predict_label.setText("预测语言:")

        self._text_predict_language = BodyLabel(self)
        self._text_language_predict_layout = QHBoxLayout()

        self._text_language_predict_layout.addWidget(self._text_language_predict_label)
        self._text_language_predict_layout.addWidget(self._text_predict_language)
        self._text_language_predict_layout.addStretch()

        self._confirm_button: PrimaryPushButton = PrimaryPushButton(self)
        self._confirm_button.setText("确认")
        self._confirm_button.setMinimumWidth(100)
        self._confirm_button.clicked.connect(self.on_confirmed)
        self._confirm_button.setEnabled(False)

        self._cancel_button: PushButton = PushButton(self)
        self._cancel_button.setText("取消")
        self._cancel_button.setMinimumWidth(100)
        self._cancel_button.clicked.connect(self.close)

        self.vbox_layout.addWidget(self._text_label)
        self.vbox_layout.addWidget(self._text_edit)
        self.vbox_layout.addLayout(self._text_language_predict_layout)
        self.hbox_layout.addWidget(self._confirm_button)
        self.hbox_layout.addWidget(self._cancel_button)
        self.vbox_layout.addLayout(self.hbox_layout)

        self.show()

    def on_confirmed(self):
        text = self._text_edit.toPlainText()
        text = text.strip()
        self.arg_dict["text"] = text
        self.confirm_signal.emit(self.arg_dict)
        self.close()

    def on_text_changed(self):
        display_text = ""
        text = self._text_edit.toPlainText()
        if not text:
            self._text_predict_language.setText(display_text)
            self._confirm_button.setEnabled(False)
        else:
            language = self.langid.predict(text)
            language = language.split("-")[0]
            if language == "en":
                display_text = "英语"
            elif language == "ja":
                display_text = "日语"

            if language in self.support_language_list:
                self.arg_dict["language"] = language
                self._confirm_button.setEnabled(True)
                text_limit = self.tokenizer.char_limits.get(language, 250)
                if len(text) > text_limit:
                    display_text = f"{display_text} (超出长度限制\"{text_limit}\")"
            else:
                display_text = f"{language} (暂不支持)"
                self._confirm_button.setEnabled(False)
            self._text_predict_language.setText(display_text)
'''