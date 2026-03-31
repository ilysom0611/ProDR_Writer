"""
Word Document Writer Tool for Disaster Recovery Solution
高质量灾备技术方案 Word 文档生成工具
"""
from crewai.tools import BaseTool
from pydantic import Field
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from datetime import datetime
from typing import Dict, Any, List
import os


class WordDocumentWriterTool(BaseTool):
    """
    生成高质量灾备技术方案 Word 文档的工具
    
    输入: content (Dict) - 包含文档所有内容的字典
    输出: output_path (str) - 保存路径
    """
    name: str = "word_document_writer"
    description: str = "生成高质量灾备技术方案 Word 文档。将完整的文档内容结构写入 Word 文件。"

    def _set_cell_shading(self, cell, color: str):
        """设置单元格背景色"""
        shading_elm = OxmlElement('w:shd')
        shading_elm.set(qn('w:fill'), color)
        cell._tc.get_or_add_tcPr().append(shading_elm)

    def _set_cell_border(self, cell, **kwargs):
        """设置单元格边框"""
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement('w:tcBorders')
        for edge in ['top', 'left', 'bottom', 'right']:
            edge_data = kwargs.get(edge)
            if edge_data:
                tag = f'w:{edge}'
                element = OxmlElement(tag)
                element.set(qn('w:val'), edge_data.get('val', 'single'))
                element.set(qn('w:sz'), str(edge_data.get('sz', 4)))
                element.set(qn('w:color'), edge_data.get('color', '000000'))
                tcBorders.append(element)
        tcPr.append(tcBorders)

    def _add_page_number(self, doc):
        """添加页码"""
        for section in doc.sections:
            footer = section.footer
            paragraph = footer.paragraphs[0]
            paragraph.text = ""
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            run = paragraph.add_run()
            fldChar1 = OxmlElement('w:fldChar')
            fldChar1.set(qn('w:fldCharType'), 'begin')
            
            instrText = OxmlElement('w:instrText')
            instrText.set(qn('xml:space'), 'preserve')
            instrText.text = "PAGE"
            
            fldChar2 = OxmlElement('w:fldChar')
            fldChar2.set(qn('w:fldCharType'), 'separate')
            
            fldChar3 = OxmlElement('w:fldChar')
            fldChar3.set(qn('w:fldCharType'), 'end')
            
            run._r.append(fldChar1)
            run._r.append(instrText)
            run._r.append(fldChar2)
            run._r.append(fldChar3)
            
            run = paragraph.add_run(" / ")
            
            fldChar4 = OxmlElement('w:fldChar')
            fldChar4.set(qn('w:fldCharType'), 'begin')
            
            instrText2 = OxmlElement('w:instrText')
            instrText2.set(qn('xml:space'), 'preserve')
            instrText2.text = "NUMPAGES"
            
            fldChar5 = OxmlElement('w:fldChar')
            fldChar5.set(qn('w:fldCharType'), 'separate')
            
            fldChar6 = OxmlElement('w:fldChar')
            fldChar6.set(qn('w:fldCharType'), 'end')
            
            run._r.append(fldChar4)
            run._r.append(instrText2)
            run._r.append(fldChar5)
            run._r.append(fldChar6)

    def _create_title_page(self, doc: Document, content: Dict[str, Any]):
        """创建封面"""
        # 标题
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title.add_run("\n\n\n\n")
        
        title_run = title.add_run(content.get('title', '灾备技术方案'))
        title_run.font.size = Pt(44)
        title_run.font.bold = True
        title_run.font.color.rgb = RGBColor(0, 51, 102)
        
        # 副标题
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sub_run = subtitle.add_run(f"\n\n{content.get('subtitle', '')}")
        sub_run.font.size = Pt(28)
        sub_run.font.color.rgb = RGBColor(64, 64, 64)
        
        # 分割线
        doc.add_paragraph("\n\n\n\n")
        
        # 项目信息表格
        info_table = doc.add_table(rows=5, cols=2)
        info_table.style = 'Table Grid'
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        info_data = [
            ("项目名称", content.get('project_name', '')),
            ("投标单位", content.get('company_name', '')),
            ("编制日期", content.get('date', datetime.now().strftime('%Y年%m月%d日'))),
            ("版本号", content.get('version', 'V1.0')),
            ("密级", content.get('classification', '机密'))
        ]
        
        for i, (label, value) in enumerate(info_data):
            row = info_table.rows[i]
            row.height = Cm(1.2)
            
            label_cell = row.cells[0]
            label_cell.width = Cm(4)
            label_cell.text = label
            self._set_cell_shading(label_cell, "003366")
            para = label_cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.runs[0]
            run.font.size = Pt(14)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            
            value_cell = row.cells[1]
            value_cell.text = value
            para = value_cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = para.runs[0]
            run.font.size = Pt(14)

    def _create_toc_page(self, doc: Document, content: Dict[str, Any]):
        """创建目录页"""
        doc.add_page_break()
        
        toc_title = doc.add_heading('目 录', level=1)
        toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        toc_entries = content.get('toc', [])
        for entry in toc_entries:
            p = doc.add_paragraph()
            p.add_run(entry.get('title', ''))
            p.add_run('\t' * 6)
            p.add_run(entry.get('page', '1'))
        
        doc.add_page_break()

    def _create_section(self, doc: Document, section: Dict[str, Any]):
        """创建章节"""
        # 章节标题
        heading = doc.add_heading(section.get('title', ''), level=1)
        heading.runs[0].font.color.rgb = RGBColor(0, 51, 102)
        
        # 章节内容
        for item in section.get('content', []):
            item_type = item.get('type', 'text')
            
            if item_type == 'text':
                p = doc.add_paragraph(item.get('text', ''))
                p.paragraph_format.first_line_indent = Cm(0.74)  # 首行缩进2字符
                p.paragraph_format.line_spacing = 1.5
                
            elif item_type == 'heading':
                doc.add_heading(item.get('text', ''), level=2)
                
            elif item_type == 'subheading':
                doc.add_heading(item.get('text', ''), level=3)
                
            elif item_type == 'list':
                for list_item in item.get('items', []):
                    p = doc.add_paragraph(list_item, style='List Bullet')
                    p.paragraph_format.line_spacing = 1.5
                    
            elif item_type == 'numbered_list':
                for i, list_item in enumerate(item.get('items', []), 1):
                    p = doc.add_paragraph(f"{i}. {list_item}")
                    p.paragraph_format.line_spacing = 1.5
                    
            elif item_type == 'table':
                self._create_table(doc, item)
                
            elif item_type == 'image':
                # 图片需要图片路径
                if item.get('path'):
                    try:
                        doc.add_picture(item['path'], width=Inches(6))
                    except:
                        p = doc.add_paragraph(f"[图片: {item.get('caption', '')}]")

    def _create_table(self, doc: Document, table_data: Dict[str, Any]):
        """创建表格"""
        rows = table_data.get('rows', [])
        if not rows:
            return
            
        table = doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        for i, row_data in enumerate(rows):
            for j, cell_data in enumerate(row_data):
                cell = table.rows[i].cells[j]
                cell.text = str(cell_data)
                
                # 表头样式
                if i == 0:
                    self._set_cell_shading(cell, "003366")
                    para = cell.paragraphs[0]
                    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    run = para.runs[0]
                    run.font.size = Pt(11)
                    run.font.bold = True
                    run.font.color.rgb = RGBColor(255, 255, 255)
                else:
                    para = cell.paragraphs[0]
                    run = para.runs[0]
                    run.font.size = Pt(10)

    def _run(self, content: str = None, output_path: str = None) -> str:
        """同步执行方法 - BaseTool 要求"""
        return self.run(content, output_path)

    def run(self, content=None, output_path: str = None) -> str:
        """
        生成 Word 文档

        Args:
            content: 文档内容（dict 或 JSON 字符串）
            output_path: 输出文件路径

        Returns:
            str: JSON 格式结果字符串
        """
        import json as json_module
        try:
            # 如果 content 是字符串，尝试解析为 JSON
            if isinstance(content, str):
                try:
                    content = json_module.loads(content)
                except (json_module.JSONDecodeError, TypeError):
                    # 解析失败，使用空字典
                    content = {}

            # content 可能是 None 或其他类型
            if not isinstance(content, dict) or content is None:
                content = {}

            # 默认输出路径
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_path = f"outputs/灾备技术方案_{timestamp}.docx"

            os.makedirs(os.path.dirname(output_path) or 'outputs', exist_ok=True)

            # 创建文档
            doc = Document()
            for section in doc.sections:
                section.top_margin = Cm(2.54)
                section.bottom_margin = Cm(2.54)
                section.left_margin = Cm(3.17)
                section.right_margin = Cm(3.17)

            self._add_page_number(doc)

            # 如果有结构化内容，使用完整模板
            if content.get('sections') or content.get('project_name'):
                self._build_professional_doc(doc, content)
            else:
                # 回退：创建基础文档
                self._build_basic_doc(doc, content)

            doc.save(output_path)
            result = {
                "status": "success",
                "data": {
                    "document_path": output_path
                }
            }
            return json_module.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            import json as json_module
            result = {
                "status": "error",
                "message": f"生成文档时出错: {str(e)}",
                "data": {}
            }
            return json_module.dumps(result, ensure_ascii=False, indent=2)

    def _parse_task_description(self, text: str) -> dict:
        """从任务描述文本中解析出文档内容"""
        import re
        content = {
            'project_name': '',
            'company_name': '',
            'industry': '',
            'date': datetime.now().strftime('%Y年%m月%d日'),
            'sections': []
        }

        # 提取项目名称
        name_match = re.search(r'["""]?项目名称["""]?\s*[:：]\s*(.+?)(?:\n|$)', text)
        if name_match:
            content['project_name'] = name_match.group(1).strip()

        # 提取投标单位
        company_match = re.search(r'["""]?投标单位["""]?\s*[:：]\s*(.+?)(?:\n|$)', text)
        if company_match:
            content['company_name'] = company_match.group(1).strip()

        # 提取行业
        industry_match = re.search(r'["""]?行业["""]?\s*[:：]\s*(.+?)(?:\n|$)', text)
        if industry_match:
            content['industry'] = industry_match.group(1).strip()

        # 从 JSON 块中提取 BIA 数据
        bia_match = re.search(r'### BIA[^\n]*\n(.+?)(?=\n###|\n---\n|$)', text, re.DOTALL)
        if bia_match:
            bia_text = bia_match.group(1)
            systems = []
            for m in re.finditer(r'"name"\s*:\s*"([^"]+)"', bia_text):
                systems.append(m.group(1))
            if systems:
                content['sections'].append({
                    'title': '业务影响分析（BIA）',
                    'content': [{'type': 'text', 'text': bia_text.strip()[:2000]}]
                })

        # 尝试从文本中找 JSON 块（架构等）
        json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
        sections = []
        for block in json_blocks[:5]:
            try:
                import json as json_module
                parsed = json_module.loads(block)
                # 如果是架构相关 JSON
                if isinstance(parsed, dict) and ('architecture' in str(parsed) or 'dr_strategy' in str(parsed)):
                    sections.append({
                        'title': '灾备架构设计',
                        'content': [{'type': 'text', 'text': json_module.dumps(parsed, ensure_ascii=False, indent=2)[:3000]}]
                    })
            except:
                pass

        if sections and len(content['sections']) == 0:
            content['sections'].extend(sections)

        return content

    def _build_professional_doc(self, doc: Document, content: dict):
        """构建专业文档"""
        # 封面
        doc.add_paragraph("\n\n\n\n")
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run(content.get('project_name', '灾备技术方案'))
        run.font.size = Pt(44)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 51, 102)

        doc.add_paragraph("\n")
        sub = doc.add_paragraph()
        sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = sub.add_run("技术方案投标文件")
        run.font.size = Pt(24)
        run.font.color.rgb = RGBColor(64, 64, 64)

        doc.add_paragraph("\n\n\n")
        info_table = doc.add_table(rows=4, cols=2)
        info_table.style = 'Table Grid'
        info_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        info_data = [
            ("投标单位", content.get('company_name', 'XX科技有限公司')),
            ("行业", content.get('industry', '金融')),
            ("日期", content.get('date', datetime.now().strftime('%Y年%m月%d日'))),
            ("密级", "机密")
        ]
        for i, (label, value) in enumerate(info_data):
            row = info_table.rows[i]
            label_cell = row.cells[0]
            label_cell.text = label
            self._set_cell_shading(label_cell, "003366")
            para = label_cell.paragraphs[0]
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            para.runs[0].font.size = Pt(12)
            para.runs[0].font.bold = True
            para.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            value_cell = row.cells[1]
            value_cell.text = value
            value_cell.paragraphs[0].runs[0].font.size = Pt(12)

        doc.add_page_break()

        # 目录
        toc_heading = doc.add_heading('目 录', level=1)
        toc_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sections = content.get('sections', [])
        if not sections:
            sections = [{'title': '第一章 概述'}, {'title': '第二章 需求分析'},
                        {'title': '第三章 方案设计'}, {'title': '第四章 投资估算'},
                        {'title': '第五章 风险评估'}]
        for i, sec in enumerate(sections, 1):
            p = doc.add_paragraph(f"第一章  {sec.get('title', '章节')}")
            p.paragraph_format.line_spacing = 1.5

        doc.add_page_break()

        # 各章节
        for sec in sections:
            h = doc.add_heading(sec.get('title', ''), level=1)
            h.runs[0].font.color.rgb = RGBColor(0, 51, 102)
            for item in sec.get('content', []):
                if item.get('type') == 'text':
                    p = doc.add_paragraph(item.get('text', ''))
                    p.paragraph_format.first_line_indent = Cm(0.74)
                    p.paragraph_format.line_spacing = 1.5
                elif item.get('type') == 'table':
                    self._create_table(doc, item)
                elif item.get('type') == 'list':
                    for li in item.get('items', []):
                        doc.add_paragraph(li, style='List Bullet')
                elif item.get('type') == 'heading':
                    doc.add_heading(item.get('text', ''), level=2)

        # 添加执行摘要
        if not sections:
            doc.add_heading('第一章 概述', level=1)
            doc.add_paragraph(
                f"本方案针对 {content.get('project_name', '本项目')} 进行灾备技术设计。"
                f"投标单位：{content.get('company_name', 'XX科技有限公司')}，"
                f"行业：{content.get('industry', '金融')}。"
                "\n\n本方案涵盖业务影响分析、现状评估、灾备架构设计、技术选型、"
                "投资估算和风险评估等内容，可作为投标技术文件使用。"
            )

    def _build_basic_doc(self, doc: Document, content: dict):
        """构建基础文档（fallback）"""
        doc.add_paragraph("\n\n")
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run(content.get('project_name', '灾备技术方案'))
        run.font.size = Pt(36)
        run.font.bold = True
        doc.add_paragraph(f"\n投标单位: {content.get('company_name', '')}")
        doc.add_paragraph(f"日期: {content.get('date', '')}")
        doc.add_page_break()
        doc.add_heading('概述', level=1)
        doc.add_paragraph('本灾备技术方案针对项目需求进行系统性设计。')


