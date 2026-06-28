# coding: utf-8
import collections
import html
import re
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, QPointF, QMarginsF
from PySide6.QtGui import QColor, QPainter, QBrush, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QFileDialog
from qfluentwidgets import (
    ScrollArea, SubtitleLabel, BodyLabel, CardWidget, PrimaryPushButton, PushButton
)

_ELLIPSIS_COLORS = ['#e15b64', '#f47e60', '#f8b26a', '#abbd81', '#e15b64']


class EllipsisSpinner(QWidget):

    def __init__(self, size=18, parent=None):
        super().__init__(parent)
        w = size + (len(_ELLIPSIS_COLORS) - 1) * 8
        self.setFixedSize(w, size)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(60)
        self._timer.start()

    def _tick(self):
        self._phase += 1
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        n = len(_ELLIPSIS_COLORS)
        spacing = 8
        total_w = (n - 1) * spacing
        start_x = cx - total_w / 2.0
        period = 18

        for i in range(n):
            offset = (self._phase - i * (period // n)) % period
            t = offset / float(period)
            scale = t * 2.0 if t < 0.5 else (1.0 - t) * 2.0
            r = 2.0 + scale * 5.0
            x = start_x + i * spacing

            color = QColor(_ELLIPSIS_COLORS[i])
            color.setAlpha(int(80 + scale * 175))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(color))
            p.drawEllipse(QPointF(x, cy), r, r)

        p.end()

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()


class ThinkingWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick = 0
        self._cursor_visible = True
        self._base_text = 'AI分析中'
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._onAnimTick)
        self._anim_timer.setInterval(90)
        self.__initUI()

    def __initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._spinner = EllipsisSpinner(20)
        layout.addWidget(self._spinner)

        self._text = BodyLabel(self._base_text)
        self._text.setStyleSheet('font-size: 14px; font-weight: 600; color: #1F2937;')
        layout.addWidget(self._text)
        layout.addStretch()

    def _onAnimTick(self):
        self._tick += 1
        total = len(self._base_text)
        visible = (self._tick % (total + 4)) + 1
        if visible > total:
            visible = total
        self._cursor_visible = not self._cursor_visible
        cursor = '|' if self._cursor_visible else ' '
        self._text.setText(f'{self._base_text[:visible]}{cursor}')

    def start(self):
        self._spinner.start()
        self._anim_timer.start()
        self._tick = 0
        self._cursor_visible = True
        self._text.setText('A|')

    def stop(self):
        self._spinner.stop()
        self._anim_timer.stop()
        self._text.setText(self._base_text)


