from src.function import split_docx_pipline


def main():
    input_dir = r"D:\compile\Test\input"
    output_dir = r"D:\compile\Test\output"
    work_dir = r"D:\compile\Test"
    days_to_keep = 1

    split_docx_pipline(input_dir=input_dir,
                       output_dir=output_dir,
                       work_dir=work_dir,
                       days_to_keep=days_to_keep
                       )


if __name__ == "__main__":
    main()