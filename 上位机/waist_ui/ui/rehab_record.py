# coding: utf-8
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit
from qfluentwidgets import (
    ScrollArea,
    SubtitleLabel,
    BodyLabel,
    CaptionLabel,
    CardWidget,
    PushButton,
)

from ui.ai_analysis import AiAnalysisInterface


class RehabRecordInterface(ScrollArea):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('rehabRecordInterface')
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self._records = {}
        self._selected_record_id = None
        self.__initWidget()
        self.__initLayout()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.vBoxLayout.setSpacing(20)

    def __initLayout(self):
        title = SubtitleLabel('康复记录')
        self.vBoxLayout.addWidget(title)
        self.vBoxLayout.addWidget(self.__createRecordCard())
        self.vBoxLayout.addWidget(self.__createReportCard())
        self.vBoxLayout.addStretch()

    def __createRecordCard(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel('训练记录'))

        tip = CaptionLabel('显示用户名称、训练开始时间，并可查看对应 AI 分析报告。')
        layout.addWidget(tip)

        self._record_list_layout = QVBoxLayout()
        self._record_list_layout.setSpacing(10)
        layout.addLayout(self._record_list_layout)

        self._empty_label = BodyLabel('当前暂无康复训练记录。')
        self._record_list_layout.addWidget(self._empty_label)
        return card

    def __createReportCard(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(SubtitleLabel('AI分析报告'))

        self._report_meta_label = CaptionLabel('请选择一条康复记录查看报告。')
        layout.addWidget(self._report_meta_label)

        self._report_edit = QTextEdit()
        self._report_edit.setReadOnly(True)
        self._report_edit.setMinimumHeight(420)
        self._report_edit.setPlaceholderText('点击右侧“查看报告”后，将在这里显示对应的 AI 分析结果。')
        self._report_edit.setStyleSheet(
            'QTextEdit { border: 1px solid #E0E0E0; border-radius: 6px; '
            'padding: 12px; font-size: 14px; color: #323130; background: #FAFAFA; }'
        )
        self._report_edit.document().setDefaultStyleSheet(
            'body { font-size: 14px; color: #323130; line-height: 1.7; }'
            'h1 { font-size: 22px; margin: 6px 0 14px 0; color: #1F2937; }'
            'h2 { font-size: 18px; margin: 14px 0 8px 0; color: #1F2937; }'
            'p { margin: 6px 0; }'
            'ul, ol { margin: 6px 0 6px 22px; }'
            'li { margin: 4px 0; }'
            'table { border-collapse: collapse; width: 100%; margin: 10px 0 14px 0; }'
            'th { background: #F3F4F6; font-weight: 600; }'
            'th, td { border: 1px solid #D1D5DB; padding: 8px 10px; text-align: left; }'
            'code { background: #F3F4F6; padding: 1px 4px; border-radius: 4px; }'
        )
        layout.addWidget(self._report_edit)
        return card

    def add_record(self, info: dict):
        record_id = info['record_id']
        if record_id in self._records:
            self._records[record_id]['info'] = info
            self._records[record_id]['name_label'].setText(info['user_name'])
            self._records[record_id]['time_label'].setText(info['start_time'])
            return

        if self._empty_label is not None:
            self._empty_label.hide()

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(12, 8, 12, 8)
        row_layout.setSpacing(16)

        name_label = BodyLabel(info['user_name'])
        row_layout.addWidget(name_label, 2)

        time_label = CaptionLabel(info['start_time'])
        row_layout.addWidget(time_label, 2)

        row_layout.addStretch(1)

        view_btn = PushButton('查看报告')
        view_btn.setFixedWidth(100)
        view_btn.clicked.connect(
            lambda checked=False, current_record_id=record_id: self.show_record_report(current_record_id)
        )
        row_layout.addWidget(view_btn)

        self._record_list_layout.addWidget(row_widget)
        self._records[record_id] = {
            'info': info,
            'report': '',
            'row_widget': row_widget,
            'name_label': name_label,
            'time_label': time_label,
            'view_btn': view_btn,
        }

    def set_record_report(self, record_id: str, report_text: str):
        record = self._records.get(record_id)
        if record is None:
            return
        record['report'] = report_text
        if self._selected_record_id == record_id:
            self.show_record_report(record_id)

    def show_record_report(self, record_id: str):
        record = self._records.get(record_id)
        if record is None:
            return

        self._selected_record_id = record_id
        info = record['info']
        self._report_meta_label.setText(
            f"用户名称：{info['user_name']}    开始时间：{info['start_time']}"
        )

        if record['report']:
            self._report_edit.setHtml(AiAnalysisInterface.render_report_html(record['report']))
        else:
            self._report_edit.setHtml(
                AiAnalysisInterface.render_report_html(
                    '该条康复记录暂未生成 AI 分析报告，请稍后再查看。'
                )
            )
