import json
import logging
import os
import re 
from typing import Optional, Dict, Tuple

try:
    import pymsgbox
except Exception:
    pymsgbox = None

try:
    import tkinter as tk
except Exception:
    tk = None


def generatetext(output_dir, work_dir):
    """Show two dialogs: one via pymsgbox, one via tkinter.

    Args:
        output_dir: 输出目录（未强制使用，仅保留为接口一致性）
        work_dir: 工作目录（未强制使用，仅保留为接口一致性）
    """
    # PyMsgBox 弹窗（确认按钮组）
    if pymsgbox:
        try:
            choice1 = pymsgbox.confirm(text='这是 PyMsgBox 弹窗，选择一个按钮：', title='PyMsgBox', buttons=['确定', '取消'])
        except Exception as e:
            choice1 = f'pymsgbox 报错: {e}'
    else:
        choice1 = 'pymsgbox 未安装'

    # Tkinter 弹窗（自定义窗口 + 两个按钮）
    if tk:
        try:
            root = tk.Tk()
            root.withdraw()

            sel = {'value': None}

            win = tk.Toplevel(root)
            win.title('Tkinter 弹窗')
            win.geometry('320x140')

            label = tk.Label(win, text='这是 Tkinter 弹窗，选择一个按钮：')
            label.pack(pady=12)

            def on_ok():
                sel['value'] = '确定'
                win.destroy()

            def on_cancel():
                sel['value'] = '取消'
                win.destroy()

            btn_frame = tk.Frame(win)
            btn_frame.pack(pady=8)

            ok_btn = tk.Button(btn_frame, text='确定', width=10, command=on_ok)
            ok_btn.pack(side='left', padx=8)
            cancel_btn = tk.Button(btn_frame, text='取消', width=10, command=on_cancel)
            cancel_btn.pack(side='left', padx=8)

            win.protocol('WM_DELETE_WINDOW', on_cancel)
            root.wait_window(win)
            choice2 = sel['value']
            root.destroy()
        except Exception as e:
            choice2 = f'tkinter 报错: {e}'
    else:
        choice2 = 'tkinter 不可用'

    # 最终结果提示（优先使用 pymsgbox.alert，否则打印）
    result_text = f'PyMsgBox 选择: {choice1}\nTkinter 选择: {choice2}'
    if pymsgbox:
        try:
            pymsgbox.alert(result_text, '选择结果')
        except Exception:
            print(result_text)
    else:
        print(result_text)


if __name__ == "__main__":
    # 输入文件位置（当前未使用，可根据需要扩展）
    input_dir = r"D:\\compile\\Test\\input"
    # 输出文件位置
    output_dir = r"D:\\compile\\Test\\output"
    # 代码保存位置
    work_dir = r"D:\\compile\\Test"

    # 确保目录存在
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    generatetext(output_dir, work_dir)
