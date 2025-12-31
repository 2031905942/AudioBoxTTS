import traceback
from pathlib import Path
from typing import Optional

from lxml.etree import Element

from lxml import etree
from Source.Utility.base_utility import BaseUtility


class XmlUtility(BaseUtility):
    def read_xml(self, xml_path: str) -> Optional[Element]:
        if not xml_path:
            self.error_signal.emit("读取Xml文件失败, 路径为空.")
            return None
        if not Path(xml_path).is_file():
            self.error_signal.emit(f"读取Xml文件失败, 路径不合法:\n{xml_path}")
            return None
        try:
            element_tree = etree.parse(xml_path)
            element_root = element_tree.getroot()
            return element_root
        except Exception as error:
            self.error_signal.emit(f"读取Xml文件发生异常:\n{error}")
            self._print_log_error(f"读取Xml文件发生异常: {traceback.format_exc()}.")
        return None

    def write_wwise_xml(self, root_element: Element, path):
        xml_str: str = etree.tostring(root_element, encoding="unicode")
        xml_str = xml_str.replace(" />", "/>")
        xml_str = f"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n{xml_str}\n"
        try:
            with open(path, 'wb') as file:
                file.write(xml_str.encode())
        except Exception as error:
            self.error_signal.emit(f"写入Xml文件\"{path}\"发生异常:\n{error}")
            self._print_log_error(f"写入Xml文件\"{path}\"发生异常: {traceback.format_exc()}.")
