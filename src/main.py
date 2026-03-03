from function import split_docx_pipline


def main():
    # 输入文件位置
    input_dir = r"D:\compile\Test\input"
    # 输出文件位置
    output_dir = r"D:\compile\Test\output"
    # 代码保存位置
    work_dir = r"D:\compile\Test"
    # 日志保存时间（单位：天）
    days_to_keep = 1

    split_docx_pipline(input_dir=input_dir,
                       output_dir=output_dir,
                       work_dir=work_dir,
                       days_to_keep=days_to_keep
                       )


if __name__ == "__main__":
    main()