class AiAnalysisInterface(ScrollArea):

    MAX_CHART_POINTS = 10000
    SEMG_VALUE_SCALE = 1024.0
    _TABLE_SEPARATOR_RE = re.compile(r'^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('aiAnalysisInterface')
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self._last_report_html = ''
        self.__initWidget()
        self.__initLayout()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.vBoxLayout.setContentsMargins(20, 20, 20, 20)
        self.vBoxLayout.setSpacing(20)

    def __initLayout(self):
        title = SubtitleLabel('AI分析')
        self.vBoxLayout.addWidget(title)

        semg_card = self.__createSemgCard()
        self.vBoxLayout.addWidget(semg_card)

        ai_card = self.__createThinkingCard()
        self.vBoxLayout.addWidget(ai_card)

        self.vBoxLayout.addStretch()

    def __createSemgCard(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        header = SubtitleLabel('sEMG实时监控')
        layout.addWidget(header)

        self._semg_plot = pg.PlotWidget()
        self._semg_plot.setBackground('w')
        self._semg_plot.showGrid(x=True, y=True, alpha=0.3)
        self._semg_plot.setLabel('left', 'Amplitude')
        self._semg_plot.setLabel('bottom', '样本')
        self._semg_plot.setYRange(-4096, 4096)
        self._semg_plot.setMinimumHeight(320)
        self._semg_plot.getPlotItem().hideButtons()

        self._semg_waveform_curve = self._semg_plot.plot(pen=pg.mkPen(color='#0078D4', width=1))
        self._semg_rectified_curve = self._semg_plot.plot(pen=pg.mkPen(color='#0078D4', width=2))
        self._semg_envelope_curve = self._semg_plot.plot(pen=pg.mkPen(color='#E74C3C', width=3))
        layout.addWidget(self._semg_plot)

        self._semg_value_label = BodyLabel('当前: ---')
        self._semg_value_label.setStyleSheet('font-size: 14px; font-weight: bold; color: #0078D4;')
        layout.addWidget(self._semg_value_label)

        self._waveform_data = collections.deque(maxlen=self.MAX_CHART_POINTS)
        self._rectified_data = collections.deque(maxlen=self.MAX_CHART_POINTS)
        self._envelope_data = collections.deque(maxlen=self.MAX_CHART_POINTS)
        self._semg_point_count = 0
        self._semg_last_update = 0
        return card

    def append_sEMG_data(self, sample):
        if isinstance(sample, (tuple, list)) and len(sample) >= 3:
            waveform, rectified, envelope = sample[:3]
        else:
            waveform = sample
            rectified = abs(sample)
            envelope = abs(sample)

        self._waveform_data.append(waveform)
        self._rectified_data.append(rectified)
        self._envelope_data.append(envelope)
        self._semg_point_count += 1

        import time
        now = time.time()
        if now - self._semg_last_update < 0.016:
            return
        self._semg_last_update = now

        n = len(self._waveform_data)
        start_idx = 0 if self._semg_point_count <= self.MAX_CHART_POINTS else self._semg_point_count - n
        x = np.arange(start_idx, self._semg_point_count)
        self._semg_waveform_curve.setData(x=x, y=np.array(self._waveform_data, dtype=np.float64))
        self._semg_rectified_curve.setData(x=x, y=np.array(self._rectified_data, dtype=np.float64))
        self._semg_envelope_curve.setData(x=x, y=np.array(self._envelope_data, dtype=np.float64))

        if self._semg_point_count <= self.MAX_CHART_POINTS:
            self._semg_plot.setXRange(0, self.MAX_CHART_POINTS)
        else:
            self._semg_plot.setXRange(start_idx, start_idx + self.MAX_CHART_POINTS)

        val = self._envelope_data[-1] / self.SEMG_VALUE_SCALE if n > 0 else 0
        self._semg_value_label.setText(f'当前: sEMG: {val:.2f}')

    def __createThinkingCard(self):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self._think_widget = ThinkingWidget()
        header_row.addWidget(self._think_widget)
        header_row.addStretch()

        self._ai_trigger_btn = PrimaryPushButton('AI分析')
        self._ai_trigger_btn.setFixedWidth(108)
        self._ai_trigger_btn.clicked.connect(self._onAiTrigger)
        header_row.addWidget(self._ai_trigger_btn)

        self._export_pdf_btn = PushButton('导出PDF')
        self._export_pdf_btn.setFixedWidth(108)
        self._export_pdf_btn.setEnabled(False)
        self._export_pdf_btn.clicked.connect(self._exportAiReportPdf)
        header_row.addWidget(self._export_pdf_btn)

        layout.addLayout(header_row)

        self._ai_result_edit = QTextEdit()
        self._ai_result_edit.setReadOnly(True)
        self._ai_result_edit.setMinimumHeight(380)
        self._ai_result_edit.setMaximumHeight(520)
        self._ai_result_edit.setPlaceholderText('点击“AI分析”开始生成 sEMG 分析报告...')
        self._ai_result_edit.setStyleSheet(
            'QTextEdit { border: 1px solid #E0E0E0; border-radius: 6px; '
            'padding: 12px; font-size: 14px; color: #323130; background: #FAFAFA; }'
        )
        self._ai_result_edit.document().setDefaultStyleSheet(
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
        layout.addWidget(self._ai_result_edit)
        return card

    @staticmethod
    def _format_inline_markdown(text: str) -> str:
        escaped = html.escape(text.strip())
        escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)
        return escaped

    @classmethod
    def _is_table_block_start(cls, lines, index: int) -> bool:
        if index + 1 >= len(lines):
            return False
        return '|' in lines[index] and bool(cls._TABLE_SEPARATOR_RE.match(lines[index + 1]))

    @staticmethod
    def _parse_table_cells(line: str) -> list[str]:
        text = line.strip()
        if text.startswith('|'):
            text = text[1:]
        if text.endswith('|'):
            text = text[:-1]
        return [cell.strip() for cell in text.split('|')]

    @classmethod
    def _render_table_html(cls, lines, start: int) -> tuple[str, int]:
        header_cells = cls._parse_table_cells(lines[start])
        body_rows = []
        index = start + 2

        while index < len(lines):
            line = lines[index]
            if not line.strip() or '|' not in line:
                break
            body_rows.append(cls._parse_table_cells(line))
            index += 1

        parts = ['<table><thead><tr>']
        parts.extend(f'<th>{cls._format_inline_markdown(cell)}</th>' for cell in header_cells)
        parts.append('</tr></thead><tbody>')

        for row in body_rows:
            parts.append('<tr>')
            parts.extend(f'<td>{cls._format_inline_markdown(cell)}</td>' for cell in row)
            parts.append('</tr>')

        parts.append('</tbody></table>')
        return ''.join(parts), index

    @classmethod
    def _render_markdown_html(cls, text: str) -> str:
        lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        blocks = []
        index = 0

        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue

            if cls._is_table_block_start(lines, index):
                table_html, index = cls._render_table_html(lines, index)
                blocks.append(table_html)
                continue

            if stripped.startswith('#'):
                level = len(stripped) - len(stripped.lstrip('#'))
                level = max(1, min(level, 6))
                content = cls._format_inline_markdown(stripped[level:].strip())
                blocks.append(f'<h{level}>{content}</h{level}>')
                index += 1
                continue

            if stripped.startswith('- '):
                items = []
                while index < len(lines) and lines[index].strip().startswith('- '):
                    items.append(f'<li>{cls._format_inline_markdown(lines[index].strip()[2:])}</li>')
                    index += 1
                blocks.append(f"<ul>{''.join(items)}</ul>")
                continue

            if re.match(r'^\d+\.\s+', stripped):
                items = []
                while index < len(lines) and re.match(r'^\d+\.\s+', lines[index].strip()):
                    item_text = re.sub(r'^\d+\.\s+', '', lines[index].strip(), count=1)
                    items.append(f'<li>{cls._format_inline_markdown(item_text)}</li>')
                    index += 1
                blocks.append(f"<ol>{''.join(items)}</ol>")
                continue

            paragraph_lines = [stripped]
            index += 1
            while index < len(lines):
                next_line = lines[index].strip()
                if not next_line:
                    break
                if (
                    next_line.startswith('#')
                    or next_line.startswith('- ')
                    or re.match(r'^\d+\.\s+', next_line)
                    or cls._is_table_block_start(lines, index)
                ):
                    break
                paragraph_lines.append(next_line)
                index += 1

            paragraph = '<br/>'.join(cls._format_inline_markdown(part) for part in paragraph_lines)
            blocks.append(f'<p>{paragraph}</p>')

        return f"<html><body>{''.join(blocks)}</body></html>"

    def _setAiResultHtml(self, html_text: str, allow_export: bool = True):
        self._last_report_html = html_text
        self._ai_result_edit.setHtml(html_text)
        has_content = bool(self._ai_result_edit.toPlainText().strip())
        self._export_pdf_btn.setEnabled(allow_export and has_content)

    def _exportAiReportPdf(self):
        plain_text = self._ai_result_edit.toPlainText().strip()
        if not plain_text:
            self._setAiResultHtml(
                self._render_markdown_html('[错误] 当前没有可导出的 AI 分析报告。'),
                allow_export=False
            )
            return

        default_name = f"腰部康复训练分析报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, '导出 AI 分析报告', default_name, 'PDF Files (*.pdf)'
        )
        if not file_path:
            return
        if not file_path.lower().endswith('.pdf'):
            file_path += '.pdf'

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter)

        document = self._ai_result_edit.document().clone()
        document.setPageSize(printer.pageRect(QPrinter.Point).size())

        try:
            document.print_(printer)
        except Exception as e:
            self._setAiResultHtml(
                self._render_markdown_html(f'[错误] PDF 导出失败: {e}'),
                allow_export=False
            )

    def _onAiTrigger(self):
        if hasattr(self, '_ai_analyzer') and self._ai_analyzer:
            self._ai_analyzer.trigger_analysis()
        else:
            self._setAiResultHtml(
                self._render_markdown_html('[错误] AI分析模块未连接，请检查配置。'),
                allow_export=False
            )

    def set_ai_analyzer(self, analyzer):
        self._ai_analyzer = analyzer

    def on_ai_thinking(self, thinking: bool):
        if thinking:
            self._think_widget.start()
            self._ai_trigger_btn.setEnabled(False)
            self._setAiResultHtml(
                self._render_markdown_html('AI 分析中，请稍候...'),
                allow_export=False
            )
        else:
            self._think_widget.stop()
            self._ai_trigger_btn.setEnabled(True)

    def on_ai_result(self, text: str):
        self._setAiResultHtml(self._render_markdown_html(text))

    def on_ai_error(self, error: str):
        self._setAiResultHtml(
            self._render_markdown_html(f'[错误] {error}'),
            allow_export=False
        )