class DisasterRecoveryDocWriterTool(BaseTool):
    """
    专用于灾备技术方案的 Word 文档生成工具
    提供预设的文档模板和格式
    """
    name: str = "disaster_recovery_doc_writer"
    description: str = "生成高质量灾备技术方案 Word 文档，包含封面、目录、需求分析、方案设计等完整章节。"

    output_path: str = Field(description="输出文件路径")
    
    def _create_dr_document(self, doc: Document, content: Dict[str, Any]):
        """创建灾备技术方案文档"""
        # 封面
        doc.add_paragraph("\n\n\n\n")
        title = doc.add_paragraph()
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title.add_run("灾备技术方案")
        run.font.size = Pt(44)
        run.font.bold = True
        
        subtitle = doc.add_paragraph()
        subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = subtitle.add_run(f"\n\n{content.get('project_name', '')}")
        run.font.size = Pt(24)
        
        # 投标单位信息
        doc.add_paragraph("\n\n\n\n")
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        info.add_run(f"投标单位: {content.get('company_name', '')}\n\n")
        info.add_run(f"日期: {datetime.now().strftime('%Y年%m月%d日')}")

    def _run(self, content: str = None, output_path: str = None) -> str:
        """同步执行方法 - BaseTool 要求"""
        return self.run(content, output_path)

    def run(self, content: str = None, output_path: str = None) -> str:
        """生成灾备技术方案文档"""
        tool = WordDocumentWriterTool()
        return tool.run(content=content, output_path=output_path or self.output_path)
