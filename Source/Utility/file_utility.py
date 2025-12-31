import filecmp
import hashlib
import os
import pathlib
import shutil
import time
import traceback
from datetime import datetime
from typing import Optional

from Source.Utility.base_utility import BaseUtility


class FileUtility(BaseUtility):
    def create_directory(self, dir_path: str) -> bool:
        try:
            os.makedirs(dir_path, exist_ok=True)
            return True
        except Exception as error:
            self.error_signal.emit(f"创建目录发生异常:\n{error}")
            return False

    def remove_empty_directory(self, dir_path: str):
        if not os.path.isdir(dir_path):
            return
        self.update_progress_text_signal.emit(f"清理空目录...\n\"{dir_path}\"")
        for (path, _, files) in os.walk(dir_path, topdown=False):
            if files:
                continue
            if path == dir_path:
                continue
            try:
                os.rmdir(path)
            except OSError:
                pass

    def backup_directory(self, dir_path: str) -> bool:
        if not os.path.isdir(dir_path):
            self.error_signal.emit(f"目录路径不合法:\n{dir_path}")
            return False

        current_time = datetime.now()
        current_time_string: str = current_time.strftime("%m-%d %H-%M-%S")
        backup_dir_path: str = f"{dir_path}(备份) {current_time_string}"
        self.update_progress_text_signal.emit(f"备份目录...\n\"{backup_dir_path}\"")
        try:
            if os.path.exists(backup_dir_path):
                shutil.rmtree(backup_dir_path)
            shutil.copytree(dir_path, backup_dir_path)
        except Exception as error:
            self.error_signal.emit(f"备份目录发生异常:\n{error}")
            self._print_log_error(f"备份目录发生异常: {traceback.format_exc()}.")
            return False
        return True

    def get_files(self, dir_path: str, extension_list: Optional[list[str]] = None, is_except_extension_list: bool = False, file_name_list: Optional[list[str]] = None, is_recursively: bool = True) -> \
            list[str]:
        file_path_list: [str] = []
        if not os.path.isdir(dir_path):
            return file_path_list
        scan_dir_iterator = os.scandir(dir_path)
        for dir_entry in scan_dir_iterator:
            dir_entry: os.DirEntry
            if dir_entry.is_file():
                is_added: bool = False
                if extension_list:
                    find_match_file: bool = False
                    for extension in extension_list:
                        extension: str
                        if dir_entry.name.lower().endswith(extension):
                            find_match_file = True
                            break
                    if find_match_file:
                        is_added = not is_except_extension_list
                    else:
                        if file_name_list:
                            if dir_entry.name in file_name_list:
                                is_added = True
                        else:
                            is_added = is_except_extension_list
                else:
                    if file_name_list:
                        if dir_entry.name in file_name_list:
                            is_added = True
                    else:
                        is_added = True
                if is_added:
                    file_path = str(dir_entry.path.replace("\\", "/"))
                    file_path_list.append(file_path)
            elif dir_entry.is_dir() and is_recursively:
                child_file_path_list = self.get_files(dir_entry.path, extension_list, is_except_extension_list, file_name_list)
                file_path_list += child_file_path_list
        return file_path_list

    def move_file(self, src_path: str, dst_path: str) -> bool:
        if not os.path.isfile(src_path):
            self.error_signal.emit(f"移动文件失败, 源文件路径不合法:\n{src_path}")
            return False
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.move(src_path, dst_path)
            return True
        except Exception as error:
            self.error_signal.emit(f"移动文件发生异常:\n{error}")
            return False

    def copy_file(self, src_path: str, dst_path: str, use_copy2 = True) -> bool:
        if not os.path.isfile(src_path):
            self.error_signal.emit(f"复制文件失败, 源文件路径不合法:\n{src_path}")
            return False
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            if use_copy2:
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copy(src_path, dst_path)
            return True
        except Exception as error:
            self.error_signal.emit(f"复制文件发生异常:\n{error}")
            return False

    def sync_file(self, src_path: str, dst_path: str, use_copy2 = True) -> tuple[bool, bool]:
        if not os.path.isfile(src_path):
            self.error_signal.emit(f"同步文件失败, 源文件路径不合法:\n{src_path}")
            return False, False
        if not os.path.isfile(dst_path):
            self.error_signal.emit(f"同步文件失败, 目标文件路径不合法:\n{dst_path}")
            return False, False
        try:
            start_time = time.time()
            is_same = FileUtility.compare_file(src_path, dst_path)
            end_time = time.time()
            print(f"比对文件\"{pathlib.Path(src_path).name}\";" + " 耗时: {:.3f}秒;".format(end_time - start_time))
            if is_same:
                return True, False
            else:
                start_time = time.time()
                copy_result: bool = self.copy_file(src_path, dst_path, use_copy2)
                end_time = time.time()
                print(f"拷贝文件\"{pathlib.Path(src_path).name}\";" + " 耗时: {:.3f}秒;".format(end_time - start_time))
                return True, copy_result
        except Exception as error:
            self.error_signal.emit(f"同步文件发生异常:\n{error}")
            return False, False

    @staticmethod
    def compare_file(file1, file2, chunk_size=8192) -> bool:
        # 先比较文件大小
        if os.path.getsize(file1) != os.path.getsize(file2):
            return False

        # 逐块计算哈希
        hash1 = hashlib.md5()
        hash2 = hashlib.md5()

        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            while True:
                chunk1 = f1.read(chunk_size)
                chunk2 = f2.read(chunk_size)
                if chunk1 != chunk2:  # 提前终止差异
                    return False
                if not chunk1:  # 文件结束
                    break
                hash1.update(chunk1)
                hash2.update(chunk2)

        return hash1.digest() == hash2.digest()

    def delete_file(self, path: str) -> bool:
        if not os.path.isfile(path):
            self.error_signal.emit(f"删除文件失败, 路径不合法:\n{path}")
            return False
        try:
            os.remove(path)
            return True
        except Exception as error:
            self.error_signal.emit(f"删除文件\"{path}\"发生异常:\n{error}")
            return False

    def check_same_file(self, src_file_path: str, dst_file_path: str) -> bool:
        try:
            is_same: bool = filecmp.cmp(src_file_path, dst_file_path, shallow=False)
            return is_same
        except Exception as error:
            self.error_signal.emit(f"检查文件内容是否相同发生异常:\n{error}")
            return False

    def calculate_file_hash(self, file_path: str, algorithm: str = 'md5', buffer_size: int = 65536):
        """
        计算文件的哈希值
        :param file_path: 文件路径
        :param algorithm: 哈希算法（如 'md5', 'sha1', 'sha256'）
        :param buffer_size: 分块读取的缓冲区大小（字节）
        :return: 十六进制哈希字符串
        """
        try:
            hash_obj = hashlib.new(algorithm)
            with open(file_path, 'rb') as f:
                while chunk := f.read(buffer_size):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as error:
            self.error_signal.emit(f"计算文件\"{file_path}\"的哈希值发生异常:\n{error}")
            return None
