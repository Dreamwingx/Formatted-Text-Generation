import os
import sys
import time
import uuid
import argparse
import requests
import zipfile

# $env:MINERU_API_TOKEN="eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI1NTYwMDQwMSIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc3MjE1NDkxOCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiMTg5OTEzOTcyMDkiLCJvcGVuSWQiOm51bGwsInV1aWQiOiI5MzEyNTg2NC0wMjIyLTRmZmYtOTY3ZS04MjBhMDZlMmY2NzgiLCJlbWFpbCI6IiIsImV4cCI6MTc3OTkzMDkxOH0.E0PXyRGDdPtxWsC3o2LK_TJOL7sSSNUVJ8B5sqnRqi2lrNMKnmeEp4LxAIAKPhmWGgE6C5Nzu-JzKZRaR6GlZQ"


def select_file():
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()
        path = filedialog.askopenfilename()
        root.destroy()
        if path:
            return path
    except Exception:
        pass

    path = input("请输入要上传的文件路径 (或拖入并回车): ").strip('" ')
    if not path:
        print("未选择文件，退出.")
        sys.exit(1)
    if not os.path.isfile(path):
        print(f"文件不存在: {path}")
        sys.exit(1)
    return path


def get_token():
    token = os.getenv("MINERU_API_TOKEN")
    if token:
        return token
    token = input("请输入 Mineru API Token: ").strip()
    if not token:
        print("未提供 token，退出.")
        sys.exit(1)
    return token


def apply_upload_url(token, filename, data_id=None, model_version="vlm"):
    url = "https://mineru.net/api/v4/file-urls/batch"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    if data_id is None:
        data_id = uuid.uuid4().hex
    data = {
        "files": [{"name": filename, "data_id": data_id}],
        "model_version": model_version
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"apply upload url failed: {result}")
    file_urls = result["data"]["file_urls"]
    batch_id = result["data"].get("batch_id")
    return batch_id, file_urls


def upload_file_to_url(file_path, upload_url):
    with open(file_path, 'rb') as f:
        resp = requests.put(upload_url, data=f)
    return resp


def poll_extract_result(token, batch_id, filename, timeout=600, interval=5):
    """轮询 extract-results，直至该文件的 state 为 done 或 failed，返回 full_zip_url（如果有）。"""
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    end = time.time() + timeout
    while time.time() < end:
        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            result = resp.json()
        except Exception as e:
            print("查询提取结果失败：", e)
            time.sleep(interval)
            continue

        if result.get("code") != 0:
            print("查询返回非 0 code：", result)
            time.sleep(interval)
            continue

        items = result.get("data", {}).get("extract_result", [])
        # 找到对应文件
        item = None
        for it in items:
            if it.get("file_name") == filename:
                item = it
                break
        if not item:
            print("还未在结果中找到文件条目，继续等待...")
            time.sleep(interval)
            continue

        state = item.get("state")
        if state == "done":
            zip_url = item.get("full_zip_url")
            if zip_url:
                return zip_url
            else:
                raise RuntimeError("处理完成但未返回 full_zip_url")
        elif state == "failed":
            raise RuntimeError(f"提取失败: {item.get('err_msg')}")
        else:
            prog = item.get("extract_progress")
            if prog:
                extracted = prog.get("extracted_pages")
                total = prog.get("total_pages")
                print(f"处理中: {extracted}/{total} 页，状态: {state}")
            else:
                print(f"状态: {state}，继续等待...")
            time.sleep(interval)

    raise TimeoutError("等待提取结果超时，请稍后重试或增加 --timeout 值。")


def download_url_to_file(url, dest_path):
    print(f"开始下载: {url}\n保存到: {dest_path}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = r.headers.get('content-length')
        total = int(total) if total is not None else None
        written = 0
        with open(dest_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = written * 100 / total
                        print(f"下载进度: {pct:.1f}% ({written}/{total})", end='\r')
    print("\n下载完成。")


def extract_zip_to_dir(zip_path, extract_dir):
    """将 zip 文件解压到指定目录（会创建目录）。"""
    print(f"开始解压: {zip_path} -> {extract_dir}")
    try:
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        print("解压完成。")
    except Exception as e:
        raise RuntimeError(f"解压失败: {e}")


def mineru(output_dir):
    """上传文件到 Mineru 并在处理完成后下载提取结果 zip 到指定的 output_dir。

    说明：此函数不再从命令行读取 --timeout 或 --interval，使用内置默认值。
    """
    # 默认轮询参数（如需不同值，可让调用方在外部实现重试或调整）
    timeout = 600
    interval = 5

    file_path = select_file()
    token = get_token()
    filename = os.path.basename(file_path)

    print(f"准备上传: {file_path} -> 文件名: {filename}")

    try:
        batch_id, file_urls = apply_upload_url(token, filename)
        upload_url = file_urls[0]
        print(f"得到上传 URL，开始上传...")
        resp = upload_file_to_url(file_path, upload_url)
        if resp.status_code in (200, 201):
            print("上传成功，开始轮询提取结果...")
        else:
            print(f"上传失败: status={resp.status_code}, resp={resp.text}")
            return

        zip_url = poll_extract_result(token, batch_id, filename, timeout=timeout, interval=interval)

        out_dir = os.path.abspath(output_dir)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.splitext(filename)[0]
        dest = os.path.join(out_dir, f"{base}_extract.zip")
        download_url_to_file(zip_url, dest)
        print(f"文件已保存到: {dest}")

        extract_dir = os.path.join(out_dir, f"{base}_extract")
        try:
            extract_zip_to_dir(dest, extract_dir)
            print(f"已解压到: {extract_dir}")
        except Exception as e:
            print("解压失败:", e)
    except Exception as e:
        print("发生错误:", e)


if __name__ == '__main__':
    mineru(os.path.abspath(os.getcwd()))
